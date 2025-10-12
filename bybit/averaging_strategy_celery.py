"""
Стратегия шорт-позиций с усреднением для работы через Celery
Адаптированная версия для приема сигналов через вебхуки
"""
from pybit.unified_trading import WebSocket, HTTP
from time import sleep
import asyncio
from typing import Optional, Dict, Any
from config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET, TELEGRAM_BOT_TOKEN
from database import get_all_subscribed_users
from utils.send_tg_message import (
    notify_position_opened,
    notify_averaging_order_placed,
    notify_averaging_executed,
    notify_take_profit_reached,
    notify_breakeven_moved,
    notify_position_closed,
    notify_stop_loss_triggered,
    notify_strategy_error
)
from logger_config import setup_logger

logger = setup_logger(__name__)

# Настройки по умолчанию для стратегии
DEFAULT_USDT_AMOUNT = 100
DEFAULT_AVERAGING_PERCENT = 10.0
DEFAULT_INITIAL_TP_PERCENT = 3.0
DEFAULT_BREAKEVEN_STEP = 2.0
DEFAULT_STOP_LOSS_PERCENT = 15.0


class ShortAveragingStrategyCelery:
    """Стратегия шорт-позиций с усреднением для работы через Celery"""
    
    def __init__(
        self,
        symbol: str,
        usdt_amount: float = DEFAULT_USDT_AMOUNT,
        averaging_percent: float = DEFAULT_AVERAGING_PERCENT,
        initial_tp_percent: float = DEFAULT_INITIAL_TP_PERCENT,
        breakeven_step: float = DEFAULT_BREAKEVEN_STEP,
        stop_loss_percent: float = DEFAULT_STOP_LOSS_PERCENT,
        use_demo: bool = True
    ):
        """
        Инициализация стратегии
        
        Args:
            symbol: Торговая пара (например, "BTCUSDT")
            usdt_amount: Сумма в USDT для открытия позиции
            averaging_percent: Процент для усреднения (по умолчанию 10%)
            initial_tp_percent: Начальный тейк-профит (по умолчанию 3%)
            breakeven_step: Шаг перемещения безубытка (по умолчанию 2%)
            stop_loss_percent: Стоп-лосс после усреднения (по умолчанию 15%)
            use_demo: Использовать демо-счет
        """
        self.symbol = symbol.upper()
        self.usdt_amount = usdt_amount
        self.averaging_percent = averaging_percent
        self.initial_tp_percent = initial_tp_percent
        self.breakeven_step = breakeven_step
        self.stop_loss_percent = stop_loss_percent
        self.use_demo = use_demo
        
        # Инициализация сессии
        # Выбираем ключи в зависимости от режима
        api_key = DEMO_API_KEY if use_demo else API_KEY
        api_secret = DEMO_API_SECRET if use_demo else API_SECRET
        
        self.session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret,
            demo=use_demo
        )
        
        # Получаем информацию о символе
        self.qty_precision = None
        self.min_qty = None
        self.max_qty = None
        self._load_symbol_info()
        
        # Состояние позиции
        self.position_qty = 0
        self.entry_price = None
        self.averaged_price = None
        self.is_averaged = False
        self.averaging_order_id = None
        
        # Состояние тейк-профита и безубытка
        self.tp_price = None
        self.breakeven_price = None
        self.best_profit_percent = 0
        
        # Флаги состояния
        self.position_opened = False
        self.stop_loss_price = None
        
        # Счетчик попыток открытия
        self.open_attempts = 0
        self.max_open_attempts = 5
        self.failed_to_open = False
        self.last_error = None
        
        # WebSocket для мониторинга цены
        self.ws = None
        self.should_stop = False
        
        logger.info(f"[{self.symbol}] Стратегия инициализирована")

    def _load_symbol_info(self):
        """Загружает информацию о символе и правилах торговли"""
        try:
            response = self.session.get_instruments_info(
                category="linear",
                symbol=self.symbol
            )
            
            if response.get('retCode') == 0:
                instruments = response.get('result', {}).get('list', [])
                if len(instruments) > 0:
                    instrument = instruments[0]
                    lot_size_filter = instrument.get('lotSizeFilter', {})
                    
                    qty_step = float(lot_size_filter.get('qtyStep', '0.01'))
                    self.min_qty = float(lot_size_filter.get('minOrderQty', '0.01'))
                    self.max_qty = float(lot_size_filter.get('maxOrderQty', '1000000'))
                    
                    self.qty_precision = len(str(qty_step).rstrip('0').split('.')[-1])
                    
                    logger.info(
                        f"[{self.symbol}] Информация о символе: "
                        f"qty_step={qty_step}, precision={self.qty_precision}, "
                        f"min={self.min_qty}, max={self.max_qty}"
                    )
                else:
                    logger.warning(f"[{self.symbol}] Символ не найден, используем значения по умолчанию")
                    self.qty_precision = 3
                    self.min_qty = 0.001
                    self.max_qty = 1000000
            else:
                logger.warning(
                    f"[{self.symbol}] Ошибка получения информации: {response.get('retMsg')}"
                )
                self.qty_precision = 3
                self.min_qty = 0.001
                self.max_qty = 1000000
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при загрузке информации: {e}")
            self.qty_precision = 3
            self.min_qty = 0.001
            self.max_qty = 1000000

    def calculate_qty(self, price: float) -> float:
        """Рассчитывает количество актива для покупки на заданную сумму USDT"""
        qty = self.usdt_amount / price
        
        if self.qty_precision is not None:
            qty = round(qty, self.qty_precision)
        else:
            qty = round(qty, 3)
        
        if self.min_qty and qty < self.min_qty:
            logger.warning(
                f"[{self.symbol}] Qty {qty} < min {self.min_qty}, используем минимальное"
            )
            qty = self.min_qty
        
        if self.max_qty and qty > self.max_qty:
            logger.warning(
                f"[{self.symbol}] Qty {qty} > max {self.max_qty}, используем максимальное"
            )
            qty = self.max_qty
        
        return qty

    def check_position_exists(self) -> bool:
        """Проверяет существование открытой позиции на бирже"""
        try:
            response = self.session.get_positions(
                category="linear",
                symbol=self.symbol
            )
            
            if response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                for pos in positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        return True
            return False
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка проверки позиции: {e}")
            return False

    async def open_short_position(self, current_price: float) -> bool:
        """Открывает шорт-позицию с повторными попытками"""
        if self.open_attempts >= self.max_open_attempts:
            if not self.failed_to_open:
                self.failed_to_open = True
                error_msg = (
                    f"Превышено максимальное количество попыток открытия позиции: "
                    f"{self.max_open_attempts}. Последняя ошибка: {self.last_error}"
                )
                logger.error(f"[{self.symbol}] {error_msg}")
                
                # Уведомляем об ошибке
                try:
                    chat_ids = await get_all_subscribed_users()
                    await notify_strategy_error(
                        chat_ids, TELEGRAM_BOT_TOKEN, self.symbol, 
                        error_msg, "SHORT_AVERAGING"
                    )
                except Exception as e:
                    logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
            return False
        
        try:
            self.open_attempts += 1
            qty = self.calculate_qty(current_price)
            
            logger.info(
                f"[{self.symbol}] Попытка #{self.open_attempts}/{self.max_open_attempts} - "
                f"Открываем ШОРТ. Цена: {current_price:.6f}, Qty: {qty}, Сумма: {self.usdt_amount} USDT"
            )
            
            # Открываем шорт-позицию
            order = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Sell",
                orderType="Market",
                qty=qty,
            )
            
            if order.get('retCode') == 0:
                self.entry_price = current_price
                self.position_qty = qty
                self.position_opened = True
                
                # Рассчитываем цену тейк-профита (для шорта это НИЖЕ)
                self.tp_price = self.entry_price * (1 - self.initial_tp_percent / 100)
                
                logger.info(
                    f"[{self.symbol}] ШОРТ позиция открыта! "
                    f"Entry: {self.entry_price:.6f}, TP: {self.tp_price:.6f}"
                )
                
                # Отправляем уведомление об открытии позиции
                try:
                    chat_ids = await get_all_subscribed_users()
                    await notify_position_opened(
                        chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                        self.entry_price, self.position_qty, self.usdt_amount,
                        self.tp_price, self.initial_tp_percent, "SHORT"
                    )
                except Exception as e:
                    logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
                
                # Выставляем лимитный ордер на усреднение
                await self.place_averaging_order()
                
                return True
            else:
                error_msg = order.get('retMsg', 'Неизвестная ошибка')
                self.last_error = error_msg
                logger.error(
                    f"[{self.symbol}] Ошибка открытия позиции "
                    f"(попытка {self.open_attempts}/{self.max_open_attempts}): {error_msg}"
                )
                return False
                
        except Exception as e:
            self.last_error = str(e)
            logger.error(
                f"[{self.symbol}] Исключение при открытии позиции "
                f"(попытка {self.open_attempts}/{self.max_open_attempts}): {e}"
            )
            return False

    async def place_averaging_order(self) -> bool:
        """Выставляет лимитный ордер на усреднение"""
        try:
            # Для шорта усреднение происходит ВЫШЕ (+10%)
            averaging_price = self.entry_price * (1 + self.averaging_percent / 100)
            qty = self.calculate_qty(averaging_price)
            
            logger.info(
                f"[{self.symbol}] Выставляем лимитный ордер на усреднение: "
                f"цена={averaging_price:.6f} (+{self.averaging_percent}%), qty={qty}"
            )
            
            order = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Sell",
                orderType="Limit",
                qty=qty,
                price=averaging_price,
            )
            
            if order.get('retCode') == 0:
                self.averaging_order_id = order.get('result', {}).get('orderId')
                logger.info(f"[{self.symbol}] Лимитный ордер выставлен! ID: {self.averaging_order_id}")
                
                # Отправляем уведомление
                try:
                    chat_ids = await get_all_subscribed_users()
                    await notify_averaging_order_placed(
                        chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                        averaging_price, self.averaging_percent, qty
                    )
                except Exception as e:
                    logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
                
                return True
            else:
                logger.error(
                    f"[{self.symbol}] Ошибка выставления ордера: "
                    f"{order.get('retMsg', 'Неизвестная ошибка')}"
                )
                return False
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при выставлении ордера: {e}")
            return False

    def check_averaging_order_filled(self) -> bool:
        """Проверяет, был ли исполнен ордер на усреднение"""
        try:
            if not self.averaging_order_id:
                return False
                
            response = self.session.get_open_orders(
                category="linear",
                symbol=self.symbol,
                orderId=self.averaging_order_id
            )
            
            if response.get('retCode') == 0:
                orders = response.get('result', {}).get('list', [])
                if len(orders) == 0:
                    # Проверяем историю
                    history = self.session.get_order_history(
                        category="linear",
                        symbol=self.symbol,
                        orderId=self.averaging_order_id
                    )
                    
                    if history.get('retCode') == 0:
                        orders_hist = history.get('result', {}).get('list', [])
                        if len(orders_hist) > 0:
                            order_status = orders_hist[0].get('orderStatus')
                            if order_status == 'Filled':
                                return True
            return False
            
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка проверки ордера: {e}")
            return False

    async def apply_averaging(self, current_price: float) -> bool:
        """Применяет логику после усреднения"""
        try:
            logger.info(f"[{self.symbol}] Усреднение сработало!")
            
            # Рассчитываем усредненную цену
            averaging_price = self.entry_price * (1 + self.averaging_percent / 100)
            new_qty = self.calculate_qty(averaging_price)
            
            total_qty = self.position_qty + new_qty
            self.averaged_price = (
                self.entry_price * self.position_qty + averaging_price * new_qty
            ) / total_qty
            self.position_qty = total_qty
            self.is_averaged = True
            
            # Устанавливаем стоп-лосс (для шорта это ВЫШЕ усредненной цены)
            self.stop_loss_price = self.averaged_price * (1 + self.stop_loss_percent / 100)
            
            # Новый тейк-профит от усредненной цены
            self.tp_price = self.averaged_price * (1 - self.initial_tp_percent / 100)
            self.best_profit_percent = 0
            self.breakeven_price = None
            
            logger.info(
                f"[{self.symbol}] Усредненная цена: {self.averaged_price:.6f}, "
                f"SL: {self.stop_loss_price:.6f}, TP: {self.tp_price:.6f}, "
                f"Qty: {self.position_qty}"
            )
            
            # Отправляем уведомление
            try:
                chat_ids = await get_all_subscribed_users()
                await notify_averaging_executed(
                    chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                    self.averaged_price, self.position_qty,
                    self.tp_price, self.initial_tp_percent,
                    self.stop_loss_price, self.stop_loss_percent
                )
            except Exception as e:
                logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка применения усреднения: {e}")
            return False

    async def update(self, current_price: float) -> Optional[str]:
        """Обновляет состояние стратегии на основе текущей цены"""
        
        if not self.position_opened:
            return None
        
        # Проверяем существование позиции на бирже
        if not self.check_position_exists():
            logger.warning(f"[{self.symbol}] Позиция закрыта вручную или не существует!")
            return "STOP"
        
        # Определяем базовую цену для расчетов
        base_price = self.averaged_price if self.is_averaged else self.entry_price
        
        # Рассчитываем текущую прибыль для шорта
        profit_percent = (base_price - current_price) / base_price * 100
        
        # Проверяем стоп-лосс (только после усреднения)
        if self.is_averaged and self.stop_loss_price:
            if current_price >= self.stop_loss_price:
                logger.warning(
                    f"[{self.symbol}] Стоп-лосс сработал! "
                    f"Цена: {current_price:.6f} >= {self.stop_loss_price:.6f}"
                )
                
                # Уведомляем о срабатывании стоп-лосса
                try:
                    chat_ids = await get_all_subscribed_users()
                    await notify_stop_loss_triggered(
                        chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                        current_price, self.stop_loss_price
                    )
                except Exception as e:
                    logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
                
                return "CLOSE"
        
        # Проверяем, был ли исполнен ордер на усреднение
        if not self.is_averaged and self.check_averaging_order_filled():
            await self.apply_averaging(current_price)
        
        # Логика тейк-профита и безубытка
        if profit_percent >= self.initial_tp_percent:
            if not self.breakeven_price:
                # Первый раз достигли TP
                self.breakeven_price = base_price * (1 - self.initial_tp_percent / 100)
                self.best_profit_percent = profit_percent
                logger.info(
                    f"[{self.symbol}] Достигнут TP {self.initial_tp_percent}%! "
                    f"Безубыток: {self.breakeven_price:.6f}"
                )
                
                # Уведомляем о достижении TP
                try:
                    chat_ids = await get_all_subscribed_users()
                    await notify_take_profit_reached(
                        chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                        current_price, profit_percent, self.breakeven_price
                    )
                except Exception as e:
                    logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
            else:
                # Проверяем шаг в 2%
                steps_passed = int((profit_percent - self.initial_tp_percent) / self.breakeven_step)
                target_breakeven_percent = self.initial_tp_percent + steps_passed * self.breakeven_step
                new_breakeven = base_price * (1 - target_breakeven_percent / 100)
                
                if new_breakeven < self.breakeven_price:
                    old_breakeven = self.breakeven_price
                    self.breakeven_price = new_breakeven
                    self.best_profit_percent = profit_percent
                    logger.info(
                        f"[{self.symbol}] Безубыток перемещен с {old_breakeven:.6f} на "
                        f"{self.breakeven_price:.6f} ({target_breakeven_percent:.1f}%)"
                    )
                    
                    # Уведомляем о перемещении безубытка
                    try:
                        chat_ids = await get_all_subscribed_users()
                        await notify_breakeven_moved(
                            chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                            self.breakeven_price, target_breakeven_percent, profit_percent
                        )
                    except Exception as e:
                        logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
        
        # Проверяем срабатывание безубытка
        if self.breakeven_price and current_price >= self.breakeven_price:
            logger.info(
                f"[{self.symbol}] Безубыток сработал! "
                f"Цена: {current_price:.6f} >= {self.breakeven_price:.6f}"
            )
            return "CLOSE"
        
        return None

    async def cancel_averaging_order(self) -> bool:
        """Отменяет лимитный ордер на усреднение с повторными попытками"""
        if not self.averaging_order_id:
            return True
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"[{self.symbol}] Попытка {attempt}/{max_attempts} отменить лимитный ордер"
                )
                response = self.session.cancel_order(
                    category="linear",
                    symbol=self.symbol,
                    orderId=self.averaging_order_id
                )
                
                if response.get('retCode') == 0:
                    logger.info(f"[{self.symbol}] Лимитный ордер успешно отменен")
                    return True
                else:
                    error_msg = response.get('retMsg', 'Неизвестная ошибка')
                    if 'not exists' in error_msg.lower() or 'not found' in error_msg.lower():
                        logger.info(f"[{self.symbol}] Лимитный ордер уже не существует")
                        return True
                    logger.warning(f"[{self.symbol}] Попытка {attempt}: {error_msg}")
                    
            except Exception as e:
                error_str = str(e)
                if 'not exists' in error_str.lower() or 'not found' in error_str.lower():
                    logger.info(f"[{self.symbol}] Лимитный ордер уже не существует")
                    return True
                logger.warning(f"[{self.symbol}] Исключение при попытке {attempt}: {e}")
            
            if attempt < max_attempts:
                await asyncio.sleep(0.5)
        
        return False

    async def close_position(self) -> bool:
        """Закрывает позицию"""
        try:
            logger.info(f"[{self.symbol}] Закрываем позицию...")
            
            # Получаем текущую цену
            response = self.session.get_tickers(
                category="linear",
                symbol=self.symbol
            )
            current_price = None
            if response.get('retCode') == 0:
                tickers = response.get('result', {}).get('list', [])
                if len(tickers) > 0:
                    current_price = float(tickers[0].get('lastPrice', 0))
            
            # Отменяем ордер на усреднение если он еще активен
            if not self.is_averaged and self.averaging_order_id:
                await self.cancel_averaging_order()
            
            # Закрываем позицию (для закрытия шорта нужен Buy)
            order = self.session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Buy",
                orderType="Market",
                qty=self.position_qty,
            )
            
            if order.get('retCode') == 0:
                logger.info(f"[{self.symbol}] Позиция успешно закрыта!")
                
                # Рассчитываем прибыль/убыток
                base_price = self.averaged_price if self.is_averaged else self.entry_price
                profit_percent = None
                profit_usdt = None
                
                if current_price and base_price:
                    profit_percent = (base_price - current_price) / base_price * 100
                    profit_usdt = (base_price - current_price) * self.position_qty
                
                # Определяем причину закрытия
                close_reason = "BREAKEVEN"
                if self.is_averaged and self.stop_loss_price and current_price:
                    if current_price >= self.stop_loss_price:
                        close_reason = "STOP_LOSS"
                
                # Отправляем уведомление о закрытии
                try:
                    chat_ids = await get_all_subscribed_users()
                    await notify_position_closed(
                        chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                        close_reason, base_price, current_price or 0,
                        self.position_qty, profit_percent, profit_usdt,
                        self.is_averaged
                    )
                except Exception as e:
                    logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {e}")
                
                return True
            else:
                error_msg = order.get('retMsg', 'Неизвестная ошибка')
                logger.error(f"[{self.symbol}] Ошибка закрытия позиции: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Исключение при закрытии позиции: {e}")
            return False

    def handle_message(self, message):
        """Обработчик сообщений из WebSocket"""
        try:
            if 'data' in message:
                data = message['data']
                current_price = float(data.get('lastPrice', 0))
                
                if current_price <= 0:
                    return
                
                # Автоматическое открытие позиции (если не открыта)
                if not self.position_opened and not self.failed_to_open:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    success = loop.run_until_complete(self.open_short_position(current_price))
                    loop.close()
                    
                    if not success and self.failed_to_open:
                        self.should_stop = True
                    return
                
                # Обновляем стратегию
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                action = loop.run_until_complete(self.update(current_price))
                loop.close()
                
                if action == "CLOSE":
                    logger.info(f"[{self.symbol}] Условие закрытия сработало!")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.close_position())
                    loop.close()
                    self.should_stop = True
                    
                elif action == "STOP":
                    logger.warning(f"[{self.symbol}] Алгоритм остановлен (позиция закрыта вручную)")
                    self.should_stop = True
                
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка обработки сообщения: {e}")

    async def run(self):
        """Запускает стратегию через WebSocket"""
        try:
            logger.info(f"[{self.symbol}] Запуск стратегии SHORT с усреднением")
            logger.info(
                f"[{self.symbol}] Параметры: USDT={self.usdt_amount}, "
                f"Averaging={self.averaging_percent}%, TP={self.initial_tp_percent}%, "
                f"BE Step={self.breakeven_step}%, SL={self.stop_loss_percent}%"
            )
            
            # Инициализируем WebSocket
            self.ws = WebSocket(testnet=False, channel_type="linear")
            
            # Запускаем подписку на тикер
            self.ws.ticker_stream(self.symbol, self.handle_message)
            
            # Ждем остановки
            while not self.should_stop:
                await asyncio.sleep(1)
            
            logger.info(f"[{self.symbol}] Стратегия завершена")
            
        except Exception as e:
            logger.error(f"[{self.symbol}] Ошибка выполнения стратегии: {e}")
            
            # Уведомляем об ошибке
            try:
                chat_ids = await get_all_subscribed_users()
                await notify_strategy_error(
                    chat_ids, TELEGRAM_BOT_TOKEN, self.symbol,
                    str(e), "SHORT_AVERAGING"
                )
            except Exception as notify_error:
                logger.error(f"[{self.symbol}] Ошибка отправки уведомления: {notify_error}")
            
            raise


async def run_short_averaging_strategy(
    symbol: str,
    usdt_amount: float = DEFAULT_USDT_AMOUNT,
    averaging_percent: float = DEFAULT_AVERAGING_PERCENT,
    initial_tp_percent: float = DEFAULT_INITIAL_TP_PERCENT,
    breakeven_step: float = DEFAULT_BREAKEVEN_STEP,
    stop_loss_percent: float = DEFAULT_STOP_LOSS_PERCENT,
    use_demo: bool = True
):
    """
    Запускает стратегию шорт с усреднением
    
    Args:
        symbol: Торговый символ
        usdt_amount: Сумма в USDT
        averaging_percent: Процент усреднения
        initial_tp_percent: Начальный тейк-профит
        breakeven_step: Шаг безубытка
        stop_loss_percent: Стоп-лосс
        use_demo: Использовать демо-счет
    """
    strategy = ShortAveragingStrategyCelery(
        symbol=symbol,
        usdt_amount=usdt_amount,
        averaging_percent=averaging_percent,
        initial_tp_percent=initial_tp_percent,
        breakeven_step=breakeven_step,
        stop_loss_percent=stop_loss_percent,
        use_demo=use_demo
    )
    
    await strategy.run()

