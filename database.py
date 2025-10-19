import motor.motor_asyncio
import pymongo
import redis
import json
import threading
from typing import Optional, List
from logger_config import setup_logger

logger = setup_logger(__name__)

# MongoDB настройки
MONGO_URI = 'mongodb://localhost:27017'
DB_NAME = 'bybit_tv'
COLLECTION_NAME = 'subscriptions'
COMPLETED_COLLECTION_NAME = 'completed_transactions'

# Redis настройки
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None  # Если нужен пароль, укажите здесь

# Асинхронный MongoDB клиент (Motor)
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]
completed_collection = db[COMPLETED_COLLECTION_NAME]

# Синхронный MongoDB клиент (PyMongo)
sync_client = pymongo.MongoClient(MONGO_URI)
sync_db = sync_client[DB_NAME]
sync_collection = sync_db[COLLECTION_NAME]
sync_completed_collection = sync_db[COMPLETED_COLLECTION_NAME]

# Redis клиент
try:
    redis_client = redis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        db=REDIS_DB, 
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    # Проверяем соединение
    redis_client.ping()
    logger.info("✅ Redis подключен успешно")
except Exception as e:
    logger.error(f"❌ Ошибка подключения к Redis: {e}")
    redis_client = None

# Блокировка для обновления кэша
_cache_lock = threading.Lock()

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


# ==================== СИНХРОННЫЕ ФУНКЦИИ ДЛЯ CELERY ====================

def is_user_subscribed_sync(user_id: int) -> bool:
    """Синхронная версия проверки подписки пользователя"""
    try:
        doc = sync_collection.find_one({'user_id': user_id})
        return bool(doc and doc.get('subscribed', False))
    except Exception as e:
        logger.error(f"Ошибка проверки подписки пользователя {user_id}: {e}")
        return False

def set_user_subscription_sync(user_id: int, subscribed: bool):
    """Синхронная версия установки подписки пользователя"""
    try:
        sync_collection.update_one(
            {'user_id': user_id},
            {'$set': {'subscribed': subscribed}},
            upsert=True
        )
        # Обновляем кэш после изменения
        update_subscribers_cache()
        logger.info(f"Подписка пользователя {user_id} установлена: {subscribed}")
    except Exception as e:
        logger.error(f"Ошибка установки подписки пользователя {user_id}: {e}")

def get_all_subscribed_users_sync() -> List[int]:
    """Синхронная версия получения всех подписчиков"""
    try:
        cursor = sync_collection.find({'subscribed': True})
        return [doc['user_id'] for doc in cursor]
    except Exception as e:
        logger.error(f"Ошибка получения подписчиков: {e}")
        return []

def save_completed_transaction_sync(transaction: dict):
    """Синхронная версия сохранения завершенной транзакции"""
    try:
        sync_completed_collection.insert_one(transaction)
        logger.info(f"Транзакция сохранена: {transaction.get('symbol', 'unknown')}")
    except Exception as e:
        logger.error(f"Ошибка сохранения транзакции: {e}")

def get_all_completed_transactions_sync() -> List[dict]:
    """Синхронная версия получения всех завершенных транзакций"""
    try:
        cursor = sync_completed_collection.find({})
        return [doc for doc in cursor]
    except Exception as e:
        logger.error(f"Ошибка получения транзакций: {e}")
        return []


# ==================== REDIS КЭШИРОВАНИЕ ====================

def get_cached_subscribers() -> List[int]:
    """Получает кэшированный список подписчиков из Redis"""
    if not redis_client:
        logger.warning("Redis недоступен, используем синхронную БД")
        return get_all_subscribed_users_sync()
    
    try:
        cached = redis_client.get('subscribed_users')
        if cached:
            users = json.loads(cached)
            logger.debug(f"Получено {len(users)} подписчиков из кэша")
            return users
    except Exception as e:
        logger.error(f"Ошибка получения кэша подписчиков: {e}")
    
    # Если кэш пуст или ошибка, получаем из БД и кэшируем
    logger.info("Кэш подписчиков пуст, обновляем из БД")
    return update_subscribers_cache()

def update_subscribers_cache() -> List[int]:
    """Обновляет кэш подписчиков в Redis"""
    if not redis_client:
        logger.warning("Redis недоступен, возвращаем данные из БД")
        return get_all_subscribed_users_sync()
    
    with _cache_lock:
        try:
            # Получаем актуальные данные из БД
            users = get_all_subscribed_users_sync()
            
            # Сохраняем в Redis с TTL 5 минут
            redis_client.setex('subscribed_users', 300, json.dumps(users))
            logger.info(f"Кэш подписчиков обновлен: {len(users)} пользователей")
            return users
            
        except Exception as e:
            logger.error(f"Ошибка обновления кэша подписчиков: {e}")
            # Fallback на БД
            return get_all_subscribed_users_sync()

def invalidate_subscribers_cache():
    """Инвалидирует кэш подписчиков"""
    if not redis_client:
        return
    
    try:
        redis_client.delete('subscribed_users')
        logger.info("Кэш подписчиков очищен")
    except Exception as e:
        logger.error(f"Ошибка очистки кэша подписчиков: {e}")

def get_subscribers_count() -> int:
    """Возвращает количество подписчиков (из кэша или БД)"""
    try:
        users = get_cached_subscribers()
        return len(users)
    except Exception as e:
        logger.error(f"Ошибка получения количества подписчиков: {e}")
        return 0


# import asyncio
# from utils.send_tg_message import send_message_to_telegram
# from config import TELEGRAM_BOT_TOKEN

# async def main():
#     users = await get_all_subscribed_users()
#     send_message_to_telegram('test', users, TELEGRAM_BOT_TOKEN)

# asyncio.run(main())