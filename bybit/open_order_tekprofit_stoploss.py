from pybit.unified_trading import HTTP, WebSocket
from utils.send_tg_message import send_message_to_telegram
from logger_config import setup_logger
from config import API_KEY, API_SECRET, TELEGRAM_BOT_TOKEN
from database import get_all_subscribed_users, save_completed_transaction
from bybit.position_monitor import position_monitor
import asyncio
import time
import aiohttp

# --- НАСТРОЙКИ ДЛЯ ТОРГОВЛИ STRONG SHORT ---
TRADE_SYMBOL = "Clankerusdt".upper()  # ← тикер монеты (в верхнем регистре)
TRADE_AMOUNT = 5            # ← сумма в долларах на одну сделку
TAKE_PROFIT_PERCENT = 15    # ← тейк профит 15%
AVERAGING_PERCENT = 20      # ← усреднение при росте на 20%
STOP_LOSS_PERCENT = 30      # ← стоп лосс 30%

# Настраиваем логгер
logger = setup_logger(__name__)

key = API_KEY
secret = API_SECRET

if not key or not secret:
    logger.error("API_KEY или API_SECRET не заданы. Проверьте файл .env.")
    exit(1)

session = HTTP(api_key=key, api_secret=secret, testnet=False, recv_window=60000)

# Глобальная переменная для хранения задачи мониторинга
monitoring_task = None

# Получение минимального значения qty и шага qty
def get_qty_limits(symbol):
    try:
        response = session.get_instruments_info(category="linear")
        if response.get("retCode") == 0:
            instruments = response.get("result", {}).get("list", [])
            for instrument in instruments:
                if instrument.get("symbol") == symbol:
                    lot_size_filter = instrument.get("lotSizeFilter", {})
                    min_qty = float(lot_size_filter.get("minOrderQty", 1))
                    step_size = float(lot_size_filter.get("qtyStep", 1))
                    return min_qty, step_size
    except Exception as e:
        logger.error(f"Ошибка при получении ограничений qty для {symbol}: {e}")
    return 1, 1

def round_qty(qty, step_size):
    return round(qty - (qty % step_size), len(str(step_size).split('.')[1]))

# Открытие рыночного шорт-ордера
async def open_short(symbol, dollar_value, chat_ids):
    # Получаем цену через REST (для открытия позиции)
    response = session.get_tickers(category="linear", symbol=symbol)
    entry_price = 0
    if response.get("retCode") == 0:
        result = response.get("result", {}).get("list", [])
        for ticker in result:
            if ticker.get("symbol") == symbol:
                entry_price = float(ticker.get("lastPrice", 0))
    if entry_price <= 0:
        logger.error("Не удалось получить цену символа для открытия позиции.")
        await send_message_to_telegram(
            f"❌ Ошибка: Не удалось получить цену символа {symbol} для открытия позиции. Сигнал не обработан.",
            chat_ids, TELEGRAM_BOT_TOKEN
        )
        return None
    qty = dollar_value / entry_price * 10
    min_qty, step_size = get_qty_limits(symbol)
    if qty < min_qty:
        qty = min_qty
    qty = round_qty(qty, step_size)

    # Механизм автоматического увеличения qty до минимальной стоимости ордера
    order_value = qty * entry_price
    if order_value < 5.0:
        # Стартуем с минимально возможного qty
        min_qty_for_value = max(min_qty, 5.0 / entry_price)
        # Округляем вверх до ближайшего шага
        steps = int((min_qty_for_value - min_qty) / step_size)
        qty = min_qty + steps * step_size
        # Увеличиваем qty, пока не достигнем нужной стоимости
        while qty * entry_price < 5.0:
            qty += step_size
            qty = round(qty, len(str(step_size).split('.')[1]))
        order_value = qty * entry_price
        if order_value < 5.0:
            logger.error(f"Даже после увеличения qty ордер не соответствует минимальной стоимости 5 USDT: qty={qty}, entry_price={entry_price}, value={order_value}")
            await send_message_to_telegram(
                f"Ошибка: даже после увеличения qty ордер не соответствует минимальной стоимости 5 USDT (qty={qty}, цена={entry_price}, value={order_value})",
                chat_ids, TELEGRAM_BOT_TOKEN
            )
            return None
        else:
            logger.info(f"qty автоматически увеличено до {qty} для соответствия минимальной стоимости ордера 5 USDT")
            await send_message_to_telegram(
                f"qty автоматически увеличено до {qty} для соответствия минимальной стоимости ордера 5 USDT (итоговая стоимость: {order_value})",
                chat_ids, TELEGRAM_BOT_TOKEN
            )

    response = session.place_order(
        category="linear",
        symbol=symbol,
        side="Sell",
        orderType="Market",
        qty=str(qty),
        timeInForce="IOC",
        reduceOnly=False
    )
    if response.get("retCode") == 0:
        logger.info(f"Открыта шорт-позиция {symbol} qty={qty} по цене {entry_price}")
        await send_message_to_telegram(f"Открыта шорт-позиция {symbol} qty={qty} по цене {entry_price}", chat_ids, TELEGRAM_BOT_TOKEN)
        return entry_price, qty
    else:
        logger.error(f"Ошибка открытия позиции: {response.get('retMsg')}")
        await send_message_to_telegram(f"Ошибка открытия позиции: {response.get('retMsg')}", chat_ids, TELEGRAM_BOT_TOKEN)
        return None

