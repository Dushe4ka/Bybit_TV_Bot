# Скрипты управления Celery и Redis

Этот каталог содержит утилиты для управления Celery worker'ами и Redis.

## 📋 Доступные скрипты

### 1. `clear_redis.py` - Очистка Redis и Celery очередей

**Назначение**: Полная очистка Redis базы данных и всех задач Celery.

**Использование**:
```bash
python scripts/clear_redis.py
```

**Что делает**:
- ✅ Подключается к Redis (порт 14572, db=10)
- ✅ Показывает количество ключей
- ✅ Очищает базу данных Redis
- ✅ Очищает Celery очереди
- ✅ Отменяет все активные задачи

**Когда использовать**:
- Застряли задачи в очереди
- После изменения кода задач
- Нужен "чистый старт"

---

### 2. `stop_workers.py` - Остановка Celery worker'ов

**Назначение**: Корректная остановка всех активных Celery worker'ов.

**Использование**:
```bash
# С подтверждением
python scripts/stop_workers.py

# Без подтверждения (принудительно)
python scripts/stop_workers.py -f
```

**Что делает**:
- ✅ Показывает список активных worker'ов
- ✅ Показывает активные и зарезервированные задачи
- ✅ Отправляет команду shutdown всем worker'ам

**Когда использовать**:
- Перед обновлением кода
- Перед очисткой Redis
- При зависших worker'ах

---

## 🔧 Типичные сценарии использования

### Полная перезагрузка системы

```bash
# 1. Остановить worker'ы
python scripts/stop_workers.py -f

# 2. Очистить Redis и очереди
python scripts/clear_redis.py

# 3. Запустить worker'ы заново
celery -A celery_app worker --loglevel=info
```

### После изменения кода задач

```bash
# 1. Остановить worker'ы
python scripts/stop_workers.py -f

# 2. Запустить worker'ы заново
celery -A celery_app worker --loglevel=info
```

### Очистка застрявших задач (без остановки)

```bash
python scripts/clear_redis.py
```

---

## ⚙️ Подключение к Redis

**Параметры** (из `celery_app/celery_config.py`):
- **Host**: 127.0.0.1
- **Port**: 14572 (Docker)
- **Password**: Ollama12357985
- **Database**: 10

### Ручное подключение через redis-cli

```bash
# Подключение к Redis в Docker
redis-cli -h 127.0.0.1 -p 14572 -a Ollama12357985 -n 10

# Проверка ключей
KEYS *

# Очистка базы данных
FLUSHDB

# Очистка всех баз данных (осторожно!)
FLUSHALL
```

---

## 🐛 Решение проблем

### Worker'ы не останавливаются

**Windows**:
```powershell
tasklist | findstr celery
taskkill /F /IM celery.exe
```

**Linux/macOS**:
```bash
ps aux | grep celery
pkill -9 -f 'celery worker'
```

### Не удается подключиться к Redis

1. Проверьте, что Docker контейнер запущен:
```bash
docker ps | grep redis
```

2. Проверьте логи контейнера:
```bash
docker logs <container_id>
```

3. Проверьте порт:
```bash
netstat -an | grep 14572
```

### Задачи продолжают выполняться после очистки

1. Убедитесь, что worker'ы остановлены:
```bash
python scripts/stop_workers.py -f
```

2. Принудительно завершите процессы (см. выше)

3. Очистите Redis:
```bash
python scripts/clear_redis.py
```

---

## 📊 Мониторинг

### Проверка активных задач

```bash
celery -A celery_app inspect active
```

### Проверка зарезервированных задач

```bash
celery -A celery_app inspect reserved
```

### Статистика worker'ов

```bash
celery -A celery_app inspect stats
```

### Проверка подключенных worker'ов

```bash
celery -A celery_app inspect ping
```

---

## 🔐 Безопасность

⚠️ **Важно**: Пароль Redis хранится в открытом виде в скриптах для удобства разработки. 

Для production:
- Используйте переменные окружения
- Храните пароли в `.env` файле
- Не коммитьте пароли в репозиторий

---

## 📝 Дополнительная информация

- **Документация Celery**: https://docs.celeryq.dev/
- **Документация Redis**: https://redis.io/docs/
- **pybit**: https://github.com/bybit-exchange/pybit

