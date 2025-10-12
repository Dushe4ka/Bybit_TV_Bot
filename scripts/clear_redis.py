#!/usr/bin/env python3
"""
Скрипт для очистки Redis от отложенных задач Celery
Подключается к Redis через Docker на порту 14572
"""
import redis
import sys
from celery_app import celery_app

# Параметры подключения к Redis (из celery_config.py)
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 14572
REDIS_PASSWORD = 'Ollama12357985'
REDIS_DB = 10

def clear_redis():
    try:
        # Подключаемся к Redis с паролем
        print(f"🔌 Подключаемся к Redis ({REDIS_HOST}:{REDIS_PORT}, db={REDIS_DB})...")
        r = redis.Redis(
            host=REDIS_HOST, 
            port=REDIS_PORT, 
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # Проверяем подключение
        r.ping()
        print("✅ Подключение к Redis успешно")
        
        # Получаем список всех ключей
        keys = r.keys('*')
        print(f"📊 Найдено ключей в Redis (db={REDIS_DB}): {len(keys)}")
        
        if keys:
            print("\n🔍 Типы ключей:")
            celery_keys = [k for k in keys if 'celery' in k.lower()]
            other_keys = [k for k in keys if 'celery' not in k.lower()]
            print(f"   - Celery ключи: {len(celery_keys)}")
            print(f"   - Другие ключи: {len(other_keys)}")
            
            # Выводим первые 10 ключей для проверки
            if len(keys) <= 10:
                print(f"\n📝 Ключи: {keys}")
            else:
                print(f"\n📝 Первые 10 ключей: {keys[:10]}")
            
            print("\n🗑️ Очищаем базу данных...")
            r.flushdb()  # Очищаем только текущую БД (db=10), не все базы
            print("✅ Redis база данных очищена")
        else:
            print("ℹ️ Redis база данных уже пуста")
            
        # Очищаем Celery очереди через API
        print("\n🧹 Очищаем Celery очереди через control API...")
        try:
            celery_app.control.purge()
            print("✅ Celery очереди очищены")
        except Exception as e:
            print(f"⚠️ Не удалось очистить через control API: {e}")
            print("   Пробуем через командную строку...")
            import subprocess
            result = subprocess.run(
                ['celery', '-A', 'celery_app', 'purge', '-f'], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print("✅ Celery очереди очищены через CLI")
                if result.stdout:
                    print(result.stdout)
            else:
                print(f"⚠️ Предупреждения: {result.stderr}")
                
        # Останавливаем активные задачи
        print("\n🛑 Останавливаем активные задачи...")
        try:
            celery_app.control.discard_all()
            print("✅ Активные задачи отменены")
        except Exception as e:
            print(f"⚠️ Ошибка отмены задач: {e}")
            
        print("\n✅ Очистка завершена успешно!")
        print("\n💡 Рекомендация: перезапустите Celery worker'ы:")
        print("   celery -A celery_app worker --loglevel=info")
            
    except redis.ConnectionError as e:
        print(f"❌ Ошибка подключения к Redis: {e}")
        print(f"\n🔍 Проверьте:")
        print(f"   1. Запущен ли Docker контейнер с Redis")
        print(f"   2. Доступен ли порт {REDIS_PORT}")
        print(f"   3. Правильный ли пароль: {REDIS_PASSWORD[:3]}***")
        print(f"\n📝 Команды для проверки Docker:")
        print(f"   docker ps | grep redis")
        print(f"   docker logs <container_id>")
    except redis.AuthenticationError:
        print("❌ Ошибка аутентификации Redis. Проверьте пароль в celery_config.py")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    clear_redis() 