from pybit.unified_trading import WebSocket, HTTP
from time import sleep
import json
from config import DEMO_API_KEY, DEMO_API_SECRET

session = HTTP(testnet=False, api_key=DEMO_API_KEY, api_secret=DEMO_API_SECRET, demo=True)
ws = WebSocket(testnet=False, channel_type="linear")


class ShortAveragingStrategy:
    def __init__(self, symbol, usdt_amount, averaging_percent=10.0, initial_tp_percent=3.0, 
                 breakeven_step=2.0, stop_loss_percent=15.0):
        """
        Стратегия шорт-позиций с усреднением
        
        :param symbol: Торговая пара (например, "BTCUSDT")
        :param usdt_amount: Сумма в USDT для открытия позиции
        :param averaging_percent: Процент для усреднения (по умолчанию 10%)
        :param initial_tp_percent: Начальный тейк-профит (по умолчанию 3%)
        :param breakeven_step: Шаг перемещения безубытка (по умолчанию 2%)
        :param stop_loss_percent: Стоп-лосс после усреднения (по умолчанию 15%)
        """
        self.symbol = symbol.upper()
        self.usdt_amount = usdt_amount
        self.averaging_percent = averaging_percent
        self.initial_tp_percent = initial_tp_percent
        self.breakeven_step = breakeven_step
        self.stop_loss_percent = stop_loss_percent
        
        # Получаем информацию о символе и правила округления
        self.qty_precision = None
        self.min_qty = None
        self.max_qty = None
        self._load_symbol_info()
        
        # Состояние позиции
        self.position_qty = 0  # Количество актива в позиции
        self.entry_price = None  # Цена первого входа
        self.averaged_price = None  # Усредненная цена после второго входа
        self.is_averaged = False  # Флаг усреднения
        self.averaging_order_id = None  # ID лимитного ордера на усреднение
        
        # Состояние тейк-профита и безубытка
        self.tp_price = None  # Цена тейк-профита
        self.breakeven_price = None  # Текущая цена безубытка
        self.best_profit_percent = 0  # Лучший процент прибыли
        
        # Флаги состояния
        self.position_opened = False
        self.stop_loss_price = None
        
        # Счетчик попыток открытия
        self.open_attempts = 0
        self.max_open_attempts = 5
        self.failed_to_open = False
        self.last_error = None

    def _load_symbol_info(self):
        """Загружает информацию о символе и правилах торговли"""
        try:
            response = session.get_instruments_info(
                category="linear",
                symbol=self.symbol
            )
            
            if response.get('retCode') == 0:
                instruments = response.get('result', {}).get('list', [])
                if len(instruments) > 0:
                    instrument = instruments[0]
                    lot_size_filter = instrument.get('lotSizeFilter', {})
                    
                    # Получаем точность количества
                    qty_step = float(lot_size_filter.get('qtyStep', '0.01'))
                    self.min_qty = float(lot_size_filter.get('minOrderQty', '0.01'))
                    self.max_qty = float(lot_size_filter.get('maxOrderQty', '1000000'))
                    
                    # Вычисляем количество знаков после запятой
                    self.qty_precision = len(str(qty_step).rstrip('0').split('.')[-1])
                    
                    print(f"📊 Информация о символе {self.symbol}:")
                    print(f"   Шаг qty: {qty_step}")
                    print(f"   Точность: {self.qty_precision} знаков")
                    print(f"   Мин. qty: {self.min_qty}")
                    print(f"   Макс. qty: {self.max_qty}")
                else:
                    print(f"⚠️ Символ {self.symbol} не найден, используем значения по умолчанию")
                    self.qty_precision = 3
                    self.min_qty = 0.001
                    self.max_qty = 1000000
            else:
                print(f"⚠️ Ошибка получения информации о символе: {response.get('retMsg')}")
                self.qty_precision = 3
                self.min_qty = 0.001
                self.max_qty = 1000000
                
        except Exception as e:
            print(f"⚠️ Исключение при загрузке информации о символе: {e}")
            self.qty_precision = 3
            self.min_qty = 0.001
            self.max_qty = 1000000

    def calculate_qty(self, price):
        """Рассчитывает количество актива для покупки на заданную сумму USDT"""
        qty = self.usdt_amount / price
        
        # Округляем согласно правилам символа
        if self.qty_precision is not None:
            qty = round(qty, self.qty_precision)
        else:
            qty = round(qty, 3)
        
        # Проверяем минимальное и максимальное количество
        if self.min_qty and qty < self.min_qty:
            print(f"⚠️ Qty {qty} меньше минимального {self.min_qty}, используем минимальное")
            qty = self.min_qty
        
        if self.max_qty and qty > self.max_qty:
            print(f"⚠️ Qty {qty} больше максимального {self.max_qty}, используем максимальное")
            qty = self.max_qty
        
        return qty

    def check_position_exists(self):
        """Проверяет существование открытой позиции на бирже"""
        try:
            response = session.get_positions(
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
            print(f"❌ Ошибка проверки позиции: {e}")
            return False

    def open_short_position(self, current_price):
        """Открывает шорт-позицию с повторными попытками"""
        # Проверяем, не превышен ли лимит попыток
        if self.open_attempts >= self.max_open_attempts:
            if not self.failed_to_open:
                self.failed_to_open = True
                print(f"❌❌❌ КРИТИЧЕСКАЯ ОШИБКА ❌❌❌")
                print(f"🚫 Превышено максимальное количество попыток открытия позиции: {self.max_open_attempts}")
                print(f"📋 Последняя ошибка: {self.last_error}")
                print(f"💡 Возможные причины:")
                print(f"   1. Неверное название символа (должно быть в верхнем регистре)")
                print(f"   2. Символ не доступен на demo-аккаунте")
                print(f"   3. Недостаточно средств на балансе")
                print(f"   4. Символ не поддерживает шорт-позиции")
                print(f"   5. Неверное количество (qty) - проверьте правила символа")
                print(f"   6. Слишком маленькая сумма USDT для данного символа")
                print(f"🛑 Алгоритм остановлен!")
            return False
        
        try:
            self.open_attempts += 1
            qty = self.calculate_qty(current_price)
            
            print(f"🚀 Попытка #{self.open_attempts}/{self.max_open_attempts} - Открываем ШОРТ позицию...")
            print(f"💰 Сумма: {self.usdt_amount} USDT")
            print(f"📊 Цена: {current_price:.2f}")
            print(f"📈 Количество: {qty} (точность: {self.qty_precision} знаков)")
            
            # Открываем шорт-позицию
            order = session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Sell",  # Sell для открытия шорта
                orderType="Market",
                qty=qty,
            )
            
            if order.get('retCode') == 0:
                self.entry_price = current_price
                self.position_qty = qty
                self.position_opened = True
                
                # Рассчитываем цену тейк-профита (для шорта это НИЖЕ)
                self.tp_price = self.entry_price * (1 - self.initial_tp_percent / 100)
                
                print(f"✅ ШОРТ позиция открыта!")
                print(f"💵 Цена входа: {self.entry_price:.2f}")
                print(f"🎯 Тейк-профит: {self.tp_price:.2f} (-{self.initial_tp_percent}%)")
                
                # Сразу выставляем лимитный ордер на усреднение (+10% от входа для шорта это выше)
                self.place_averaging_order()
                
                return True
            else:
                error_msg = order.get('retMsg', 'Неизвестная ошибка')
                self.last_error = error_msg
                print(f"❌ Ошибка открытия позиции (попытка {self.open_attempts}/{self.max_open_attempts}): {error_msg}")
                return False
                
        except Exception as e:
            self.last_error = str(e)
            print(f"❌ Исключение при открытии позиции (попытка {self.open_attempts}/{self.max_open_attempts}): {e}")
            return False

    def place_averaging_order(self):
        """Выставляет лимитный ордер на усреднение (+10% от цены входа)"""
        try:
            # Для шорта усреднение происходит ВЫШЕ (+10%)
            averaging_price = self.entry_price * (1 + self.averaging_percent / 100)
            qty = self.calculate_qty(averaging_price)
            
            print(f"📝 Выставляем лимитный ордер на усреднение...")
            print(f"💰 Цена усреднения: {averaging_price:.2f} (+{self.averaging_percent}%)")
            print(f"📈 Количество: {qty} (округлено до {self.qty_precision} знаков)")
            
            order = session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Sell",  # Sell для увеличения шорт-позиции
                orderType="Limit",
                qty=qty,
                price=averaging_price,
            )
            
            if order.get('retCode') == 0:
                self.averaging_order_id = order.get('result', {}).get('orderId')
                print(f"✅ Лимитный ордер выставлен! ID: {self.averaging_order_id}")
                return True
            else:
                print(f"❌ Ошибка выставления ордера: {order.get('retMsg', 'Неизвестная ошибка')}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение при выставлении ордера: {e}")
            return False

    def check_averaging_order_filled(self):
        """Проверяет, был ли исполнен ордер на усреднение"""
        try:
            if not self.averaging_order_id:
                return False
                
            response = session.get_open_orders(
                category="linear",
                symbol=self.symbol,
                orderId=self.averaging_order_id
            )
            
            if response.get('retCode') == 0:
                orders = response.get('result', {}).get('list', [])
                # Если ордер не найден в открытых, значит он исполнен или отменен
                if len(orders) == 0:
                    # Проверяем историю, чтобы убедиться что он исполнен
                    history = session.get_order_history(
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
            print(f"❌ Ошибка проверки ордера: {e}")
            return False

    def apply_averaging(self, current_price):
        """Применяет логику после усреднения"""
        try:
            print(f"🎯 Усреднение сработало!")
            
            # Рассчитываем усредненную цену
            # Для шорта: (entry_price * qty1 + averaging_price * qty2) / (qty1 + qty2)
            averaging_price = self.entry_price * (1 + self.averaging_percent / 100)
            new_qty = self.calculate_qty(averaging_price)
            
            total_qty = self.position_qty + new_qty
            self.averaged_price = (self.entry_price * self.position_qty + averaging_price * new_qty) / total_qty
            self.position_qty = total_qty
            self.is_averaged = True
            
            # Устанавливаем стоп-лосс (для шорта это ВЫШЕ усредненной цены)
            self.stop_loss_price = self.averaged_price * (1 + self.stop_loss_percent / 100)
            
            # Новый тейк-профит от усредненной цены
            self.tp_price = self.averaged_price * (1 - self.initial_tp_percent / 100)
            self.best_profit_percent = 0
            self.breakeven_price = None
            
            print(f"💵 Усредненная цена: {self.averaged_price:.2f}")
            print(f"🛡️ Стоп-лосс: {self.stop_loss_price:.2f} (+{self.stop_loss_percent}%)")
            print(f"🎯 Новый тейк-профит: {self.tp_price:.2f} (-{self.initial_tp_percent}%)")
            print(f"📊 Общее количество: {self.position_qty}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка применения усреднения: {e}")
            return False

    def update(self, current_price):
        """Обновляет состояние стратегии на основе текущей цены"""
        
        # Если позиция не открыта, ничего не делаем
        if not self.position_opened:
            return None
        
        # Проверяем, существует ли позиция на бирже
        if not self.check_position_exists():
            print(f"⚠️ Позиция закрыта вручную или не существует!")
            return "STOP"
        
        # Определяем базовую цену для расчетов
        base_price = self.averaged_price if self.is_averaged else self.entry_price
        
        # Рассчитываем текущую прибыль для шорта (entry - current) / entry * 100
        profit_percent = (base_price - current_price) / base_price * 100
        
        # Выводим текущее состояние
        pnl_emoji = "📈" if profit_percent >= 0 else "📉"
        print(f"💰 Цена: {current_price:.2f} | {pnl_emoji} PnL: {profit_percent:+.2f}%")
        
        # Проверяем стоп-лосс (только после усреднения)
        if self.is_averaged and self.stop_loss_price:
            if current_price >= self.stop_loss_price:
                print(f"🛡️ Стоп-лосс сработал! Цена: {current_price:.2f} >= {self.stop_loss_price:.2f}")
                return "CLOSE"
        
        # Проверяем, был ли исполнен ордер на усреднение
        if not self.is_averaged and self.check_averaging_order_filled():
            self.apply_averaging(current_price)
        
        # Логика тейк-профита и безубытка
        if profit_percent >= self.initial_tp_percent:
            # Достигли начального тейк-профита
            if not self.breakeven_price:
                # Первый раз достигли TP - ставим безубыток НА ЭТИ ЖЕ 3%
                self.breakeven_price = base_price * (1 - self.initial_tp_percent / 100)
                self.best_profit_percent = profit_percent
                print(f"🎯 Достигнут тейк-профит {self.initial_tp_percent}%!")
                print(f"🔒 Установлен безубыток на {self.initial_tp_percent}%: {self.breakeven_price:.2f}")
            else:
                # Уже в безубытке, проверяем шаг в 2%
                # Рассчитываем на какую точку должен быть безубыток
                steps_passed = int((profit_percent - self.initial_tp_percent) / self.breakeven_step)
                target_breakeven_percent = self.initial_tp_percent + steps_passed * self.breakeven_step
                new_breakeven = base_price * (1 - target_breakeven_percent / 100)
                
                if new_breakeven < self.breakeven_price:  # Для шорта безубыток двигается ВНИЗ
                    self.breakeven_price = new_breakeven
                    self.best_profit_percent = profit_percent
                    print(f"📈 Безубыток перемещен на {target_breakeven_percent:.1f}%: {self.breakeven_price:.2f} (Текущая прибыль: {profit_percent:.2f}%)")
        
        # Проверяем срабатывание безубытка
        if self.breakeven_price and current_price >= self.breakeven_price:
            print(f"🔒 Безубыток сработал! Цена: {current_price:.2f} >= {self.breakeven_price:.2f}")
            return "CLOSE"
        
        return None

    def cancel_averaging_order(self):
        """Отменяет лимитный ордер на усреднение с повторными попытками"""
        if not self.averaging_order_id:
            return True
        
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"🔄 Попытка {attempt}/{max_attempts} отменить лимитный ордер...")
                response = session.cancel_order(
                    category="linear",
                    symbol=self.symbol,
                    orderId=self.averaging_order_id
                )
                
                if response.get('retCode') == 0:
                    print(f"✅ Лимитный ордер на усреднение успешно отменен")
                    return True
                else:
                    error_msg = response.get('retMsg', 'Неизвестная ошибка')
                    # Если ордер не существует - это тоже успех (он уже не активен)
                    if 'not exists' in error_msg.lower() or 'not found' in error_msg.lower():
                        print(f"ℹ️ Лимитный ордер уже не существует (возможно, уже отменен)")
                        return True
                    print(f"⚠️ Попытка {attempt}: {error_msg}")
                    
            except Exception as e:
                error_str = str(e)
                if 'not exists' in error_str.lower() or 'not found' in error_str.lower():
                    print(f"ℹ️ Лимитный ордер уже не существует")
                    return True
                print(f"⚠️ Исключение при попытке {attempt}: {e}")
            
            if attempt < max_attempts:
                sleep(0.5)  # Небольшая задержка между попытками
        
        # Если все попытки неудачны, проверяем существует ли ордер вообще
        print(f"⚠️ Не удалось отменить ордер после {max_attempts} попыток")
        print(f"🔍 Проверяем статус ордера на бирже...")
        
        try:
            response = session.get_open_orders(
                category="linear",
                symbol=self.symbol,
                orderId=self.averaging_order_id
            )
            
            if response.get('retCode') == 0:
                orders = response.get('result', {}).get('list', [])
                if len(orders) == 0:
                    print(f"✅ Ордер не найден в открытых - все в порядке")
                    return True
                else:
                    print(f"⚠️ ВНИМАНИЕ: Ордер все еще активен на бирже!")
                    print(f"⚠️ ID ордера: {self.averaging_order_id}")
                    print(f"⚠️ Рекомендуется отменить вручную!")
                    return False
        except Exception as e:
            print(f"⚠️ Не удалось проверить статус ордера: {e}")
            return False

    def close_position(self):
        """Закрывает позицию"""
        try:
            print(f"🚨 Закрываем позицию...")
            
            # Отменяем ордер на усреднение если он еще активен
            if not self.is_averaged and self.averaging_order_id:
                self.cancel_averaging_order()
            
            # Закрываем позицию (для закрытия шорта нужен Buy)
            order = session.place_order(
                category="linear",
                symbol=self.symbol,
                side="Buy",
                orderType="Market",
                qty=self.position_qty,
            )
            
            if order.get('retCode') == 0:
                print(f"✅ Позиция успешно закрыта!")
                return True
            else:
                print(f"❌ Ошибка закрытия позиции: {order.get('retMsg', 'Неизвестная ошибка')}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение при закрытии позиции: {e}")
            return False

    def reset(self):
        """Сбрасывает все параметры для новой сделки"""
        self.position_qty = 0
        self.entry_price = None
        self.averaged_price = None
        self.is_averaged = False
        self.averaging_order_id = None
        self.tp_price = None
        self.breakeven_price = None
        self.best_profit_percent = 0
        self.position_opened = False
        self.stop_loss_price = None
        
        # Сбрасываем счетчики попыток (на случай если хотим начать заново)
        self.open_attempts = 0
        self.failed_to_open = False
        self.last_error = None
        
        print(f"🔄 Стратегия сброшена, готова к новой сделке")


