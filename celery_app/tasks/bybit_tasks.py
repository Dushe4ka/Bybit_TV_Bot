from celery_app import celery_app
import asyncio
import threading
from bybit.open_order_tekprofit_stoploss import strong_short_strategy, short_strategy
from bybit.weak_short_strategy import weak_short_strategy
from bybit.position_monitor import position_monitor
from bybit.averaging_strategy_celery import run_short_averaging_strategy
from utils.signal_parser import process_signal
from utils.send_tg_message import send_message_to_telegram
from database import get_all_subscribed_users
from config import TELEGRAM_BOT_TOKEN
from logger_config import setup_logger

logger = setup_logger(__name__)

# Глобальный словарь для хранения event loop для каждого потока
_thread_local = threading.local()

def get_or_create_event_loop():
    """Получает или создает event loop для текущего потока"""
    if not hasattr(_thread_local, 'loop'):
        _thread_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local.loop)
    return _thread_local.loop

def get_strategy_function(strategy_name: str):
    """Возвращает функцию стратегии по названию"""
    strategy_functions = {
        'strong_short_strategy': strong_short_strategy,
        'weak_short_strategy': weak_short_strategy,
        'short_strategy': short_strategy,  # Алиас для обратной совместимости
        'short_averaging_strategy': run_short_averaging_strategy,  # Стратегия с усреднением
    }
    return strategy_functions.get(strategy_name)

async def send_error_notification(symbol: str, error_message: str, strategy_name: str = ""):
    """Отправляет уведомление об ошибке в Telegram"""
    try:
        chat_ids = await get_all_subscribed_users()
        strategy_text = f" ({strategy_name})" if strategy_name else ""
        message = f"❌ Ошибка при обработке сигнала для {symbol}{strategy_text}:\n{error_message}\n\nСигнал не обработан."
        await send_message_to_telegram(message, chat_ids, TELEGRAM_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление об ошибке: {e}")

@celery_app.task(bind=True, name='celery_app.tasks.bybit_tasks.run_strategy_by_signal')
def run_strategy_by_signal(self, signal_text: str):
    """Запускает стратегию на основе парсинга сигнала"""
    logger.info(f"[Bybit] Обработка сигнала: {signal_text}")
    
    try:
        # Парсим сигнал
        symbol, signal_type, strategy_function_name = process_signal(signal_text)
        
        if not symbol or not signal_type or not strategy_function_name:
            logger.error(f"[Bybit] Не удалось обработать сигнал: {signal_text}")
            return {'status': 'error', 'error': 'Не удалось обработать сигнал'}
        
        # Получаем функцию стратегии
        strategy_function = get_strategy_function(strategy_function_name)
        if not strategy_function:
            logger.error(f"[Bybit] Неизвестная стратегия: {strategy_function_name}")
            return {'status': 'error', 'error': f'Неизвестная стратегия: {strategy_function_name}'}
        
        # Получаем или создаем event loop для текущего потока
        loop = get_or_create_event_loop()
        logger.info(f"[Bybit] Запуск стратегии {strategy_function_name} для {symbol}")
        
        # Запускаем асинхронную функцию в изолированном event loop
        result = loop.run_until_complete(strategy_function(symbol))
        return {
            'status': 'success', 
            'symbol': symbol, 
            'signal_type': signal_type,
            'strategy': strategy_function_name
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Bybit] Ошибка при обработке сигнала '{signal_text}': {error_msg}")
        
        # Отправляем уведомление об ошибке
        try:
            loop = get_or_create_event_loop()
            loop.run_until_complete(send_error_notification(symbol or "неизвестный", error_msg, strategy_function_name or ""))
        except Exception as notify_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notify_error}")
        
        return {'status': 'error', 'signal': signal_text, 'error': error_msg}

@celery_app.task(bind=True, name='celery_app.tasks.bybit_tasks.run_short_strategy')
def run_short_strategy(self, symbol: str):
    """Запускает стандартную шорт-стратегию (для обратной совместимости)"""
    # Очищаем символ от лишних кавычек и пробелов
    clean_symbol = symbol.strip().strip("'\"")
    logger.info(f"[Bybit] Запуск стандартной short_strategy для {clean_symbol}")
    
    try:
        # Получаем или создаем event loop для текущего потока
        loop = get_or_create_event_loop()
        logger.info(f"[Bybit] Используем event loop для {clean_symbol}: {loop}")
        
        # Запускаем асинхронную функцию в изолированном event loop
        result = loop.run_until_complete(short_strategy(clean_symbol))
        return {'status': 'success', 'symbol': clean_symbol}
        
    except Exception as e:
        logger.error(f"[Bybit] Ошибка при запуске short_strategy для {clean_symbol}: {e}")
        return {'status': 'error', 'symbol': clean_symbol, 'error': str(e)}

@celery_app.task(bind=True, name='celery_app.tasks.bybit_tasks.run_strong_short_strategy')
def run_strong_short_strategy(self, symbol: str):
    """Запускает STRONG SHORT стратегию"""
    clean_symbol = symbol.strip().strip("'\"")
    logger.info(f"[Bybit] Запуск STRONG SHORT стратегии для {clean_symbol}")
    
    try:
        loop = get_or_create_event_loop()
        logger.info(f"[Bybit] Используем event loop для {clean_symbol}: {loop}")
        
        result = loop.run_until_complete(strong_short_strategy(clean_symbol))
        return {'status': 'success', 'symbol': clean_symbol, 'strategy': 'strong_short'}
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Bybit] Ошибка при запуске STRONG SHORT стратегии для {clean_symbol}: {error_msg}")
        
        # Отправляем уведомление об ошибке
        try:
            loop = get_or_create_event_loop()
            loop.run_until_complete(send_error_notification(clean_symbol, error_msg, "STRONG SHORT"))
        except Exception as notify_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notify_error}")
        
        return {'status': 'error', 'symbol': clean_symbol, 'error': error_msg}

