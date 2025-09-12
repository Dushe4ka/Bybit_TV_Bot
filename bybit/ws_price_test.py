import time
import logging
from pybit.unified_trading import WebSocket

# Настройка логгера
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SYMBOL = "BTCUSDT"  # замените на нужный тикер

last_price = None
non_dict_msg_count = 0  # Счётчик для не-dict сообщений

def price_callback(msg):
    global last_price, non_dict_msg_count
    if not isinstance(msg, dict):
        if non_dict_msg_count < 3:
            logger.info(f"Сервисное сообщение от WebSocket (тип {type(msg)}): {msg}")
        non_dict_msg_count += 1
        return
    try:
        for ticker in msg.get('data', []):
            if ticker.get('symbol') == SYMBOL:
                last_price = float(ticker.get('lastPrice'))
                logger.info(f"Текущая цена {SYMBOL}: {last_price}")
    except Exception as e:
        logger.error(f"Ошибка в price_callback (dict): {e}")

def start_ws():
    while True:
        try:
            logger.info(f"Запуск WebSocket для {SYMBOL}")
            ws = WebSocket(testnet=False, channel_type="linear")
            ws.ticker_stream(callback=price_callback, symbol=SYMBOL)
            while True:
                time.sleep(5)
                if last_price is not None:
                    logger.info(f"Последняя полученная цена {SYMBOL}: {last_price}")
                else:
                    logger.info(f"Нет данных по цене для {SYMBOL} (ожидание)")
        except Exception as e:
            logger.error(f"WebSocket ошибка: {e}. Переподключение через 5 секунд...")
            time.sleep(5)
        finally:
            try:
                ws.exit()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        start_ws()
    except KeyboardInterrupt:
        logger.info("Остановка теста WebSocket...") 