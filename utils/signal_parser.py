import re
from typing import Tuple, Optional
from logger_config import setup_logger

logger = setup_logger(__name__)

def parse_signal_message(message):
    """
    Улучшенный парсинг сообщения с надежной обработкой JSON
    """
    import json
    
    text = str(message)
    
    # Пытаемся найти JSON в строке
    if '{' in text and '}' in text:
        try:
            # Ищем JSON объект в строке
            start = text.find('{')
            end = text.rfind('}') + 1
            json_str = text[start:end]
            
            data = json.loads(json_str)
            if 'text' in data:
                text = data['text']
        except (json.JSONDecodeError, ValueError):
            # Если не получается распарсить JSON, оставляем исходный текст
            pass
    
    # Извлекаем монету и код
    coin = None
    code = None
    
    # Разделяем по первому двоеточию
    if ':' in text:
        parts = text.split(':', 1)
        coin = parts[0].strip()
        remaining_text = parts[1]
    else:
        remaining_text = text
    
    # Ищем код в оставшемся тексте
    code_match = re.search(r'Code\s+(\d+)', remaining_text)
    if code_match:
        code = f"Code {code_match.group(1)}"
    
    return coin, code

def parse_signal(signal_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Парсит сигнал и возвращает символ и тип сигнала
    
    Args:
        signal_text: Текст сигнала, например "ALUUSDT.P: Code 1 SHORT signal!"
    
    Returns:
        Tuple[Optional[str], Optional[str]]: (символ, тип_сигнала)
        Пример: ("ALUUSDT", "WEAK_SHORT")
    """
    try:
        # Используем улучшенный парсер
        coin, code = parse_signal_message(signal_text)
        
        if coin and code:
            # Очищаем символ
            symbol = coin.strip().upper()
            
            # Удаляем суффикс .P если он есть (TradingView добавляет его для perpetual контрактов)
            if symbol.endswith('.P'):
                symbol = symbol[:-2]
                logger.info(f"[SignalParser] Удален суффикс .P из символа: {coin} -> {symbol}")
            
            # Определяем тип сигнала на основе кода
            signal_type = determine_signal_type(code)
            
            if symbol and signal_type:
                logger.info(f"[SignalParser] Распознан сигнал: символ={symbol}, код={code}, тип={signal_type}")
                return symbol, signal_type
        
        logger.warning(f"[SignalParser] Не удалось распарсить сигнал: {signal_text}")
        return None, None
            
    except Exception as e:
        logger.error(f"[SignalParser] Ошибка при парсинге сигнала '{signal_text}': {e}")
        return None, None

def determine_signal_type(code: str) -> Optional[str]:
    """
    Определяет тип сигнала на основе кода
    
    Args:
        code: Код сигнала, например "Code 1" или "Code 2"
    
    Returns:
        Optional[str]: Нормализованный тип сигнала
    """
    code = code.upper().strip()
    
    # Словарь для сопоставления кодов с типами сигналов
    code_mapping = {
        "CODE 1": "WEAK_SHORT",           # Code 1 = WEAK SHORT стратегия
        "CODE 2": "STRONG_SHORT",         # Code 2 = STRONG SHORT стратегия
        "CODE 3": "SHORT_AVERAGING",      # Code 3 = SHORT с усреднением
        # Можно добавить другие коды в будущем
    }
    
    # Ищем точное совпадение
    if code in code_mapping:
        return code_mapping[code]
    
    logger.warning(f"[SignalParser] Неизвестный код сигнала: {code}")
    return None



def get_strategy_function(signal_type: str) -> Optional[str]:
    """
    Возвращает название функции стратегии для данного типа сигнала
    
    Args:
        signal_type: Тип сигнала (STRONG_SHORT, WEAK_SHORT, SHORT_AVERAGING, etc.)
    
    Returns:
        Optional[str]: Название функции стратегии
    """
    strategy_mapping = {
        "STRONG_SHORT": "strong_short_strategy",
        "WEAK_SHORT": "weak_short_strategy",
        "SHORT_AVERAGING": "short_averaging_strategy",  # Стратегия с усреднением
        "STRONG_LONG": "strong_long_strategy",  # Пока не реализовано
        "WEAK_LONG": "weak_long_strategy",      # Пока не реализовано
    }
    
    return strategy_mapping.get(signal_type)

def process_signal(signal_text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Обрабатывает полный сигнал и возвращает всю необходимую информацию
    
    Args:
        signal_text: Полный текст сигнала
    
    Returns:
        Tuple[Optional[str], Optional[str], Optional[str]]: (символ, тип_сигнала, функция_стратегии)
    """
    symbol, signal_type = parse_signal(signal_text)
    
    if not symbol or not signal_type:
        return None, None, None
    
    # Получаем функцию стратегии
    strategy_function = get_strategy_function(signal_type)
    
    if not strategy_function:
        logger.error(f"[SignalParser] Неизвестный тип сигнала: {signal_type}")
        return None, None, None
    
    logger.info(f"[SignalParser] Обработан сигнал: символ={symbol}, тип={signal_type}, стратегия={strategy_function}")
    return symbol, signal_type, strategy_function

# Тестовые функции
def test_signal_parsing():
    """Тестирует парсинг различных сигналов"""
    test_signals = [
        "'Heiusdt': STRONG SHORT signal!",
        "'BTCUSDT': WEAK SHORT signal!",
        "'ETHUSDT': STRONG LONG signal!",
        "'ADAUSDT': WEAK LONG signal!",
        "Invalid signal format",
        "'XRPUSDT.P': STRONG SHORT signal!",  # Невалидный символ
    ]
    
    print("=== Тестирование парсинга сигналов ===")
    
    for signal in test_signals:
        print(f"\nСигнал: {signal}")
        symbol, signal_type, strategy = process_signal(signal)
        
        if symbol and signal_type and strategy:
            print(f"✅ Результат: символ={symbol}, тип={signal_type}, стратегия={strategy}")
        else:
            print(f"❌ Не удалось обработать сигнал")

def clean_symbol(symbol: str) -> str:
    """
    Очищает символ от кавычек, пробелов и суффиксов TradingView
    
    Args:
        symbol: Исходный символ
        
    Returns:
        Очищенный символ
    """
    if not symbol:
        return symbol
    
    # Убираем кавычки и пробелы
    cleaned = symbol.strip().strip("'\"")
    
    # Убираем суффиксы TradingView (.P, .PERP и т.д.)
    suffixes_to_remove = ['.P', '.PERP', '.PERPETUAL']
    for suffix in suffixes_to_remove:
        if cleaned.upper().endswith(suffix):
            original = cleaned
            cleaned = cleaned[:-len(suffix)]
            logger.info(f"Удален суффикс {suffix} из символа: {original} -> {cleaned}")
            break
    
    return cleaned

if __name__ == "__main__":
    test_signal_parsing() 