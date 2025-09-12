import aiohttp
from logger_config import setup_logger

# Настраиваем логгер
logger = setup_logger("csv_reader_source")

async def send_message_to_telegram(message, chat_ids, TELEGRAM_BOT_TOKEN):
    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids:
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
            payload = {'chat_id': chat_id, 'text': message}
            try:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    logger.info(f"Сообщение отправлено в чат {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")