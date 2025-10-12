import aiohttp
from logger_config import setup_logger
from typing import Optional

# Настраиваем логгер
logger = setup_logger("csv_reader_source")

async def send_message_to_telegram(message, chat_ids, TELEGRAM_BOT_TOKEN):
    """Базовая функция отправки сообщений в Telegram"""
    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids:
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
            payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
            try:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    logger.info(f"Сообщение отправлено в чат {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")


async def notify_position_opened(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    entry_price: float,
    quantity: float,
    usdt_amount: float,
    tp_price: float,
    tp_percent: float,
    strategy_type: str = "SHORT"
):
    """
    Уведомление об открытии позиции
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        entry_price: Цена входа
        quantity: Количество актива
        usdt_amount: Сумма в USDT
        tp_price: Цена тейк-профита
        tp_percent: Процент тейк-профита
        strategy_type: Тип стратегии (SHORT/LONG)
    """
    message = (
        f"🚀 <b>ПОЗИЦИЯ ОТКРЫТА</b> 🚀\n\n"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"📉 Тип: <b>{strategy_type}</b>\n"
        f"💰 Сумма: <b>{usdt_amount:.2f} USDT</b>\n"
        f"📈 Количество: <b>{quantity:.4f}</b>\n"
        f"💵 Цена входа: <b>{entry_price:.6f}</b>\n"
        f"🎯 Тейк-профит: <b>{tp_price:.6f}</b> ({tp_percent:.1f}%)\n"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)


async def notify_averaging_order_placed(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    averaging_price: float,
    averaging_percent: float,
    quantity: float
):
    """
    Уведомление о выставлении лимитного ордера на усреднение
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        averaging_price: Цена усреднения
        averaging_percent: Процент усреднения
        quantity: Количество
    """
    message = (
        f"📝 <b>ОРДЕР НА УСРЕДНЕНИЕ</b>\n\n"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"💰 Цена усреднения: <b>{averaging_price:.6f}</b> (+{averaging_percent:.1f}%)\n"
        f"📈 Количество: <b>{quantity:.4f}</b>\n"
        f"⏳ Статус: <b>Ожидание исполнения</b>\n"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)


async def notify_averaging_executed(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    averaged_price: float,
    total_quantity: float,
    new_tp_price: float,
    tp_percent: float,
    stop_loss_price: float,
    sl_percent: float
):
    """
    Уведомление об исполнении усреднения
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        averaged_price: Усредненная цена
        total_quantity: Общее количество
        new_tp_price: Новая цена тейк-профита
        tp_percent: Процент тейк-профита
        stop_loss_price: Цена стоп-лосса
        sl_percent: Процент стоп-лосса
    """
    message = (
        f"🎯 <b>УСРЕДНЕНИЕ ВЫПОЛНЕНО</b> 🎯\n\n"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"💵 Усредненная цена: <b>{averaged_price:.6f}</b>\n"
        f"📊 Общее количество: <b>{total_quantity:.4f}</b>\n"
        f"🎯 Новый TP: <b>{new_tp_price:.6f}</b> ({tp_percent:.1f}%)\n"
        f"🛡️ Стоп-лосс: <b>{stop_loss_price:.6f}</b> (+{sl_percent:.1f}%)\n"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)


async def notify_take_profit_reached(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    current_price: float,
    profit_percent: float,
    breakeven_price: float
):
    """
    Уведомление о достижении тейк-профита
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        current_price: Текущая цена
        profit_percent: Процент прибыли
        breakeven_price: Цена безубытка
    """
    message = (
        f"🎯 <b>ТЕЙК-ПРОФИТ ДОСТИГНУТ!</b>\n\n"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"💰 Текущая цена: <b>{current_price:.6f}</b>\n"
        f"📈 Прибыль: <b>+{profit_percent:.2f}%</b>\n"
        f"🔒 Безубыток установлен на: <b>{breakeven_price:.6f}</b>\n"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)


