#!/usr/bin/env python3
"""
Скрипт для остановки всех Celery worker'ов
"""
from celery_app import celery_app
import sys

def stop_workers():
    """Останавливает все активные Celery worker'ы"""
    try:
        print("🛑 Останавливаем все Celery worker'ы...")
        
        # Пробуем получить статистику worker'ов
        try:
            stats = celery_app.control.inspect().stats()
            if stats:
                print(f"\n📊 Найдено активных worker'ов: {len(stats)}")
                for worker_name in stats.keys():
                    print(f"   - {worker_name}")
            else:
                print("ℹ️ Активные worker'ы не найдены")
                return
        except Exception as e:
            print(f"⚠️ Не удалось получить список worker'ов: {e}")
            print("   Пытаемся остановить в любом случае...")
        
        # Останавливаем всех worker'ов
        print("\n🛑 Отправляем команду shutdown...")
        celery_app.control.shutdown()
        print("✅ Команда на остановку отправлена!")
        
        print("\n⏳ Ожидайте несколько секунд для корректного завершения worker'ов...")
        print("\n💡 Если worker'ы не остановились, используйте принудительное завершение:")
        print("   Windows: taskkill /F /IM celery.exe")
        print("   Linux:   pkill -9 -f 'celery worker'")
        
    except Exception as e:
        print(f"❌ Ошибка при остановке worker'ов: {e}")
        print("\n💡 Попробуйте через командную строку:")
        print("   celery -A celery_app control shutdown")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def show_active_tasks():
    """Показывает активные задачи"""
    try:
        print("\n📋 Проверяем активные задачи...")
        
        i = celery_app.control.inspect()
        
        # Активные задачи
        active = i.active()
        if active:
            print("\n🔄 Активные задачи:")
            for worker, tasks in active.items():
                if tasks:
                    print(f"\n  Worker: {worker}")
                    for task in tasks:
                        print(f"    - {task.get('name')} (ID: {task.get('id')})")
        else:
            print("   Нет активных задач")
        
        # Зарезервированные задачи
        reserved = i.reserved()
        if reserved:
            print("\n📌 Зарезервированные задачи:")
            for worker, tasks in reserved.items():
                if tasks:
                    print(f"\n  Worker: {worker}")
                    for task in tasks:
                        print(f"    - {task.get('name')} (ID: {task.get('id')})")
        else:
            print("   Нет зарезервированных задач")
            
    except Exception as e:
        print(f"⚠️ Не удалось получить информацию о задачах: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🛑 ОСТАНОВКА CELERY WORKER'ОВ")
    print("=" * 60)
    
    # Показываем активные задачи
    show_active_tasks()
    
    # Спрашиваем подтверждение
    if len(sys.argv) > 1 and sys.argv[1] == '-f':
        # Принудительная остановка без подтверждения
        stop_workers()
    else:
        print("\n⚠️ Это остановит все активные worker'ы и прервет выполняющиеся задачи!")
        response = input("Продолжить? (yes/no): ").strip().lower()
        if response in ['yes', 'y', 'да', 'д']:
            stop_workers()
        else:
            print("❌ Операция отменена")
            sys.exit(0)


