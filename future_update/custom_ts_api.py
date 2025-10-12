from pybit.unified_trading import WebSocket, HTTP
from time import sleep
import json
from config import DEMO_API_KEY, DEMO_API_SECRET

session = HTTP(testnet=False, api_key=DEMO_API_KEY, api_secret=DEMO_API_SECRET, demo=True)
ws = WebSocket(testnet=False, channel_type="linear")


class TrailingStop:
    def __init__(self, symbol, position_size, activation_percent=1.0, trail_percent=0.5, initial_stop_percent=2.0):
        self.symbol = symbol
        self.position_size = position_size
        self.activation_percent = activation_percent
        self.trail_percent = trail_percent
        self.initial_stop_percent = initial_stop_percent
        self.entry_price = None
        self.best_price = None
        self.is_active = False
        self.stop_price = None
        self.position_opened = False
        self.initial_stop_price = None

    def open_position(self, current_price, side="Buy"):
        """Открывает позицию и выставляет начальный стоп-лосс"""
        try:
            # Открываем позицию
            order = session.place_order(
                category="linear",
                symbol=self.symbol,
                side=side,
                orderType="Market",
                qty=abs(self.position_size),
            )
            
            if order.get('retCode') == 0:
                self.entry_price = current_price
                self.best_price = current_price
                self.position_opened = True
                
                # Выставляем начальный стоп-лосс
                self.initial_stop_price = self.entry_price * (1 - self.initial_stop_percent / 100) if side == "Buy" else self.entry_price * (1 + self.initial_stop_percent / 100)
                
                print(f"✅ Позиция открыта! Цена входа: {self.entry_price:.2f}")
                print(f"🛡️ Начальный стоп: {self.initial_stop_price:.2f}")
                
                return True
            else:
                print(f"❌ Ошибка открытия позиции: {order.get('retMsg', 'Неизвестная ошибка')}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение при открытии позиции: {e}")
            return False

    def check_initial_stop(self, current_price):
        """Проверяет срабатывание начального стоп-лосса"""
        if not self.position_opened or self.initial_stop_price is None:
            return None
            
        # Для лонга: если цена упала ниже начального стопа
        if self.position_size > 0 and current_price <= self.initial_stop_price:
            return "Sell"
        # Для шорта: если цена поднялась выше начального стопа  
        elif self.position_size < 0 and current_price >= self.initial_stop_price:
            return "Sell"  # Для закрытия шорт позиции тоже нужен Sell
            
        return None

    def update(self, current_price, bid_price, ask_price):
        # Используем lastPrice как основную, но можем учитывать bid/ask
        # Рассчитываем PnL если позиция открыта
        if self.position_opened and self.entry_price:
            if self.position_size > 0:  # long позиция
                pnl_percent = (current_price - self.entry_price) / self.entry_price * 100
            else:  # short позиция
                pnl_percent = (self.entry_price - current_price) / self.entry_price * 100
            
            pnl_emoji = "📈" if pnl_percent >= 0 else "📉"
            print(f"💰 Last: {current_price:.2f} | Bid: {bid_price:.2f} | Ask: {ask_price:.2f} | {pnl_emoji} PnL: {pnl_percent:+.2f}%")
        else:
            print(f"💰 Last: {current_price:.2f} | Bid: {bid_price:.2f} | Ask: {ask_price:.2f}")

        # Если позиция не открыта, ничего не делаем
        if not self.position_opened:
            return None

        # Проверяем начальный стоп-лосс
        initial_stop_action = self.check_initial_stop(current_price)
        if initial_stop_action:
            print(f"🛡️ Начальный стоп-лосс сработал!")
            return initial_stop_action

        # Логика трейлинг-стопа
        if self.position_size > 0:  # long позиция
            if current_price > self.best_price:
                self.best_price = current_price

            profit_percent = (current_price - self.entry_price) / self.entry_price * 100

            if not self.is_active and profit_percent >= self.activation_percent:
                self.is_active = True
                self.stop_price = self.best_price * (1 - self.trail_percent / 100)
                print(f"🎯 Трейлинг-стоп активирован! Прибыль: {profit_percent:.2f}%")

            if self.is_active:
                new_stop = self.best_price * (1 - self.trail_percent / 100)
                if new_stop > self.stop_price:
                    self.stop_price = new_stop
                    print(f"📈 Стоп перемещен: {self.stop_price:.2f}")

                # Проверяем срабатывание по lastPrice
                if current_price <= self.stop_price:
                    return "Sell"

        elif self.position_size < 0:  # short позиция
            if current_price < self.best_price:
                self.best_price = current_price

            profit_percent = (self.entry_price - current_price) / self.entry_price * 100

            if not self.is_active and profit_percent >= self.activation_percent:
                self.is_active = True
                self.stop_price = self.best_price * (1 + self.trail_percent / 100)
                print(f"🎯 Трейлинг-стоп активирован! Прибыль: {profit_percent:.2f}%")

            if self.is_active:
                new_stop = self.best_price * (1 + self.trail_percent / 100)
                if new_stop < self.stop_price:
                    self.stop_price = new_stop
                    print(f"📉 Стоп перемещен: {self.stop_price:.2f}")

                # Проверяем срабатывание по lastPrice
                if current_price >= self.stop_price:
                    return "Sell"  # Для закрытия шорт позиции тоже нужен Sell

        return None