# Установка тейк-профита
async def set_take_profit(symbol, qty, entry_price, percent, chat_ids):
    tp_price = entry_price * (1 - percent / 100)
    response = session.place_order(
        category="linear",
        symbol=symbol,
        side="Buy",
        orderType="Limit",
        qty=str(qty),
        price=str(tp_price),
        timeInForce="GTC",
        reduceOnly=True
    )
    if response.get("retCode") == 0:
        logger.info(f"Тейк-профит установлен на {tp_price}")
        await send_message_to_telegram(f"Тейк-профит установлен на {tp_price}", chat_ids, TELEGRAM_BOT_TOKEN)
    else:
        logger.error(f"Ошибка установки тейк-профита: {response.get('retMsg')}")
        await send_message_to_telegram(f"Ошибка установки тейк-профита: {response.get('retMsg')}", chat_ids, TELEGRAM_BOT_TOKEN)

# Установка стоп-лосса
async def set_stop_loss(symbol, qty, stop_price, chat_ids):
    response = session.place_order(
        category="linear",
        symbol=symbol,
        side="Buy",
        orderType="Stop",
        qty=str(qty),
        triggerPrice=str(stop_price),
        timeInForce="GTC",
        reduceOnly=True
    )
    if response.get("retCode") == 0:
        logger.info(f"Стоп-лосс установлен на {stop_price}")
        await send_message_to_telegram(f"Стоп-лосс установлен на {stop_price}", chat_ids, TELEGRAM_BOT_TOKEN)
    else:
        logger.error(f"Ошибка установки стоп-лосса: {response.get('retMsg')}")
        await send_message_to_telegram(f"Ошибка установки стоп-лосса: {response.get('retMsg')}", chat_ids, TELEGRAM_BOT_TOKEN)

