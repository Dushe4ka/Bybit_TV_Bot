import asyncio
import time
from pybit.unified_trading import HTTP, WebSocket
from utils.send_tg_message import send_message_to_telegram
from logger_config import setup_logger
from config import API_KEY, API_SECRET, TELEGRAM_BOT_TOKEN
from database import get_all_subscribed_users, save_completed_transaction

# Настраиваем логгер
logger = setup_logger(__name__)

# --- Глобальные настройки ---
key = API_KEY
secret = API_SECRET

if not key or not secret:
    logger.error("API_KEY или API_SECRET не заданы. Проверьте файл .env.")
    exit(1)

# Создаем одну сессию для всего скрипта
session = HTTP(api_key=key, api_secret=secret, testnet=False, recv_window=60000)


# --- Вспомогательные функции для работы с API ---

def get_instrument_info(symbol):
    """Получает полную информацию об инструменте (тикеры, шаги и т.д.)."""
    try:
        response = session.get_instruments_info(category="linear", symbol=symbol)
        if response.get("retCode") == 0:
            return response.get("result", {}).get("list", [{}])[0]
    except Exception as e:
        logger.error(f"Ошибка при получении информации об инструменте для {symbol}: {e}")
    return {}

def get_qty_limits(instrument_info):
    """Извлекает минимальное значение и шаг для количества (qty)."""
    lot_size_filter = instrument_info.get("lotSizeFilter", {})
    min_qty = float(lot_size_filter.get("minOrderQty", "1"))
    step_size = float(lot_size_filter.get("qtyStep", "1"))
    return min_qty, step_size

def get_price_tick(instrument_info):
    """Извлекает шаг цены (tick size) для округления."""
    price_filter = instrument_info.get("priceFilter", {})
    tick_size = float(price_filter.get("tickSize", "0.0001"))
    return tick_size

def round_qty(qty, step_size):
    """Округляет количество (qty) до разрешенного биржей шага."""
    if 'e' in str(step_size): # Обработка научной нотации (e.g., 1e-5)
        precision = abs(int(str(step_size).split('e-')[1]))
    else:
        precision = len(str(step_size).split('.')[1]) if '.' in str(step_size) else 0
    return round(qty - (qty % step_size), precision)

async def open_short(symbol, dollar_value, chat_ids, instrument_info):
    """Открывает рыночный шорт-ордер на заданную сумму в долларах."""
    try:
        response = session.get_tickers(category="linear", symbol=symbol)
        entry_price = float(response['result']['list'][0]['lastPrice'])
        if entry_price <= 0:
            raise ValueError("Не удалось получить корректную цену")
    except Exception as e:
        logger.error(f"Не удалось получить цену для открытия позиции {symbol}: {e}")
        return None

    min_qty, step_size = get_qty_limits(instrument_info)
    qty = dollar_value / entry_price
    
    # Округляем до шага qty
    qty = round_qty(qty, step_size)
    if qty < min_qty:
        qty = min_qty
        logger.info(f"Расчетное qty ({dollar_value / entry_price}) меньше минимального. Установлено минимальное qty: {qty}")

    order_value = qty * entry_price
    if order_value < 5.0: # Минимальная стоимость ордера на Bybit ~5 USDT
        logger.warning(f"Стоимость ордера ({order_value:.2f} USDT) меньше 5 USDT. Пытаемся увеличить qty.")
        qty = round_qty(5.0 / entry_price, step_size) + step_size # Увеличиваем до минимально возможного
        logger.info(f"Qty автоматически увеличено до {qty} для соответствия минимальной стоимости ордера.")
        await send_message_to_telegram(
            f"Qty автоматически увеличено до {qty} для соответствия минимальной стоимости ордера 5 USDT.",
            chat_ids, TELEGRAM_BOT_TOKEN
        )

    try:
        response = session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=str(qty),
        )
        if response.get("retCode") == 0:
            logger.info(f"✅ Открыта шорт-позиция {symbol} qty={qty} по ~цене {entry_price}")
            await send_message_to_telegram(f"✅ Открыта шорт-позиция {symbol} qty={qty} по ~цене {entry_price}", chat_ids, TELEGRAM_BOT_TOKEN)
            # Ждем немного, чтобы ордер исполнился и получаем точную цену входа
            await asyncio.sleep(2)
            pos_info = session.get_positions(category="linear", symbol=symbol)
            actual_entry_price = float(pos_info['result']['list'][0]['avgPrice'])
            return actual_entry_price, qty
        else:
            raise Exception(response.get('retMsg'))
    except Exception as e:
        logger.error(f"❌ Ошибка открытия позиции: {e}")
        await send_message_to_telegram(f"❌ Ошибка открытия позиции: {e}", chat_ids, TELEGRAM_BOT_TOKEN)
        return None

