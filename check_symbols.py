from pybit.unified_trading import HTTP
from config import API_KEY, API_SECRET

# Инициализация сессии
session = HTTP(api_key=API_KEY, api_secret=API_SECRET, testnet=False)

# Получение списка всех символов
try:
    response = session.get_instruments_info(category="linear")
    if response.get("retCode") == 0:
        instruments = response.get("result", {}).get("list", [])
        print(f"Всего символов: {len(instruments)}")
        
        # Поиск SOL символов
        sol_symbols = [inst for inst in instruments if "SOL" in inst.get("symbol", "")]
        print(f"\nСимволы с SOL:")
        for symbol in sol_symbols:
            print(f"  - {symbol['symbol']}")
        
        # Поиск XRP символов
        xrp_symbols = [inst for inst in instruments if "XRP" in inst.get("symbol", "")]
        print(f"\nСимволы с XRP:")
        for symbol in xrp_symbols:
            print(f"  - {symbol['symbol']}")
        
        # Поиск популярных символов
        popular_symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "ADAUSDT", "DOTUSDT", "SOLUSDT"]
        print(f"\nПроверка популярных символов:")
        for symbol in popular_symbols:
            found = any(inst.get("symbol") == symbol for inst in instruments)
            print(f"  - {symbol}: {'✅' if found else '❌'}")
        
        # Показать первые 20 символов для понимания формата
        print(f"\nПервые 20 символов:")
        for i, inst in enumerate(instruments[:20]):
            print(f"  {i+1}. {inst['symbol']}")
            
    else:
        print(f"Ошибка API: {response}")
except Exception as e:
    print(f"Ошибка: {e}") 