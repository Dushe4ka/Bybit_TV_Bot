# Bybit ScalpBot — Автоматизация торговли по сигналам TradingView

## Описание

**Bybit ScalpBot** — это система для автоматической торговли на бирже Bybit по сигналам, поступающим из TradingView через вебхуки.  
Бот реализует различные стратегии шорт-усреднения с управлением рисками, полностью автоматизирует открытие, сопровождение и закрытие сделок, а также уведомляет пользователей в Telegram и сохраняет историю сделок в MongoDB.

### Основные возможности

- **Приём сигналов из TradingView** через публичный FastAPI сервер (webhook).
- **Автоматический парсинг сигналов** и определение типа стратегии.
- **Множественные торговые стратегии** с разными параметрами риска.
- **Автоматический запуск торговой стратегии** по каждому сигналу (через Celery + Redis).
- **Мгновенный мониторинг цен** через WebSocket Bybit (реакция на рынке без задержек).
- **Система мониторинга позиций** - автоматическое завершение работы при закрытии позиции.
- **Управление рисками:** тейк-профит, стоп-лосс, усреднение.
- **Подробные уведомления в Telegram** для всех подписчиков.
- **Сохранение истории сделок** (результат, прибыль/убыток, параметры) в MongoDB.
- **Масштабируемая архитектура:** поддержка параллельных задач, масштабирование воркеров.
- **Автоматический проброс сервера в интернет через ngrok** (публичный URL для TradingView).

---

## Структура проекта

```
bybit/
  open_order_tekprofit_stoploss.py   # STRONG SHORT стратегия
  weak_short_strategy.py             # WEAK SHORT стратегия
  position_monitor.py                 # Система мониторинга позиций
celery_app/
  celery_config.py                   # Настройки Celery
  tasks/
    bybit_tasks.py                   # Задачи для запуска стратегий и управления мониторингом
utils/
  signal_parser.py                   # Парсинг сигналов и определение стратегий
  send_tg_message.py                 # Отправка сообщений в Telegram
config.py                            # Конфиги и токены
database.py                          # Работа с MongoDB
fastapi_server.py                    # FastAPI сервер (webhook, monitor, health, stop_monitoring, active_positions)
logger_config.py                     # Кастомный логгер
requirements.txt                     # Зависимости проекта
test_signal_parsing.py              # Тестовый скрипт для проверки парсинга сигналов
test_position_monitoring.py          # Тестовый скрипт для проверки мониторинга
```

---

### Новые возможности

#### Система парсинга сигналов

Обновлена система автоматического парсинга сигналов с улучшенной надежностью:

- **Надежный парсинг JSON** - автоматическое извлечение текста из JSON обертки
- **Поддержка символов с .P** - работа с ALUUSDT.P, BTCUSDT.P и другими
- **Код-ориентированный подход** - распознавание Code 1 и Code 2
- **Автоматический запуск** соответствующей стратегии

#### Множественные торговые стратегии

#### STRONG SHORT стратегия (Code 2 SHORT)
- **Тейк-профит:** 12% при открытии сделки, 7% после усреднения
- **Усреднение:** при росте на 10%
- **Стоп-лосс:** 15%
- **Таймер:** изменение тейк-профита на 7% через 12 часов если усреднение не сработало
- **Сигнал:** `'Heiusdt': STRONG SHORT signal!` или `'ALUUSDT.P: Code 2 SHORT signal!'`

#### WEAK SHORT стратегия (Code 1 SHORT)
- **Тейк-профит:** 7% при открытии сделки, 3% после усреднения
- **Усреднение:** при росте на 10%
- **Стоп-лосс:** 15%
- **Таймер:** изменение тейк-профита на 3% через 12 часов если усреднение не сработало
- **Сигнал:** `'BTCUSDT': WEAK SHORT signal!` или `'ALUUSDT.P: Code 1 SHORT signal!'`

#### Система таймеров для изменения тейк-профита

Добавлена система автоматического изменения тейк-профита через 12 часов:

- **Автоматическое изменение** тейк-профита если усреднение не сработало
- **Отмена таймера** при срабатывании усреднения
- **Уведомления в Telegram** о срабатывании таймера
- **Безопасная отмена** старых ордеров перед установкой новых

### Система мониторинга позиций

Добавлена система автоматического мониторинга позиций, которая:

- **Отслеживает состояние позиций** через API Bybit каждые 5 секунд
- **Автоматически завершает работу** при закрытии позиции (ручное закрытие или срабатывание TP/SL)
- **Предотвращает конфликты** между воркерами через изолированные event loops
- **Позволяет принудительно остановить** мониторинг через API

### Новые API эндпоинты

- `POST /webhook` - автоматический парсинг сигналов и запуск стратегии
- `POST /strong_short` - прямая запуск STRONG SHORT стратегии
- `POST /weak_short` - прямая запуск WEAK SHORT стратегии
- `POST /webhook_legacy` - легаси эндпоинт для обратной совместимости
- `POST /stop_monitoring` - принудительная остановка мониторинга
- `GET /active_positions` - получение списка активных позиций
- `GET /health` - проверка работоспособности сервера

### Валидация символов

Добавлена система валидации торговых пар:
- Проверка формата символов (SYMBOLUSDT)
- Блокировка недопустимых символов (с .P и др.)
- Автоматическая очистка от лишних символов

---

## Требования