# Основная стратегия STRONG SHORT
async def strong_short_strategy(symbol):
    global monitoring_task
    
    chat_ids = await get_all_subscribed_users()
    logger.info(f"Открываем первую шорт-позицию на ${TRADE_AMOUNT} (STRONG SHORT)")
    entry1 = await open_short(symbol, TRADE_AMOUNT, chat_ids)
    if not entry1:
        await send_message_to_telegram(
            f"❌ STRONG SHORT стратегия для {symbol} не запущена из-за ошибки открытия позиции.",
            chat_ids, TELEGRAM_BOT_TOKEN
        )
        return
    entry_price_1, qty1 = entry1
    
    # Добавляем позицию в мониторинг
    position_monitor.add_position(symbol, entry_price_1, qty1, "Sell")
    
    # Устанавливаем callback для остановки мониторинга
    def stop_monitoring_callback():
        global monitoring_task
        if monitoring_task:
            monitoring_task.cancel()
            logger.info(f"[StrongStrategy] Мониторинг стратегии для {symbol} остановлен из-за закрытия позиции")
    
    position_monitor.set_stop_callback(symbol, stop_monitoring_callback)
    
    # Запускаем мониторинг позиции
    loop = asyncio.get_event_loop()
    position_monitor.start_monitoring(symbol, loop)
    
    await set_take_profit(symbol, qty1, entry_price_1, TAKE_PROFIT_PERCENT, chat_ids)
    await send_message_to_telegram(
        f"Ожидание усреднения: если цена вырастет на {AVERAGING_PERCENT}% до {entry_price_1 * (1 + AVERAGING_PERCENT / 100)}", 
        chat_ids, TELEGRAM_BOT_TOKEN
    )

    ws_triggered = asyncio.Event()
    close_event = asyncio.Event()
    result_holder = {}
    usrednenie_done = False
    last_logged_time = time.time()
    log_interval = 10  # секунд
    current_price = {'value': entry_price_1}

    # Функция для проверки состояния позиции
    async def check_position_and_exit():
        """Проверяет состояние позиции и завершает работу при закрытии"""
        while True:
            try:
                # Проверяем состояние позиции через API
                response = session.get_positions(category="linear", symbol=symbol)
                if response.get("retCode") == 0:
                    positions = response.get("result", {}).get("list", [])
                    for position in positions:
                        if position.get("symbol") == symbol:
                            qty = float(position.get("size", 0))
                            if qty == 0:
                                logger.info(f"[StrongStrategy] Позиция {symbol} закрыта, завершаем работу стратегии")
                                # Устанавливаем события для завершения всех задач
                                ws_triggered.set()
                                close_event.set()
                                return
                
                await asyncio.sleep(5)  # Проверяем каждые 5 секунд
            except Exception as e:
                logger.error(f"[StrongStrategy] Ошибка при проверке позиции {symbol}: {e}")
                await asyncio.sleep(10)

    # Запускаем проверку позиции в отдельной задаче
    position_check_task = asyncio.create_task(check_position_and_exit())

    # --- Новый мониторинг цены через aiohttp WebSocket ---
    async def price_ws_monitor():
        nonlocal last_logged_time
        WS_URL = "wss://stream.bybit.com/v5/public/linear"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                sub_msg = {
                    "op": "subscribe",
                    "args": [f"tickers.{symbol}"]
                }
                await ws.send_json(sub_msg)
                logger.info(f"Подписка на {symbol} отправлена!")
                async for msg in ws:
                    # Проверяем, не нужно ли завершить работу
                    if close_event.is_set():
                        logger.info(f"[StrongStrategy] Получен сигнал завершения для {symbol}, останавливаем мониторинг цены")
                        break
                        
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = msg.json()
                        if 'data' in data and isinstance(data['data'], dict):
                            last_price = float(data['data'].get('lastPrice', 0))
                            if last_price > 0:
                                current_price['value'] = last_price
                                percent = ((last_price - entry_price_1) / entry_price_1) * 100
                                now = time.time()
                                if now - last_logged_time > log_interval:
                                    logger.info(f"Мониторинг: цена входа={entry_price_1}, текущая цена={last_price}, изменение={percent:.2f}%")
                                    last_logged_time = now
                                # Усреднение при росте на AVERAGING_PERCENT%
                                if not usrednenie_done and last_price >= entry_price_1 * (1 + AVERAGING_PERCENT / 100):
                                    result_holder['trigger_price'] = last_price
                                    loop.call_soon_threadsafe(ws_triggered.set)

    price_ws_task = asyncio.create_task(price_ws_monitor())

    # --- Параллельно логируем текущую цену и процент изменения ---
    async def periodic_log():
        while not close_event.is_set():
            last = current_price['value']
            percent = ((last - entry_price_1) / entry_price_1) * 100
            logger.info(f"Мониторинг: цена входа={entry_price_1}, текущая цена={last}, изменение={percent:.2f}%")
            await asyncio.sleep(log_interval)

    log_task = asyncio.create_task(periodic_log())

    # Ожидание усреднения или закрытия позиции
    try:
        await asyncio.wait_for(ws_triggered.wait(), timeout=3600)  # Максимум 1 час
    except asyncio.TimeoutError:
        logger.info(f"[StrongStrategy] Таймаут ожидания усреднения для {symbol}")
        position_check_task.cancel()
        price_ws_task.cancel()
        log_task.cancel()
        position_monitor.remove_position(symbol)
        return

    # Проверяем, не было ли закрытия позиции
    if close_event.is_set():
        logger.info(f"[StrongStrategy] Позиция {symbol} закрыта, завершаем работу")
        position_check_task.cancel()
        price_ws_task.cancel()
        log_task.cancel()
        position_monitor.remove_position(symbol)
        return

    usrednenie_done = True
    await send_message_to_telegram(
        f"Цена выросла на {AVERAGING_PERCENT}%. Усредняем! Текущая цена: {result_holder['trigger_price']}", 
        chat_ids, TELEGRAM_BOT_TOKEN
    )

    # Усреднение
    entry2 = await open_short(symbol, TRADE_AMOUNT, chat_ids)
    if not entry2:
        await send_message_to_telegram(
            f"❌ Ошибка усреднения для {symbol}: не удалось открыть вторую позицию. Стратегия остановлена.",
            chat_ids, TELEGRAM_BOT_TOKEN
        )
        position_check_task.cancel()
        price_ws_task.cancel()
        log_task.cancel()
        position_monitor.remove_position(symbol)
        return
    entry_price_2, qty2 = entry2
    total_qty = qty1 + qty2
    
    # Обновляем информацию о позиции в мониторе
    position_monitor.add_position(symbol, entry_price_2, total_qty, "Sell")
    
    # Стоп-лосс относительно цены входа первой позиции
    stop_loss_price = entry_price_1 * (1 + STOP_LOSS_PERCENT / 100)
    await set_stop_loss(symbol, total_qty, stop_loss_price, chat_ids)
    await set_take_profit(symbol, total_qty, entry_price_2, TAKE_PROFIT_PERCENT, chat_ids)

    # --- Приватный WebSocket для мониторинга исполнения ордеров ---
    private_ws = WebSocket(
        channel_type='private',
        api_key=key,
        api_secret=secret,
        testnet=False
    )
    close_info = {}

    def handle_execution_message(message):
        data = message.get('data', [])
        for exec_data in data:
            if exec_data.get('symbol') == symbol and exec_data.get('execType') == 'Trade':
                # Проверяем, что это закрытие позиции (reduceOnly=True)
                if exec_data.get('reduceOnly', False):
                    close_info['close_price'] = float(exec_data['execPrice'])
                    close_info['qty'] = float(exec_data['execQty'])
                    close_info['side'] = exec_data['side']
                    close_info['order_type'] = exec_data.get('orderType', '')
                    loop.call_soon_threadsafe(close_event.set)

    private_ws.execution_stream(symbol=symbol, callback=handle_execution_message)

    # Ожидание закрытия позиции или принудительного завершения
    try:
        await asyncio.wait_for(close_event.wait(), timeout=3600)  # Максимум 1 час
    except asyncio.TimeoutError:
        logger.info(f"[StrongStrategy] Таймаут ожидания закрытия позиции для {symbol}")
        position_check_task.cancel()
        price_ws_task.cancel()
        log_task.cancel()
        private_ws.exit()
        position_monitor.stop_monitoring(symbol)
        position_monitor.remove_position(symbol)
        return

    # Отменяем все задачи
    position_check_task.cancel()
    log_task.cancel()
    price_ws_task.cancel()
    private_ws.exit()
    
    # Останавливаем мониторинг позиции
    position_monitor.stop_monitoring(symbol)
    position_monitor.remove_position(symbol)

    # --- Расчет реального результата сделки ---
    if 'close_price' in close_info:
        close_price = close_info['close_price']
        avg_entry = (entry_price_1 * qty1 + entry_price_2 * qty2) / (qty1 + qty2)
        pnl = (avg_entry - close_price) * total_qty  # для шорта
        status = 'profit' if pnl > 0 else 'loss'
        pnl = round(pnl, 4)
        close_type = 'прибыль' if pnl > 0 else 'убыток'

        logger.info(f"STRONG SHORT сделка завершена. Закрытие по цене: {close_price}. Сделка закрыта в {close_type} на {pnl} USDT.")
        await send_message_to_telegram(
            f"STRONG SHORT сделка завершена.\nЗакрытие по цене: {close_price}\nСделка закрыта в {close_type} на {pnl} USDT.",
            chat_ids, TELEGRAM_BOT_TOKEN
        )
        await save_completed_transaction({
            'symbol': symbol,
            'entry_price_1': entry_price_1,
            'entry_price_2': entry_price_2,
            'qty1': qty1,
            'qty2': qty2,
            'total_qty': total_qty,
            'close_price': close_price,
            'status': status,
            'pnl': pnl,
            'strategy_type': 'strong_short',
            'timestamp': time.time()
        })
    else:
        logger.info(f"STRONG SHORT сделка {symbol} завершена принудительно")

# Алиас для обратной совместимости
async def short_strategy(symbol):
    """Алиас для обратной совместимости"""
    return await strong_short_strategy(symbol)

if __name__ == "__main__":
    symbol = TRADE_SYMBOL.upper()
    asyncio.run(strong_short_strategy(symbol))
