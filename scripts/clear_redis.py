#!/usr/bin/env python3
"""
Скрипт для очистки Redis от отложенных задач Celery
"""
import redis
import sys

def clear_redis():
    try:
        # Подключаемся к Redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Проверяем подключение
        r.ping()
        print("✅ Подключение к Redis успешно")
        
        # Получаем список всех ключей
        keys = r.keys('*')
        print(f"📊 Найдено ключей в Redis: {len(keys)}")
        
        if keys:
            print("🗑️ Очищаем все ключи...")
            r.flushall()
            print("✅ Redis очищен")
        else:
            print("ℹ️ Redis уже пуст")
            
        # Проверяем Celery очереди
        print("\n🧹 Очищаем Celery очереди...")
        import subprocess
        result = subprocess.run(['celery', '-A', 'celery_app', 'purge', '-f'], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("⚠️ Предупреждения:", result.stderr)
            
    except redis.ConnectionError:
        print("❌ Ошибка подключения к Redis. Убедитесь, что Redis запущен:")
        print("   sudo systemctl start redis-server")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    clear_redis() 