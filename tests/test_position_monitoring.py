#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы мониторинга позиций
"""

import requests
import json
import time

# Настройки
BASE_URL = "http://localhost:8000"

def test_webhook(symbol: str):
    """Тестирует webhook endpoint"""
    print(f"Тестируем webhook для символа: {symbol}")
    
    url = f"{BASE_URL}/webhook"
    data = {"text": symbol}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"Ответ webhook: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        print(f"Ошибка webhook: {e}")
        return None

def test_stop_monitoring(symbol: str):
    """Тестирует остановку мониторинга"""
    print(f"Тестируем остановку мониторинга для символа: {symbol}")
    
    url = f"{BASE_URL}/stop_monitoring"
    data = {"text": symbol}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"Ответ stop_monitoring: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        print(f"Ошибка stop_monitoring: {e}")
        return None

def test_get_positions():
    """Тестирует получение активных позиций"""
    print("Тестируем получение активных позиций")
    
    url = f"{BASE_URL}/active_positions"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Ответ active_positions: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        print(f"Ошибка active_positions: {e}")
        return None

def test_health():
    """Тестирует health endpoint"""
    print("Тестируем health endpoint")
    
    url = f"{BASE_URL}/health"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Ответ health: {response.status_code} - {response.text}")
        return response.json()
    except Exception as e:
        print(f"Ошибка health: {e}")
        return None

def main():
    """Основная функция тестирования"""
    print("=== Тестирование системы мониторинга позиций ===\n")
    
    # Тест 1: Проверка health
    test_health()
    print()
    
    # Тест 2: Запуск стратегии для валидного символа
    valid_symbol = "BTCUSDT"
    test_webhook(valid_symbol)
    print()
    
    # Тест 3: Попытка запуска для невалидного символа
    invalid_symbol = "XRPUSDT.P"
    test_webhook(invalid_symbol)
    print()
    
    # Тест 4: Получение активных позиций
    test_get_positions()
    print()
    
    # Тест 5: Остановка мониторинга
    test_stop_monitoring(valid_symbol)
    print()
    
    print("=== Тестирование завершено ===")

if __name__ == "__main__":
    main() 