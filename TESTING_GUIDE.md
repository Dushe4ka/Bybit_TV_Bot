# Руководство по тестированию торговой системы

## 🚀 Быстрый старт

### 1. Запуск сервисов
```bash
# Запуск FastAPI сервера
python3 fastapi_server.py

# Запуск Celery worker (в отдельном терминале)
celery -A celery_app worker --loglevel=info

# Запуск Telegram bot (в отдельном терминале)
python3 bot.py
```

### 2. Очистка отложенных задач
```bash
# Очистка Celery очередей
celery -A celery_app purge

# Очистка Redis (если установлен redis-tools)
redis-cli FLUSHALL

# Или используйте наш скрипт
python3 clear_redis.py
```

### 3. Тестирование вебхуков

#### Доступные символы для тестирования:
- ✅ **BTCUSDT** - Bitcoin
- ✅ **ETHUSDT** - Ethereum  
- ✅ **SOLUSDT** - Solana
- ✅ **ADAUSDT** - Cardano
- ✅ **DOTUSDT** - Polkadot
- ✅ **LINKUSDT** - Chainlink
- ✅ **MATICUSDT** - Polygon
- ✅ **AVAXUSDT** - Avalanche

#### Примеры запросов:
```bash
# Тест с BTC
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "BTCUSDT"}'

# Тест с ETH
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "ETHUSDT"}'

# Тест с SOL
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "SOLUSDT"}'
```

## ⚠️ Важные замечания

### Символы, которые НЕ работают:
- ❌ **XRPUSDT** - не найден в линейных фьючерсах Bybit
- ❌ **SOLUSDT.P** - неправильный формат (должно быть SOLUSDT)
- ❌ Любые символы с суффиксами (.P, .PERP и т.д.)

### Исправленные проблемы:
1. ✅ **Event loop is closed** - исправлено в `celery_app/tasks/bybit_tasks.py`
2. ✅ **Symbol invalid** - исправлено очисткой символов от кавычек
3. ✅ **ModuleNotFoundError** - исправлено настройкой Python пакетов

## 📊 Мониторинг

### Проверка логов:
```bash
# Логи Celery
tail -f logs/celery.log

# Логи FastAPI
tail -f logs/fastapi.log
```

### Проверка статуса:
```bash
# Проверка здоровья сервера
curl http://localhost:8000/health

# Проверка доступных символов
python3 check_symbols.py
```

## 🔧 Устранение неполадок

### Если задачи не выполняются:
1. Очистите Redis: `python3 clear_redis.py`
2. Перезапустите Celery worker
3. Проверьте логи на ошибки

### Если символ не найден:
1. Проверьте правильность символа: `python3 check_symbols.py`
2. Убедитесь, что символ в формате SYMBOLUSDT
3. Проверьте, что символ торгуется в линейных фьючерсах

### Если сервер не отвечает:
1. Проверьте, что FastAPI запущен: `ps aux | grep fastapi`
2. Перезапустите сервер: `python3 fastapi_server.py`
3. Проверьте порт 8000: `ss -tlnp | grep :8000` 