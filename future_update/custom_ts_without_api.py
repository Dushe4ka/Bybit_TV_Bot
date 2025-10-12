from pybit.unified_trading import WebSocket
from time import sleep, time
import json


class PaperTrailingStop:
    def __init__(self, symbol, position_size, activation_percent=1.0, trail_percent=0.5):
        self.symbol = symbol
        self.position_size = position_size  # + для лонга, - для шорта
        self.activation_percent = activation_percent
        self.trail_percent = trail_percent

        # Трейдинг переменные
        self.entry_price = None
        self.best_price = None
        self.is_active = False
        self.stop_price = None
        self.is_position_closed = False

        # Статистика
        self.entry_time = None
        self.close_time = None
        self.total_profit = 0

    def update(self, current_price):
        if self.is_position_closed:
            return "ALREADY_CLOSED"

        # Инициализация при первой цене
        if self.entry_price is None:
            self.entry_price = current_price
            self.best_price = current_price
            self.entry_time = time()
            print(f"🎯 Виртуальная позиция открыта по цене: {current_price:.2f}")
            return "POSITION_OPENED"

        # Расчет текущей прибыли
        if self.position_size > 0:  # LONG
            current_profit_percent = (current_price - self.entry_price) / self.entry_price * 100
            current_profit_usd = (current_price - self.entry_price) * abs(self.position_size)
        else:  # SHORT
            current_profit_percent = (self.entry_price - current_price) / self.entry_price * 100
            current_profit_usd = (self.entry_price - current_price) * abs(self.position_size)

        # Логика для LONG позиции
        if self.position_size > 0:
            if current_price > self.best_price:
                self.best_price = current_price
                print(f"📈 Новый максимум: {current_price:.2f}")

            # Активация трейлинг-стопа
            if not self.is_active and current_profit_percent >= self.activation_percent:
                self.is_active = True
                self.stop_price = self.best_price * (1 - self.trail_percent / 100)
                print(f"🚀 Трейлинг-стоп АКТИВИРОВАН!")
                print(f"   Прибыль: {current_profit_percent:.2f}% ({current_profit_usd:.2f}$)")
                print(f"   Стоп-цена: {self.stop_price:.2f}")

            # Обновление стопа
            if self.is_active:
                new_stop = self.best_price * (1 - self.trail_percent / 100)
                if new_stop > self.stop_price:
                    self.stop_price = new_stop
                    print(f"🔼 Стоп перемещен: {self.stop_price:.2f}")

                # Проверка срабатывания стопа
                if current_price <= self.stop_price:
                    self.is_position_closed = True
                    self.close_time = time()
                    self.total_profit = current_profit_usd

                    print(f"🔴 ТРЕЙЛИНГ-СТОП СРАБОТАЛ!")
                    print(f"   Цена срабатывания: {current_price:.2f}")
                    print(f"   Итоговая прибыль: {current_profit_percent:.2f}% ({current_profit_usd:.2f}$)")
                    print(f"   Длительность позиции: {self.close_time - self.entry_time:.1f} сек")
                    return "STOP_HIT"

        # Логика для SHORT позиции (аналогично)
        elif self.position_size < 0:
            if current_price < self.best_price:
                self.best_price = current_price
                print(f"📉 Новый минимум: {current_price:.2f}")

            if not self.is_active and current_profit_percent >= self.activation_percent:
                self.is_active = True
                self.stop_price = self.best_price * (1 + self.trail_percent / 100)
                print(f"🚀 Трейлинг-стоп АКТИВИРОВАН!")
                print(f"   Прибыль: {current_profit_percent:.2f}% ({current_profit_usd:.2f}$)")
                print(f"   Стоп-цена: {self.stop_price:.2f}")

            if self.is_active:
                new_stop = self.best_price * (1 + self.trail_percent / 100)
                if new_stop < self.stop_price:
                    self.stop_price = new_stop
                    print(f"🔽 Стоп перемещен: {self.stop_price:.2f}")

                if current_price >= self.stop_price:
                    self.is_position_closed = True
                    self.close_time = time()
                    self.total_profit = current_profit_usd

                    print(f"🔴 ТРЕЙЛИНГ-СТОП СРАБОТАЛ!")
                    print(f"   Цена срабатывания: {current_price:.2f}")
                    print(f"   Итоговая прибыль: {current_profit_percent:.2f}% ({current_profit_usd:.2f}$)")
                    return "STOP_HIT"

        # Вывод текущего статуса (редко, чтобы не засорять консоль)
        if hasattr(self, 'last_print') and time() - self.last_print > 5:
            status = "АКТИВЕН" if self.is_active else "ОЖИДАНИЕ"
            print(f"📊 Текущая цена: {current_price:.2f} | Прибыль: {current_profit_percent:+.2f}% | Статус: {status}")
            self.last_print = time()
        elif not hasattr(self, 'last_print'):
            self.last_print = time()

        return "UPDATED"


# Создаем виртуальный трейлинг-стоп
trailing_stop = PaperTrailingStop(
    symbol="BTCUSDT",
    position_size=0.001,  # Лонг 0.001 BTC
    activation_percent=1.0,  # Активация при +1%
    trail_percent=0.5  # Следование на 0.5%
)


def handle_message(message):
    try:
        if 'data' in message:
            data = message['data']

            # Получаем последнюю цену
            last_price = float(data.get('lastPrice', 0))
            bid_price = float(data.get('bid1Price', 0))
            ask_price = float(data.get('ask1Price', 0))

            # Пропускаем нулевые цены
            if last_price == 0:
                return

            # Обновляем трейлинг-стоп
            result = trailing_stop.update(last_price)

            # Выводим дополнительную информацию о рынке
            if hasattr(handle_message, 'counter'):
                handle_message.counter += 1
            else:
                handle_message.counter = 1
                print("🟢 Начинаем мониторинг рынка...")
                print("=" * 50)

            # Раз в 20 сообщений показываем рыночные данные
            if handle_message.counter % 20 == 0:
                change_24h = float(data.get('price24hPcnt', 0)) * 100
                print(f"📈 Рынок: {last_price:.2f} | 24h: {change_24h:+.2f}% | Bid/Ask: {bid_price:.2f}/{ask_price:.2f}")

    except Exception as e:
        print(f"❌ Ошибка обработки: {e}")


# Настройка WebSocket
ws = WebSocket(
    testnet=True,
    channel_type="linear",
)

# Запускаем поток тикеров
ws.ticker_stream("BTCUSDT", handle_message)

print("🎯 ВИРТУАЛЬНЫЙ ТРЕЙЛИНГ-СТОП ЗАПУЩЕН")
print("Конфигурация:")
print(f"• Символ: BTCUSDT")
print(f"• Размер позиции: {trailing_stop.position_size}")
print(f"• Активация при: +{trailing_stop.activation_percent}%")
print(f"• Трейлинг: {trailing_stop.trail_percent}%")
print("=" * 50)

try:
    while True:
        sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Программа остановлена пользователем")
    if trailing_stop.entry_price and not trailing_stop.is_position_closed:
        current_price = trailing_stop.best_price if trailing_stop.best_price else trailing_stop.entry_price
        profit_percent = (current_price - trailing_stop.entry_price) / trailing_stop.entry_price * 100
        print(f"📊 Финальный статус: Прибыль {profit_percent:+.2f}%")