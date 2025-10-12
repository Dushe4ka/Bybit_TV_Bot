from pybit.unified_trading import HTTP
from config import DEMO_API_KEY, DEMO_API_SECRET

session = HTTP(testnet=False, api_key=DEMO_API_KEY, api_secret=DEMO_API_SECRET, demo=True)

def testnet_open_position(symbol, side, qty):
    order = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType="Market",
        qty=qty,
    )
    return order

def testnet_close_position(symbol, side, qty):
    order = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType="Market",
        qty=qty,
    )
    return order

def testnet_get_positions(symbol):
    positions = session.get_positions(category="linear", symbol=symbol)
    return positions

# print(testnet_open_position("BTCUSDT", "Buy", 0.001))
print(testnet_get_positions("BTCUSDT"))