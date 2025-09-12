from celery.schedules import crontab
import platform

# Настройки брокера и бэкенда
broker_url = 'redis://:Ollama12357985@127.0.0.1:14572/0'
result_backend = 'redis://:Ollama12357985@127.0.0.1:14572/0'

# Настройки задач
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'Europe/Moscow'
enable_utc = True

# Настройки для Windows
if platform.system() == 'Windows':
    worker_pool = 'solo'  # Используем solo пул для Windows
else:
    worker_pool = 'prefork'  # Используем prefork пул для Linux/Mac

worker_concurrency = 30  # Уменьшаем количество воркеров для лучшей изоляции
worker_prefetch_multiplier = 1  # Каждый воркер берет по одной задаче
worker_max_tasks_per_child = 50  # Перезапуск воркера после 50 задач
worker_max_memory_per_child = 150000  # Перезапуск воркера при превышении памяти (в КБ)

# Настройки логирования
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Включаем автодискавери задач
imports = (
    'celery_app.tasks.bybit_tasks',
)

# Дополнительные настройки для отладки
task_track_started = True
task_time_limit = 3600  # Максимальное время выполнения задачи (1 час)
task_soft_time_limit = 3000  # Мягкое ограничение времени (50 минут)
task_acks_late = True  # Подтверждение задачи только после выполнения
task_reject_on_worker_lost = True  # Отклонение задачи при потере воркера

# Настройки для изоляции воркеров
worker_disable_rate_limits = True  # Отключаем rate limits для лучшей производительности
worker_enable_remote_control = False  # Отключаем remote control для безопасности 