async def set_take_profit(symbol, qty, price, tick_size, chat_ids):
    """Устанавливает лимитный ордер для фиксации прибыли."""
    # Округляем цену тейк-профита до правильного шага
    price_rounded = round(round(price / tick_size) * tick_size, 8)
    try:
        response = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy",
            orderType="Limit",
            qty=str(qty),
            price=str(price_rounded),
            reduceOnly=True
        )
        if response.get("retCode") == 0:
            logger.info(f"✅ Тейк-профит установлен на {price_rounded}")
            await send_message_to_telegram(f"✅ Тейк-профит установлен на {price_rounded}", chat_ids, TELEGRAM_BOT_TOKEN)
        else:
            raise Exception(response.get('retMsg'))
    except Exception as e:
        logger.error(f"❌ Ошибка установки тейк-профита: {e}")
        await send_message_to_telegram(f"❌ Ошибка установки тейк-профита: {e}", chat_ids, TELEGRAM_BOT_TOKEN)

async def set_stop_loss(symbol, qty, stop_price, tick_size, chat_ids):
    """Устанавливает рыночный стоп-ордер для ограничения убытков."""
    # Цена триггера также должна быть округлена
    stop_price_rounded = round(round(stop_price / tick_size) * tick_size, 8)
    try:
        response = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy",
            orderType="Market", # Исполнение по рынку при срабатывании
            qty=str(qty),
            triggerPrice=str(stop_price_rounded),
            triggerDirection=1, # 1: цена растет (для стопа на шорте)
            reduceOnly=True
        )
        if response.get("retCode") == 0:
            logger.info(f"✅ Стоп-лосс установлен на {stop_price_rounded}")
            await send_message_to_telegram(f"✅ Стоп-лосс установлен на {stop_price_rounded}", chat_ids, TELEGRAM_BOT_TOKEN)
        else:
            raise Exception(response.get('retMsg'))
    except Exception as e:
        logger.error(f"❌ Ошибка установки стоп-лосса: {e}")
        await send_message_to_telegram(f"❌ Ошибка установки стоп-лосса: {e}", chat_ids, TELEGRAM_BOT_TOKEN)


# --- Основная логика стратегии ---