@celery_app.task(bind=True, name='celery_app.tasks.bybit_tasks.run_weak_short_strategy')
def run_weak_short_strategy(self, symbol: str):
    """Запускает WEAK SHORT стратегию"""
    clean_symbol = symbol.strip().strip("'\"")
    logger.info(f"[Bybit] Запуск WEAK SHORT стратегии для {clean_symbol}")
    
    try:
        loop = get_or_create_event_loop()
        logger.info(f"[Bybit] Используем event loop для {clean_symbol}: {loop}")
        
        result = loop.run_until_complete(weak_short_strategy(clean_symbol))
        return {'status': 'success', 'symbol': clean_symbol, 'strategy': 'weak_short'}
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Bybit] Ошибка при запуске WEAK SHORT стратегии для {clean_symbol}: {error_msg}")
        
        # Отправляем уведомление об ошибке
        try:
            loop = get_or_create_event_loop()
            loop.run_until_complete(send_error_notification(clean_symbol, error_msg, "WEAK SHORT"))
        except Exception as notify_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notify_error}")
        
        return {'status': 'error', 'symbol': clean_symbol, 'error': error_msg}

@celery_app.task(bind=True, name='celery_app.tasks.bybit_tasks.stop_strategy_monitoring')
def stop_strategy_monitoring(self, symbol: str):
    """Принудительно останавливает мониторинг для указанного символа"""
    clean_symbol = symbol.strip().strip("'\"")
    logger.info(f"[Bybit] Запрос на остановку мониторинга для {clean_symbol}")
    
    try:
        # Останавливаем мониторинг позиции
        position_monitor.stop_monitoring(clean_symbol)
        position_monitor.remove_position(clean_symbol)
        
        logger.info(f"[Bybit] Мониторинг для {clean_symbol} остановлен")
        return {'status': 'stopped', 'symbol': clean_symbol}
        
    except Exception as e:
        logger.error(f"[Bybit] Ошибка при остановке мониторинга для {clean_symbol}: {e}")
        return {'status': 'error', 'symbol': clean_symbol, 'error': str(e)}

@celery_app.task(bind=True, name='celery_app.tasks.bybit_tasks.get_active_positions')
def get_active_positions(self):
    """Возвращает список активных позиций"""
    try:
        positions = position_monitor.get_active_positions()
        logger.info(f"[Bybit] Получен список активных позиций: {positions}")
        return {'status': 'success', 'positions': positions}
        
    except Exception as e:
        logger.error(f"[Bybit] Ошибка при получении активных позиций: {e}")
        return {'status': 'error', 'error': str(e)}

@celery_app.task(bind=True, name='celery_app.tasks.bybit_tasks.run_short_averaging_strategy')
def run_short_averaging_strategy_task(
    self, 
    symbol: str,
    usdt_amount: float = 100,
    averaging_percent: float = 10.0,
    initial_tp_percent: float = 3.0,
    breakeven_step: float = 2.0,
    stop_loss_percent: float = 15.0,
    use_demo: bool = True
):
    """
    Запускает стратегию SHORT с усреднением
    
    Args:
        symbol: Торговый символ
        usdt_amount: Сумма в USDT
        averaging_percent: Процент усреднения
        initial_tp_percent: Начальный тейк-профит
        breakeven_step: Шаг безубытка
        stop_loss_percent: Стоп-лосс
        use_demo: Использовать демо-счет
    """
    clean_symbol = symbol.strip().strip("'\"")
    logger.info(f"[Bybit] Запуск стратегии SHORT с усреднением для {clean_symbol}")
    logger.info(
        f"[Bybit] Параметры: USDT={usdt_amount}, Averaging={averaging_percent}%, "
        f"TP={initial_tp_percent}%, BE Step={breakeven_step}%, SL={stop_loss_percent}%"
    )
    
    try:
        loop = get_or_create_event_loop()
        logger.info(f"[Bybit] Используем event loop для {clean_symbol}: {loop}")
        
        result = loop.run_until_complete(
            run_short_averaging_strategy(
                symbol=clean_symbol,
                usdt_amount=usdt_amount,
                averaging_percent=averaging_percent,
                initial_tp_percent=initial_tp_percent,
                breakeven_step=breakeven_step,
                stop_loss_percent=stop_loss_percent,
                use_demo=use_demo
            )
        )
        return {'status': 'success', 'symbol': clean_symbol, 'strategy': 'short_averaging'}
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Bybit] Ошибка при запуске стратегии SHORT с усреднением для {clean_symbol}: {error_msg}")
        
        # Отправляем уведомление об ошибке
        try:
            loop = get_or_create_event_loop()
            loop.run_until_complete(send_error_notification(clean_symbol, error_msg, "SHORT_AVERAGING"))
        except Exception as notify_error:
            logger.error(f"Не удалось отправить уведомление об ошибке: {notify_error}")
        
        return {'status': 'error', 'symbol': clean_symbol, 'error': error_msg} 