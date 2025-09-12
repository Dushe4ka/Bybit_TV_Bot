import asyncio
import aiohttp

# ВПИШИ СЮДА СВОЮ МОНЕТУ (например, BTCUSDT, ETHUSDT, SOLUSDT и т.д.)
SYMBOL = "BTCUSDT"

# Для фьючерсов (linear) используем этот адрес:
WS_URL = "wss://stream.bybit.com/v5/public/linear"

async def main():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            # Подписка на тикер монеты
            sub_msg = {
                "op": "subscribe",
                "args": [f"tickers.{SYMBOL}"]
            }
            await ws.send_json(sub_msg)
            print(f"Подписка на {SYMBOL} отправлена!")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    # Проверяем, что пришли данные по цене
                    if 'data' in data and isinstance(data['data'], dict):
                        last_price = data['data'].get('lastPrice')
                        if last_price:
                            print(f"Текущая цена {SYMBOL}: {last_price}")

if __name__ == "__main__":
    asyncio.run(main())