async def short_strategy(symbol):
    chat_ids = await get_all_subscribed_users()
    logger.info(f"🚀 Запускаем стратегию для символа {symbol}")

    instrument_info = get_instrument_info(symbol)
    if not instrument_info:
        logger.error(f"Не удалось получить информацию для {symbol}. Стратегия остановлена.")
        return
    
    tick_size = get_price_tick(instrument_info)

    # 1. Открываем первую позицию
    logger.info("Открываем первую шорт-позицию на $5")
    entry1 = await open_short(symbol, 5, chat_ids, instrument_info)
    if not entry1:
        return
    entry_price_1, qty1 = entry1
    
    averaging_price = entry_price_1 * 1.2
    await send_message_to_telegram(f"⏳ Ожидание усреднения: если цена вырастет до {averaging_price:.4f}", chat_ids, TELEGRAM_BOT_TOKEN)

    # 2. Мониторинг цены для усреднения с помощью Queue
    price_queue = asyncio.Queue()

    def price_callback(msg):
        for ticker in msg.get('data', []):
            if ticker.get('symbol') == symbol:
                last_price = float(ticker.get('lastPrice'))
                try:
                    price_queue.put_nowait(last_price)
                except asyncio.QueueFull:
                    pass

    ws_price = WebSocket(testnet=False, channel_type="linear")
    ws_price.ticker_stream(callback=price_callback, symbol=symbol)
    logger.info("✅ Запущен WebSocket для мониторинга цены усреднения.")

    last_logged_time = time.time()
    usrednenie_done = False
    current_price = entry_price_1
    
    try:
        while not usrednenie_done:
            try:
                current_price = await asyncio.wait_for(price_queue.get(), timeout=20.0)
                if time.time() - last_logged_time > 10.0:
                    percent_change = ((current_price - entry_price_1) / entry_price_1) * 100
                    logger.info(f"📊 Мониторинг: цена входа={entry_price_1}, текущая цена={current_price}, изменение={percent_change:.2f}%")
                    last_logged_time = time.time()
                
                if current_price >= averaging_price:
                    logger.info(f"📈 Цена достигла уровня для усреднения: {current_price}")
                    usrednenie_done = True
                    break
            except asyncio.TimeoutError:
                logger.warning("❗️ Нет данных от WebSocket в течение 20 секунд. Переподключаемся...")
                ws_price.exit()
                await asyncio.sleep(1)
                ws_price = WebSocket(testnet=False, channel_type="linear")
                ws_price.ticker_stream(callback=price_callback, symbol=symbol)
                logger.info("🔄 WebSocket для мониторинга цены перезапущен.")
    finally:
        logger.info("🛑 Остановка WebSocket для мониторинга цены.")
        ws_price.exit()

    if not usrednenie_done:
        return

    # 3. Усреднение
    await send_message_to_telegram(f"Цена выросла на 20%. Усредняем! Текущая цена: {current_price}", chat_ids, TELEGRAM_BOT_TOKEN)
    entry2 = await open_short(symbol, 5, chat_ids, instrument_info)
    if not entry2:
        return
        
    entry_price_2, qty2 = entry2
    total_qty = qty1 + qty2
    
    avg_entry_price = (entry_price_1 * qty1 + entry_price_2 * qty2) / total_qty
    
    # 4. Отменяем старые ордера и ставим новые
    session.cancel_all_orders(category="linear", symbol=symbol)
    logger.info("Отменены все предыдущие ордера для установки новых.")
    await asyncio.sleep(1)

    stop_loss_price = avg_entry_price * 1.10 # Стоп-лосс 10% от средней цены входа
    take_profit_price = avg_entry_price * 0.85 # Тейк-профит 15% от средней цены входа
    
    await set_stop_loss(symbol, total_qty, stop_loss_price, tick_size, chat_ids)
    await set_take_profit(symbol, total_qty, take_profit_price, tick_size, chat_ids)
    
    # 5. Ожидание закрытия позиции
    close_event = asyncio.Event()
    close_info = {}
    loop = asyncio.get_running_loop()
    
    def order_callback(msg):
        for exec_data in msg.get('data', []):
            if exec_data.get('symbol') == symbol and exec_data.get('execType') == 'Trade' and exec_data.get('reduceOnly'):
                logger.info(f"Получено событие о закрытии ордера: {exec_data}")
                close_info['close_price'] = float(exec_data['execPrice'])
                close_info['pnl'] = float(exec_data.get('closedPnl', 0))
                loop.call_soon_threadsafe(close_event.set)

    ws_order = WebSocket(testnet=False, channel_type="private") 
    ws_order.execution_stream(callback=order_callback) 
    logger.info("✅ Запущен WebSocket для мониторинга исполнения ордеров (TP/SL).")

    try:
        await asyncio.wait_for(close_event.wait(), timeout=86400) # Ждем сутки
    except asyncio.TimeoutError:
        logger.error("Позиция не была закрыта в течение 24 часов. Закрываем принудительно.")
        session.place_order(category="linear", symbol=symbol, side="Buy", orderType="Market", qty=str(total_qty), reduceOnly=True)
    finally:
        logger.info("🛑 Остановка WebSocket для мониторинга ордеров.")
        ws_order.exit()

    # 6. Расчет PnL и завершение
    if not close_info:
        logger.error("Не удалось получить информацию о закрытии сделки.")
        return

    close_price = close_info['close_price']
    pnl = close_info['pnl']
    status = 'profit' if pnl > 0 else 'loss'
    close_type = 'прибыль' if pnl > 0 else 'убыток'

    message = f"🏁 Сделка завершена.\nЗакрытие по цене: {close_price}\nСредняя цена входа: {avg_entry_price:.4f}\nРезультат: {close_type} на {pnl:.4f} USDT."
    logger.info(message)
    await send_message_to_telegram(message, chat_ids, TELEGRAM_BOT_TOKEN)
    
    await save_completed_transaction({
        'symbol': symbol, 'avg_entry_price': avg_entry_price, 'total_qty': total_qty,
        'close_price': close_price, 'status': status, 'pnl': pnl, 'timestamp': time.time()
    })

if __name__ == "__main__":
    # Убедитесь, что символ указан в правильном формате для Bybit (без разделителей, например, BTCUSDT)
    symbol = "Fragusdt"
    try:
        asyncio.run(short_strategy(symbol.upper()))
    except KeyboardInterrupt:
        logger.info("Программа остановлена вручную.")