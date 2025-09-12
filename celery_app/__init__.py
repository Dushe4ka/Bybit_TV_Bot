from celery import Celery

# Создаем экземпляр Celery
celery_app = Celery('bybit_trading')

# Загружаем конфигурацию
celery_app.config_from_object('celery_app.celery_config')

# Автодискавери задач
celery_app.autodiscover_tasks(['celery_app.tasks'])

# Экспортируем для использования в других модулях
__all__ = ['celery_app'] 