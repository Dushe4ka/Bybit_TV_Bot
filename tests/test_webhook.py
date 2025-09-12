#!/usr/bin/env python3
import requests
import json

def test_webhook(symbol):
    url = "http://localhost:8000/webhook"
    data = {"text": symbol}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        print(f"Статус: {response.status_code}")
        print(f"Ответ: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

if __name__ == "__main__":
    symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
    
    for symbol in symbols:
        print(f"\nТестируем символ: {symbol}")
        success = test_webhook(symbol)
        if success:
            print(f"✅ {symbol} - успешно")
        else:
            print(f"❌ {symbol} - ошибка") 