trailing_stop = TrailingStop("BTCUSDT", -0.001, 1.0, 0.5, 2.0)  # Добавлен начальный стоп 2%


def handle_message(message):
    try:
        if 'data' in message:
            data = message['data']

            # Извлекаем ключевые цены
            last_price = float(data.get('lastPrice', 0))
            bid_price = float(data.get('bid1Price', 0))
            ask_price = float(data.get('ask1Price', 0))

            # Дополнительная информация для анализа
            change_24h = float(data.get('price24hPcnt', 0)) * 100  # в процентах
            high_24h = float(data.get('highPrice24h', 0))
            low_24h = float(data.get('lowPrice24h', 0))

            # Выводим полезную информацию (можно убрать в продакшене)
            print(f"📊 Изменение 24h: {change_24h:+.2f}% | Диапазон: {low_24h:.2f}-{high_24h:.2f}")

            # Автоматическое открытие позиции (если не открыта)
            if not trailing_stop.position_opened:
                print("🚀 Открываем позицию...")
                # Определяем сторону позиции на основе знака position_size
                side = "Buy" if trailing_stop.position_size > 0 else "Sell"
                if trailing_stop.open_position(last_price, side):
                    print(f"✅ Позиция успешно открыта! Сторона: {side}")
                else:
                    print("❌ Не удалось открыть позицию")
                    return

            # Обновляем трейлинг-стоп
            action = trailing_stop.update(last_price, bid_price, ask_price)

            if action:
                print(f"🚨 СТОП СРАБОТАЛ!")
                print(f"💸 Last: {last_price:.2f} | Стоп: {trailing_stop.stop_price or trailing_stop.initial_stop_price:.2f}")

                try:
                    order = session.place_order(
                        category="linear",
                        symbol="BTCUSDT",
                        side=action,
                        orderType="Market",
                        qty=abs(trailing_stop.position_size),
                    )
                    print(f"✅ Позиция закрыта! Причина: {'Трейлинг-стоп' if trailing_stop.is_active else 'Начальный стоп'}")
                    
                    # Сбрасываем состояние для новой позиции
                    trailing_stop.position_opened = False
                    trailing_stop.entry_price = None
                    trailing_stop.best_price = None
                    trailing_stop.is_active = False
                    trailing_stop.stop_price = None
                    trailing_stop.initial_stop_price = None
                    
                except Exception as e:
                    print(f"❌ Ошибка закрытия: {e}")

            # Выводим отладочную информацию раз в 10 сообщений
            if hasattr(handle_message, 'counter'):
                handle_message.counter += 1
            else:
                handle_message.counter = 1

            if handle_message.counter % 10 == 0:
                status_info = f"🔧 Статус: Позиция={'Открыта' if trailing_stop.position_opened else 'Закрыта'}"
                if trailing_stop.position_opened:
                    # Рассчитываем текущую прибыль/убыток
                    if trailing_stop.position_size > 0:  # long позиция
                        current_pnl_percent = (last_price - trailing_stop.entry_price) / trailing_stop.entry_price * 100
                    else:  # short позиция
                        current_pnl_percent = (trailing_stop.entry_price - last_price) / trailing_stop.entry_price * 100
                    
                    pnl_emoji = "📈" if current_pnl_percent >= 0 else "📉"
                    status_info += f", {pnl_emoji} PnL: {current_pnl_percent:+.2f}%"
                    status_info += f", Трейлинг={'Активен' if trailing_stop.is_active else 'Неактивен'}"
                    status_info += f", Лучшая цена={trailing_stop.best_price:.2f}"
                    if trailing_stop.is_active:
                        status_info += f", Трейлинг-стоп={trailing_stop.stop_price:.2f}"
                    else:
                        status_info += f", Начальный стоп={trailing_stop.initial_stop_price:.2f}"
                print(status_info)

    except Exception as e:
        print(f"❌ Ошибка обработки сообщения: {e}")


ws.ticker_stream("BTCUSDT", handle_message)

print("Трейлинг-стоп запущен...")
while True:
    sleep(1)