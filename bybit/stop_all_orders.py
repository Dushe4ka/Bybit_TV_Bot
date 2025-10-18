from pybit.unified_trading import HTTP
from config import DEMO_API_KEY, DEMO_API_SECRET
import time

session = HTTP(
    api_key=DEMO_API_KEY,
    api_secret=DEMO_API_SECRET,
    testnet=False,
    recv_window=60000,
    demo=True,
)

def get_all_orders():
    """Получить все открытые ордера"""
    try:
        response = session.get_open_orders(
            category="linear",
            settleCoin="USDT",  # Добавляем обязательный параметр
            limit=50
        )
        orders = response.get('result', {}).get('list', [])
        
        # Показываем типы ордеров для отладки
        if orders:
            print(f"Найдены ордера следующих типов:")
            order_types = set()
            for order in orders:
                order_types.add(order.get('orderType', 'Unknown'))
            for order_type in order_types:
                print(f"  - {order_type}")
        
        return orders
    except Exception as e:
        print(f"Ошибка при получении ордеров: {e}")
        return []

def get_all_positions():
    """Получить все открытые позиции"""
    try:
        response = session.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        return response.get('result', {}).get('list', [])
    except Exception as e:
        print(f"Ошибка при получении позиций: {e}")
        return []

def cancel_all_orders():
    """Отменить все открытые ордера"""
    orders = get_all_orders()
    
    if not orders:
        print("Нет открытых ордеров для отмены")
        return
    
    print(f"Найдено {len(orders)} открытых ордеров")
    
    for order in orders:
        try:
            symbol = order['symbol']
            order_id = order['orderId']
            order_type = order.get('orderType', 'Unknown')
            side = order.get('side', 'Unknown')
            qty = order.get('qty', 'Unknown')
            price = order.get('price', 'Market')
            
            response = session.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            
            if response.get('retCode') == 0:
                print(f"✅ {order_type} ордер {side} {qty} {symbol} @ {price} отменен")
            else:
                print(f"❌ Ошибка отмены {order_type} ордера {order_id}: {response.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Ошибка при отмене ордера {order.get('orderId', 'unknown')}: {e}")
        
        # Небольшая задержка между запросами
        time.sleep(0.1)

def close_all_positions():
    """Закрыть все открытые позиции"""
    positions = get_all_positions()
    
    # Фильтруем только позиции с размером больше 0
    active_positions = [pos for pos in positions if float(pos['size']) > 0]
    
    if not active_positions:
        print("Нет открытых позиций для закрытия")
        return
    
    print(f"Найдено {len(active_positions)} открытых позиций")
    
    for position in active_positions:
        try:
            symbol = position['symbol']
            side = position['side']
            size = position['size']
            
            # Определяем противоположную сторону для закрытия
            close_side = "Sell" if side == "Buy" else "Buy"
            
            response = session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=size,
                reduceOnly=True
            )
            
            if response.get('retCode') == 0:
                print(f"✅ Позиция {side} {size} {symbol} успешно закрыта")
            else:
                print(f"❌ Ошибка закрытия позиции {symbol}: {response.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Ошибка при закрытии позиции {position.get('symbol', 'unknown')}: {e}")
        
        # Небольшая задержка между запросами
        time.sleep(0.1)

def get_orders_by_symbol(symbol):
    """Получить все открытые ордера для определенной монеты"""
    try:
        response = session.get_open_orders(
            category="linear",
            symbol=symbol,
            settleCoin="USDT",
            limit=50
        )
        return response.get('result', {}).get('list', [])
    except Exception as e:
        print(f"Ошибка при получении ордеров для {symbol}: {e}")
        return []

def get_position_by_symbol(symbol):
    """Получить позицию для определенной монеты"""
    try:
        response = session.get_positions(
            category="linear",
            symbol=symbol,
            settleCoin="USDT"
        )
        positions = response.get('result', {}).get('list', [])
        # Возвращаем позицию если размер больше 0
        for pos in positions:
            if float(pos['size']) > 0:
                return pos
        return None
    except Exception as e:
        print(f"Ошибка при получении позиции для {symbol}: {e}")
        return None

def cancel_orders_by_symbol(symbol):
    """Отменить все ордера для определенной монеты"""
    orders = get_orders_by_symbol(symbol)
    
    if not orders:
        print(f"Нет открытых ордеров для {symbol}")
        return
    
    print(f"Найдено {len(orders)} открытых ордеров для {symbol}")
    
    for order in orders:
        try:
            order_id = order['orderId']
            order_type = order.get('orderType', 'Unknown')
            side = order.get('side', 'Unknown')
            qty = order.get('qty', 'Unknown')
            price = order.get('price', 'Market')
            
            response = session.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            
            if response.get('retCode') == 0:
                print(f"✅ {order_type} ордер {side} {qty} {symbol} @ {price} отменен")
            else:
                print(f"❌ Ошибка отмены {order_type} ордера {order_id}: {response.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Ошибка при отмене ордера {order.get('orderId', 'unknown')}: {e}")
        
        time.sleep(0.1)

def close_position_by_symbol(symbol):
    """Закрыть позицию для определенной монеты"""
    position = get_position_by_symbol(symbol)
    
    if not position:
        print(f"Нет открытой позиции для {symbol}")
        return
    
    try:
        side = position['side']
        size = position['size']
        
        # Определяем противоположную сторону для закрытия
        close_side = "Sell" if side == "Buy" else "Buy"
        
        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=close_side,
            orderType="Market",
            qty=size,
            reduceOnly=True
        )
        
        if response.get('retCode') == 0:
            print(f"✅ Позиция {side} {size} {symbol} успешно закрыта")
        else:
            print(f"❌ Ошибка закрытия позиции {symbol}: {response.get('retMsg')}")
            
    except Exception as e:
        print(f"❌ Ошибка при закрытии позиции {symbol}: {e}")

def stop_trading_by_symbol(symbol):
    """Остановить торговлю для определенной монеты"""
    print(f"🛑 Начинаем остановку торговли для {symbol}...")
    print("=" * 50)
    
    # Сначала отменяем все ордера для этой монеты
    print(f"1. Отменяем все открытые ордера для {symbol}...")
    cancel_orders_by_symbol(symbol)
    
    print("\n" + "=" * 50)
    
    # Затем закрываем позицию для этой монеты
    print(f"2. Закрываем позицию для {symbol}...")
    close_position_by_symbol(symbol)
    
    print("\n" + "=" * 50)
    print(f"✅ Остановка торговли для {symbol} завершена!")

def stop_all_trading():
    """Главная функция для остановки всей торговли"""
    print("🛑 Начинаем остановку всей торговли...")
    print("=" * 50)
    
    # Сначала отменяем все ордера
    print("1. Отменяем все открытые ордера...")
    cancel_all_orders()
    
    print("\n" + "=" * 50)
    
    # Затем закрываем все позиции
    print("2. Закрываем все открытые позиции...")
    close_all_positions()
    
    print("\n" + "=" * 50)
    print("✅ Остановка торговли завершена!")

if __name__ == "__main__":
    # Примеры использования:
    
    # 1. Остановить всю торговлю
    stop_all_trading()
    
    # 2. Остановить торговлю для конкретной монеты
    # stop_trading_by_symbol("BTCUSDT")
    
    # 3. Только отменить ордера для конкретной монеты
    # cancel_orders_by_symbol("ETHUSDT")
    
    # 4. Только закрыть позицию для конкретной монеты
    # close_position_by_symbol("ADAUSDT")