# Инициализация стратегии
# Параметры: символ, сумма в USDT, % усреднения, % TP, шаг безубытка, % SL
strategy = ShortAveragingStrategy(
    symbol="1000ratsusdt",
    usdt_amount=100,  # Пользователь указывает сумму в USDT
    averaging_percent=10.0,
    initial_tp_percent=3.0,
    breakeven_step=2.0,
    stop_loss_percent=15.0
)


def handle_message(message):
    global should_stop
    
    try:
        if 'data' in message:
            data = message['data']
            
            # Извлекаем текущую цену
            current_price = float(data.get('lastPrice', 0))
            
            # Автоматическое открытие позиции (если не открыта)
            if not strategy.position_opened and not strategy.failed_to_open:
                if strategy.open_short_position(current_price):
                    print(f"✅ ШОРТ позиция успешно открыта!")
                else:
                    # Если достигнут лимит попыток, останавливаем бота
                    if strategy.failed_to_open:
                        should_stop = True
                    return
            
            # Обновляем стратегию
            action = strategy.update(current_price)
            
            if action == "CLOSE":
                print(f"🚨 УСЛОВИЕ ЗАКРЫТИЯ СРАБОТАЛО!")
                if strategy.close_position():
                    strategy.reset()
                    # Здесь можно либо остановить бота, либо открыть новую позицию
                    # Для остановки используем глобальный флаг
                    should_stop = True
                    
            elif action == "STOP":
                print(f"⚠️ АЛГОРИТМ ОСТАНОВЛЕН (позиция закрыта вручную)")
                strategy.reset()
                should_stop = True
            
            # Выводим детальную статистику каждые 10 сообщений
            if hasattr(handle_message, 'counter'):
                handle_message.counter += 1
            else:
                handle_message.counter = 1
            
            if handle_message.counter % 10 == 0:
                status_info = f"🔧 Статус: "
                if strategy.position_opened:
                    base_price = strategy.averaged_price if strategy.is_averaged else strategy.entry_price
                    profit = (base_price - current_price) / base_price * 100
                    
                    status_info += f"Позиция ОТКРЫТА (ШОРТ)"
                    status_info += f", Усреднение={'ДА' if strategy.is_averaged else 'НЕТ'}"
                    status_info += f", PnL={profit:+.2f}%"
                    
                    if strategy.breakeven_price:
                        status_info += f", Безубыток={strategy.breakeven_price:.2f}"
                    if strategy.is_averaged and strategy.stop_loss_price:
                        status_info += f", SL={strategy.stop_loss_price:.2f}"
                else:
                    status_info += "Позиция ЗАКРЫТА"
                    
                print(status_info)
    
    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")


# Глобальный флаг для остановки
should_stop = False

# Запуск WebSocket стрима
ws.ticker_stream(strategy.symbol, handle_message)

print("=" * 60)
print("🤖 СТРАТЕГИЯ ШОРТ С УСРЕДНЕНИЕМ ЗАПУЩЕНА")
print("=" * 60)
print(f"📊 Символ: {strategy.symbol}")
print(f"💰 Сумма на сделку: {strategy.usdt_amount} USDT")
print(f"📏 Точность qty: {strategy.qty_precision} знаков (мин: {strategy.min_qty}, макс: {strategy.max_qty})")
print(f"📈 Процент усреднения: {strategy.averaging_percent}%")
print(f"🎯 Тейк-профит: {strategy.initial_tp_percent}%")
print(f"🔒 Шаг безубытка: {strategy.breakeven_step}%")
print(f"🛡️ Стоп-лосс (после усреднения): {strategy.stop_loss_percent}%")
print(f"🔄 Максимум попыток открытия: {strategy.max_open_attempts}")
print("=" * 60)

while True:
    if should_stop:
        print("🛑 Остановка алгоритма...")
        break
    sleep(1)

