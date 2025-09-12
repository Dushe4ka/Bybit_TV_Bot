#!/usr/bin/env python3
"""
Тестовый скрипт для проверки парсинга сигналов
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.signal_parser import parse_signal, process_signal

def test_signal_parsing():
    """Тестирует парсинг различных форматов сигналов"""
    
    # Тестовые сигналы
    test_signals = [
        # Новые форматы с Code
        "ALUUSDT.P: Code 1 SHORT signal!",
        "ALUUSDT.P: Code 2 SHORT signal!",
        "BTCUSDT: Code 1 SHORT signal!",
        "ETHUSDT: Code 2 SHORT signal!",
        
        # JSON форматы
        '{"text": "ALUUSDT.P: Code 1 SHORT signal!"}',
        '{"text": "BTCUSDT: Code 2 SHORT signal!"}',
        '{"text": "ETHUSDT.P: Code 1 SHORT signal!"}',
        
        # Неправильные форматы
        "Invalid signal format",
        "BTCUSDT: UNKNOWN signal!",
        "BTCUSDT: Code 3 SHORT signal!",
        "BTCUSDT: Code 1 UNKNOWN signal!"
    ]
    
    print("🧪 Тестирование парсера сигналов\n")
    
    for i, signal in enumerate(test_signals, 1):
        print(f"Тест {i}: {signal}")
        
        # Парсим сигнал
        symbol, signal_type = parse_signal(signal)
        
        if symbol and signal_type:
            print(f"   Результат: ✅ РАСПОЗНАН")
            print(f"   Символ: {symbol}")
            print(f"   Тип: {signal_type}")
        else:
            print(f"   Результат: ❌ НЕ РАСПОЗНАН")
        
        print()
    
    print("🎯 Тестирование завершено!")

def test_process_signal():
    """Тестирует полную обработку сигнала через process_signal"""
    
    print("\n🔧 Тестирование полной обработки сигнала\n")
    
    # Тестовые сигналы
    test_signals = [
        "ALUUSDT.P: Code 1 SHORT signal!",
        "ALUUSDT.P: Code 2 SHORT signal!",
        "BTCUSDT: Code 1 SHORT signal!",
        "ETHUSDT: Code 2 SHORT signal!"
    ]
    
    for i, signal in enumerate(test_signals, 1):
        print(f"Тест {i}: {signal}")
        
        # Полная обработка сигнала
        symbol, signal_type, strategy = process_signal(signal)
        
        if symbol and signal_type and strategy:
            print(f"   Результат: ✅ ПОЛНОСТЬЮ ОБРАБОТАН")
            print(f"   Символ: {symbol}")
            print(f"   Тип: {signal_type}")
            print(f"   Стратегия: {strategy}")
        else:
            print(f"   Результат: ❌ ОШИБКА ОБРАБОТКИ")
        
        print()
    
    print("🎯 Тестирование полной обработки завершено!")

if __name__ == "__main__":
    test_signal_parsing()
    test_process_signal() 