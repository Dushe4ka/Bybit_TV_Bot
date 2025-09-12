import motor.motor_asyncio
from typing import Optional

MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'bybit_tv'
COLLECTION_NAME = 'subscriptions'
COMPLETED_COLLECTION_NAME = 'completed_transactions'

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]
completed_collection = db[COMPLETED_COLLECTION_NAME]

async def is_user_subscribed(user_id: int) -> bool:
    doc = await collection.find_one({'user_id': user_id})
    return bool(doc and doc.get('subscribed', False))

async def set_user_subscription(user_id: int, subscribed: bool):
    await collection.update_one(
        {'user_id': user_id},
        {'$set': {'subscribed': subscribed}},
        upsert=True
    )

async def get_all_subscribed_users() -> list[int]:
    cursor = collection.find({'subscribed': True})
    return [doc['user_id'] async for doc in cursor]

async def save_completed_transaction(transaction: dict):
    await completed_collection.insert_one(transaction)

async def get_all_completed_transactions() -> list[dict]:
    cursor = completed_collection.find({})
    return [doc async for doc in cursor]


# import asyncio
# from utils.send_tg_message import send_message_to_telegram
# from config import TELEGRAM_BOT_TOKEN

# async def main():
#     users = await get_all_subscribed_users()
#     send_message_to_telegram('test', users, TELEGRAM_BOT_TOKEN)

# asyncio.run(main())