#!/usr/bin/env python3
"""
Тестовый скрипт для проверки принудительного завершения работы при закрытии позиции
"""

import requests
import json
import time
import asyncio
from bybit.position_monitor import position_monitor

# Настройки
BASE_URL = "http://localhost:8000"

def test_position_closure():
    """Тестирует сценарий: открытие позиции -> принудительное закрытие -> завершение работы"""
    print("=== Тест принудительного завершения работы при закрытии позиции ===\n")
    
    # Шаг 1: Запускаем стратегию
    print("1. Запускаем стратегию для BTCUSDT...")
    symbol = "BTCUSDT"
    
    url = f"{BASE_URL}/webhook"
    data = {"text": symbol}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"   Ответ: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            print("   ✅ Стратегия запущена успешно")
        else:
            print("   ❌ Ошибка запуска стратегии")
            return
            
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return
    
    # Шаг 2: Ждем немного, чтобы позиция открылась
    print("\n2. Ждем 10 секунд для открытия позиции...")
    time.sleep(10)
    
    # Шаг 3: Проверяем активные позиции
    print("\n3. Проверяем активные позиции...")
    try:
        response = requests.get(f"{BASE_URL}/active_positions", timeout=10)
        print(f"   Ответ: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Шаг 4: Симулируем принудительное закрытие позиции
    print("\n4. Симулируем принудительное закрытие позиции...")
    print("   (В реальности нужно закрыть позицию вручную в Bybit)")
    print("   Система должна автоматически завершить работу воркера")
    
    # Шаг 5: Проверяем логи через некоторое время
    print("\n5. Проверяем состояние через 30 секунд...")
    time.sleep(30)
    
    try:
        response = requests.get(f"{BASE_URL}/active_positions", timeout=10)
        print(f"   Ответ: {response.status_code} - {response.text}")
        
        # Парсим ответ
        try:
            result = response.json()
            if 'positions' in result and result['positions']:
                print("   ⚠️  Позиции все еще активны")
            else:
                print("   ✅ Позиции закрыты, воркер освобожден")
        except:
            print("   ❓ Не удалось проанализировать ответ")
            
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print("\n=== Тест завершен ===")
    print("\nИнструкции для полного тестирования:")
    print("1. Запустите этот скрипт")
    print("2. Откройте Bybit и найдите открытую позицию")
    print("3. Закройте позицию вручную")
    print("4. Проверьте логи Celery - воркер должен завершить работу")
    print("5. Проверьте, что воркер готов к новой сделке")

def test_multiple_positions():
    """Тестирует работу с несколькими позициями одновременно"""
    print("\n=== Тест работы с несколькими позициями ===\n")
    
    symbols = ["BTCUSDT", "ETHUSDT"]
    
    for i, symbol in enumerate(symbols, 1):
        print(f"{i}. Запускаем стратегию для {symbol}...")
        
        try:
            response = requests.post(f"{BASE_URL}/webhook", 
                                  json={"text": symbol}, 
                                  timeout=10)
            print(f"   Ответ: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                print(f"   ✅ Стратегия для {symbol} запущена")
            else:
                print(f"   ❌ Ошибка запуска стратегии для {symbol}")
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        time.sleep(5)  # Небольшая пауза между запусками
    
    print("\nПроверяем активные позиции...")
    try:
        response = requests.get(f"{BASE_URL}/active_positions", timeout=10)
        print(f"Ответ: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    print("Тестирование системы принудительного завершения работы при закрытии позиции")
    print("=" * 70)
    
    # Тест 1: Одиночная позиция
    test_position_closure()
    
    # Тест 2: Несколько позиций
    test_multiple_positions()
    
    print("\n" + "=" * 70)
    print("Тестирование завершено!") 