- Python 3.9+
- Redis (для Celery)
- MongoDB
- Bybit API ключи (testnet или prod)
- Telegram Bot API токен
- TradingView (для отправки сигналов)
- [ngrok](https://ngrok.com/) (для проброса FastAPI сервера в интернет)

---

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone <your-repo-url>
   cd <project-folder>
   ```

2. **Создайте и активируйте виртуальное окружение:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   pip install pyngrok
   ```

4. **Настройте переменные окружения:**
   - Создайте файл `.env` и пропишите:
     ```
     API_KEY=ваш_bybit_api_key
     API_SECRET=ваш_bybit_api_secret
     TELEGRAM_BOT_TOKEN=ваш_telegram_bot_token
     MONGO_URI=mongodb://localhost:27017
     ```

5. **Запустите Redis и MongoDB** (если не запущены).

---

## Запуск проекта

### 1. Запустите Celery воркеры

```bash
celery -A celery_app.tasks.bybit_tasks worker --loglevel=info --config=celery_app.celery_config
```
- Для Windows: добавьте `-P solo`

### 2. Запустите FastAPI сервер

```bash
uvicorn fastapi_server:app --host 0.0.0.0 --port 8000
```

---

## Использование

### Автоматический парсинг сигналов

Отправьте сигнал на `/webhook`:

```bash
# STRONG SHORT сигнал (Code 2)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "ALUUSDT.P: Code 2 SHORT signal!"}'

# WEAK SHORT сигнал (Code 1)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "ALUUSDT.P: Code 1 SHORT signal!"}'

# Поддержка символов без .P
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "BTCUSDT: Code 2 SHORT signal!"}'

# Поддержка JSON форматов
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "ETHUSDT: Code 1 SHORT signal!"}'
```

### Прямые вызовы стратегий

```bash
# STRONG SHORT стратегия
curl -X POST http://localhost:8000/strong_short \
  -H "Content-Type: application/json" \
  -d '{"text": "BTCUSDT"}'

# WEAK SHORT стратегия
curl -X POST http://localhost:8000/weak_short \
  -H "Content-Type: application/json" \
  -d '{"text": "ETHUSDT"}'
```

### Легаси для обратной совместимости

```bash
curl -X POST http://localhost:8000/webhook_legacy \
  -H "Content-Type: application/json" \
  -d '{"text": "BTCUSDT"}'
```

---

## Тестирование

### Тест парсинга сигналов
```bash
python test_signal_parsing.py
```

### Тест мониторинга позиций
```bash
python test_position_monitoring.py
```

### Тест принудительного завершения
```bash
python test_position_closure.py
```

---

## Поддерживаемые сигналы

### Формат сигналов
- `SYMBOL: Code 2 SHORT signal!` - STRONG SHORT стратегия
- `SYMBOL: Code 1 SHORT signal!` - WEAK SHORT стратегия
- `{"text": "SYMBOL: Code 2 SHORT signal!"}` - STRONG SHORT стратегия (JSON формат)
- `{"text": "SYMBOL: Code 1 SHORT signal!"}` - WEAK SHORT стратегия (JSON формат)

### Поддерживаемые символы
- Стандартные символы: `BTCUSDT`, `ETHUSDT`, `ADAUSDT`
- Символы с .P: `ALUUSDT.P`, `BTCUSDT.P`, `ETHUSDT.P`

### Примеры валидных символов
- BTCUSDT, ETHUSDT, XRPUSDT
- ADAUSDT, DOTUSDT, LINKUSDT
- И другие стандартные пары Bybit

### Заблокированные символы
- Символы с `.P` (например, XRPUSDT.P)
- Неправильные форматы
- Пустые символы

---

## Логирование

Система ведет подробные логи:

```
[SignalParser] Распознан сигнал: символ=HEIUSDT, тип=STRONG_SHORT
[Bybit] Запуск STRONG SHORT стратегии для HEIUSDT
[PositionMonitor] Добавлена позиция для мониторинга: HEIUSDT
[StrongStrategy] Позиция HEIUSDT закрыта, завершаем работу стратегии
```

---

## Устранение неполадок

### Ошибка "Event loop is closed"
Решено через использование threading.local() для изоляции event loops

### Конфликты между воркерами
Предотвращены через изоляцию данных между потоками

### Невалидные символы
Обрабатываются через валидацию на уровне API

### Воркер не освобождается
Решено через принудительное завершение работы при закрытии позиции

---

## Конфигурация

### Настройки Celery
```python
worker_concurrency = 4  # Уменьшено для лучшей изоляции
worker_max_tasks_per_child = 50  # Перезапуск воркера после 50 задач
worker_disable_rate_limits = True  # Отключение rate limits
```

### Параметры стратегий

#### STRONG SHORT (Code 2 SHORT)
```python
TAKE_PROFIT_PERCENT = 12    # Тейк профит 12% при открытии сделки
TAKE_PROFIT_AFTER_AVG = 7   # Тейк профит 7% после усреднения
AVERAGING_PERCENT = 10      # Усреднение при росте на 10%
STOP_LOSS_PERCENT = 15      # Стоп лосс 15%
TIMER_HOURS = 12            # Таймер для изменения TP через 12 часов
```

#### WEAK SHORT (Code 1 SHORT)
```python
TAKE_PROFIT_PERCENT = 7     # Тейк профит 7% при открытии сделки
TAKE_PROFIT_AFTER_AVG = 3   # Тейк профит 3% после усреднения
AVERAGING_PERCENT = 10      # Усреднение при росте на 10%
STOP_LOSS_PERCENT = 15      # Стоп лосс 15%
TIMER_HOURS = 12            # Таймер для изменения TP через 12 часов
```

---

## Безопасность

- Все API ключи хранятся в переменных окружения
- Валидация всех входящих данных
- Логирование всех операций
- Изоляция между воркерами
- Таймауты для предотвращения зависания (1 час максимум) 