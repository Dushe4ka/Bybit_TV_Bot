import json
import re

def parse_signal_message(message):
    """
    Улучшенный парсинг сообщения с надежной обработкой JSON
    """
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
    coin = "Неизвестная монета"
    code = "Код не найден"
    
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

def main():
    print("Парсер торговых сигналов")
    print("Примеры ввода:")
    print('1. {"text": "BTCUSDT: Code 1 SHORT signal!"}')
    print('2. BTCUSDT: Code 2 SHORT signal!')
    print('3. {"text": "ETHUSDT.P: Code 1 LONG signal!"}')
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\nВведите сообщение (exit для выхода): ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("До свидания!")
                break
                
            if not user_input:
                continue
                
            coin, code = parse_signal_message(user_input)
            print(f"✅ Монета: {coin}")
            print(f"✅ Код: {code}")
            
        except KeyboardInterrupt:
            print("\n\nПрограмма завершена")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()