async def notify_breakeven_moved(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    new_breakeven_price: float,
    breakeven_percent: float,
    current_profit: float
):
    """
    Уведомление о перемещении безубытка
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        new_breakeven_price: Новая цена безубытка
        breakeven_percent: Процент безубытка
        current_profit: Текущая прибыль
    """
    message = (
        f"📈 <b>БЕЗУБЫТОК ПЕРЕМЕЩЕН</b>\n\n"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"🔒 Новый безубыток: <b>{new_breakeven_price:.6f}</b> ({breakeven_percent:.1f}%)\n"
        f"💰 Текущая прибыль: <b>+{current_profit:.2f}%</b>\n"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)


async def notify_position_closed(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    close_reason: str,
    entry_price: float,
    close_price: float,
    quantity: float,
    profit_percent: Optional[float] = None,
    profit_usdt: Optional[float] = None,
    is_averaged: bool = False
):
    """
    Уведомление о закрытии позиции
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        close_reason: Причина закрытия (STOP_LOSS, BREAKEVEN, MANUAL)
        entry_price: Цена входа
        close_price: Цена закрытия
        quantity: Количество
        profit_percent: Процент прибыли/убытка
        profit_usdt: Прибыль/убыток в USDT
        is_averaged: Было ли усреднение
    """
    reason_emoji = {
        "STOP_LOSS": "🛡️",
        "BREAKEVEN": "🔒",
        "MANUAL": "✋",
        "TAKE_PROFIT": "🎯"
    }
    
    emoji = reason_emoji.get(close_reason, "🚨")
    
    profit_text = ""
    if profit_percent is not None:
        sign = "+" if profit_percent >= 0 else ""
        color = "🟢" if profit_percent >= 0 else "🔴"
        profit_text = f"📊 PnL: {color} <b>{sign}{profit_percent:.2f}%</b>\n"
    
    if profit_usdt is not None:
        sign = "+" if profit_usdt >= 0 else ""
        profit_text += f"💵 PnL USDT: <b>{sign}{profit_usdt:.2f} USDT</b>\n"
    
    averaging_text = "✅ Да" if is_averaged else "❌ Нет"
    
    message = (
        f"{emoji} <b>ПОЗИЦИЯ ЗАКРЫТА</b> {emoji}\n\n"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"📝 Причина: <b>{close_reason}</b>\n"
        f"💵 Цена входа: <b>{entry_price:.6f}</b>\n"
        f"💰 Цена закрытия: <b>{close_price:.6f}</b>\n"
        f"📈 Количество: <b>{quantity:.4f}</b>\n"
        f"🔄 Усреднение: <b>{averaging_text}</b>\n"
        f"{profit_text}"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)


async def notify_stop_loss_triggered(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    current_price: float,
    stop_loss_price: float
):
    """
    Уведомление о срабатывании стоп-лосса
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        current_price: Текущая цена
        stop_loss_price: Цена стоп-лосса
    """
    message = (
        f"🛡️ <b>СТОП-ЛОСС СРАБОТАЛ</b>\n\n"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"💰 Текущая цена: <b>{current_price:.6f}</b>\n"
        f"🛑 Стоп-лосс: <b>{stop_loss_price:.6f}</b>\n"
        f"⚠️ Закрываем позицию...\n"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)


async def notify_strategy_error(
    chat_ids: list,
    bot_token: str,
    symbol: str,
    error_message: str,
    strategy_name: str = ""
):
    """
    Уведомление об ошибке в стратегии
    
    Args:
        chat_ids: Список ID чатов
        bot_token: Токен бота
        symbol: Торговый символ
        error_message: Текст ошибки
        strategy_name: Название стратегии
    """
    strategy_text = f" ({strategy_name})" if strategy_name else ""
    message = (
        f"❌ <b>ОШИБКА В СТРАТЕГИИ</b>\n\n"
        f"📊 Символ: <code>{symbol}</code>{strategy_text}\n"
        f"⚠️ Ошибка: <code>{error_message}</code>\n"
    )
    await send_message_to_telegram(message, chat_ids, bot_token)