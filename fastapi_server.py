from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from contextlib import asynccontextmanager
from celery_app.tasks.bybit_tasks import (
    run_strategy_by_signal, 
    run_short_strategy, 
    run_strong_short_strategy, 
    run_weak_short_strategy,
    run_short_averaging_strategy_task,
    stop_strategy_monitoring, 
    get_active_positions
)
from utils.send_tg_message import send_message_to_telegram
from utils.signal_parser import process_signal
from database import get_all_subscribed_users
from config import TELEGRAM_BOT_TOKEN, NGROK_TOKEN
import asyncio
import re
from logger_config import setup_logger

# Настройка logger
logger = setup_logger(__name__)

# Проверяем конфигурацию
if not TELEGRAM_BOT_TOKEN:
    logger.warning("[CONFIG] TELEGRAM_BOT_TOKEN не настроен в переменных окружения")

public_url = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global public_url
    # Попробовать запустить ngrok, если public_url не определён
    if public_url is None:
        try:
            from pyngrok import ngrok
            ngrok.set_auth_token(NGROK_TOKEN)
            ngrok_tunnel = ngrok.connect(9000, bind_tls=True)
            public_url = ngrok_tunnel.public_url
            logger.info(f"[NGROK] Сервер доступен по адресу: {public_url}")
        except Exception as e:
            logger.error(f"[NGROK] Ошибка при запуске ngrok: {e}")
            public_url = None
    # Получаем пользователей с обработкой ошибок
    try:
        users = await get_all_subscribed_users()
        logger.info(f"[STARTUP] Найдено {len(users)} подписанных пользователей")
    except Exception as e:
        logger.error(f"[STARTUP] Ошибка при получении пользователей из БД: {e}")
        users = []
    
    # Автоматическое определение эндпоинтов
    endpoints = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            if not route.path.startswith("/docs") and not route.path.startswith("/openapi") and not route.path.startswith("/redoc"):
                methods = ','.join(route.methods)
                if public_url:
                    endpoints.append(f"{public_url}{route.path} [{methods}]")
                else:
                    endpoints.append(f"/local{route.path} [{methods}]")
    
    if public_url:
        msg = (
            f"🚀 FastAPI сервер запущен!\n"
            f"Публичный адрес: {public_url}\n\n"
            f"Эндпоинты:\n" + '\n'.join(endpoints)
        )
    else:
        msg = (
            "⚠️ FastAPI сервер запущен, но публичный адрес недоступен (ngrok не запущен).\n"
            "Проверьте настройки ngrok!\n\n"
            f"Локальные эндпоинты:\n" + '\n'.join(endpoints)
        )
    
    # Отправляем уведомление с проверкой токена
    if TELEGRAM_BOT_TOKEN and users:
        try:
            await send_message_to_telegram(msg, users, TELEGRAM_BOT_TOKEN)
            logger.info(f"[STARTUP] Уведомление отправлено {len(users)} пользователям")
        except Exception as e:
            logger.error(f"[STARTUP] Ошибка при отправке уведомления в Telegram: {e}")
    else:
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("[STARTUP] TELEGRAM_BOT_TOKEN не настроен, уведомление не отправлено")
        if not users:
            logger.warning("[STARTUP] Нет подписанных пользователей, уведомление не отправлено")
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/monitor")
async def monitor(request: Request):
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        try:
            text = body.decode("utf-8").strip()
        except Exception:
            text = str(body)
        if text:
            data = {"text": text}
        else:
            logger.error("[MONITOR] Некорректный или пустой запрос")
            raise HTTPException(status_code=400, detail="Некорректный или пустой JSON/text")
    symbol = data.get('text') or data.get('ticker')
    logger.info(f"[MONITOR] Получен запрос: {data}")
    users = await get_all_subscribed_users()
    await send_message_to_telegram(f"MONITOR: {data}", users, TELEGRAM_BOT_TOKEN)
    logger.info(f"[MONITOR] Сообщение отправлено в Telegram подписчикам. Символ: {symbol}")
    return {"received": data, "symbol": symbol}

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        try:
            text = body.decode("utf-8").strip()
        except Exception:
            text = str(body)
        if text:
            data = {"text": text}
        else:
            logger.error("[WEBHOOK] Некорректный или пустой запрос")
            raise HTTPException(status_code=400, detail="Некорректный или пустой JSON/text")
    
    signal_text = data.get('text') or data.get('ticker')
    if signal_text:
        signal_text = signal_text.strip().strip("'\"")
    
    logger.info(f"[WEBHOOK] Получен вебхук: {data}")
    if not signal_text:
        logger.error("[WEBHOOK] Ошибка: не найден сигнал в payload (ожидался 'text' или 'ticker')")
        return {"error": "No signal in payload (expected 'text' or 'ticker')"}
    
    # Парсим сигнал для определения типа стратегии
    symbol, signal_type, strategy_function = process_signal(signal_text)
    
    if not symbol or not signal_type or not strategy_function:
        logger.error(f"[WEBHOOK] Не удалось обработать сигнал: {signal_text}")
        return {"error": f"Invalid signal format: {signal_text}"}
    
    # Запускаем стратегию на основе парсинга сигнала
    result = run_strategy_by_signal.delay(signal_text)
    logger.info(f"[WEBHOOK] Задача на запуск стратегии {strategy_function} для {symbol} отправлена в Celery")
    return {
        "status": "started", 
        "symbol": symbol, 
        "signal_type": signal_type,
        "strategy": strategy_function,
        "task_id": result.id
    }

@app.post("/webhook_legacy")
async def webhook_legacy(request: Request, background_tasks: BackgroundTasks):
    """Легаси эндпоинт для обратной совместимости"""
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        try:
            text = body.decode("utf-8").strip()
        except Exception:
            text = str(body)
        if text:
            data = {"text": text}
        else:
            logger.error("[WEBHOOK_LEGACY] Некорректный или пустой запрос")
            raise HTTPException(status_code=400, detail="Некорректный или пустой JSON/text")
    
    symbol = data.get('text') or data.get('ticker')
    if symbol:
        symbol = symbol.strip().strip("'\"")
    
    logger.info(f"[WEBHOOK_LEGACY] Получен вебхук: {data}")
    if not symbol:
        logger.error("[WEBHOOK_LEGACY] Ошибка: не найден символ в payload")
        return {"error": "No symbol in payload (expected 'text' or 'ticker')"}
    

    
    run_short_strategy.delay(symbol)
    logger.info(f"[WEBHOOK_LEGACY] Задача на запуск short_strategy для {symbol} отправлена в Celery")
    return {"status": "started", "symbol": symbol}

@app.post("/strong_short")
async def strong_short(request: Request):
    """Запускает STRONG SHORT стратегию"""
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        try:
            text = body.decode("utf-8").strip()
        except Exception:
            text = str(body)
        if text:
            data = {"text": text}
        else:
            logger.error("[STRONG_SHORT] Некорректный или пустой запрос")
            raise HTTPException(status_code=400, detail="Некорректный или пустой JSON/text")
    
    symbol = data.get('text') or data.get('ticker')
    if symbol:
        symbol = symbol.strip().strip("'\"")
    
    if not symbol:
        logger.error("[STRONG_SHORT] Ошибка: не найден символ в payload")
        return {"error": "No symbol in payload (expected 'text' or 'ticker')"}
    

    
    result = run_strong_short_strategy.delay(symbol)
    logger.info(f"[STRONG_SHORT] Задача на запуск STRONG SHORT стратегии для {symbol} отправлена в Celery")
    return {"status": "started", "symbol": symbol, "strategy": "strong_short", "task_id": result.id}

@app.post("/weak_short")
async def weak_short(request: Request):
    """Запускает WEAK SHORT стратегию"""
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        try:
            text = body.decode("utf-8").strip()
        except Exception:
            text = str(body)
        if text:
            data = {"text": text}
        else:
            logger.error("[WEAK_SHORT] Некорректный или пустой запрос")
            raise HTTPException(status_code=400, detail="Некорректный или пустой JSON/text")
    
    symbol = data.get('text') or data.get('ticker')
    if symbol:
        symbol = symbol.strip().strip("'\"")
    
    if not symbol:
        logger.error("[WEAK_SHORT] Ошибка: не найден символ в payload")
        return {"error": "No symbol in payload (expected 'text' or 'ticker')"}
    

    
    result = run_weak_short_strategy.delay(symbol)
    logger.info(f"[WEAK_SHORT] Задача на запуск WEAK SHORT стратегии для {symbol} отправлена в Celery")
    return {"status": "started", "symbol": symbol, "strategy": "weak_short", "task_id": result.id}

@app.post("/short_averaging")
async def short_averaging(request: Request):
    """Запускает SHORT стратегию с усреднением"""
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        try:
            text = body.decode("utf-8").strip()
        except Exception:
            text = str(body)
        if text:
            data = {"text": text}
        else:
            logger.error("[SHORT_AVERAGING] Некорректный или пустой запрос")
            raise HTTPException(status_code=400, detail="Некорректный или пустой JSON/text")
    
    symbol = data.get('text') or data.get('ticker') or data.get('symbol')
    if symbol:
        symbol = symbol.strip().strip("'\"")
    
    if not symbol:
        logger.error("[SHORT_AVERAGING] Ошибка: не найден символ в payload")
        return {"error": "No symbol in payload (expected 'text', 'ticker' or 'symbol')"}
    
    # Получаем параметры стратегии из запроса (или используем значения по умолчанию)
    usdt_amount = float(data.get('usdt_amount', 100))
    averaging_percent = float(data.get('averaging_percent', 10.0))
    initial_tp_percent = float(data.get('initial_tp_percent', 3.0))
    breakeven_step = float(data.get('breakeven_step', 2.0))
    stop_loss_percent = float(data.get('stop_loss_percent', 15.0))
    use_demo = data.get('use_demo', True)
    
    logger.info(
        f"[SHORT_AVERAGING] Запуск стратегии для {symbol} с параметрами: "
        f"USDT={usdt_amount}, Avg={averaging_percent}%, TP={initial_tp_percent}%, "
        f"BE={breakeven_step}%, SL={stop_loss_percent}%"
    )
    
    result = run_short_averaging_strategy_task.delay(
        symbol=symbol,
        usdt_amount=usdt_amount,
        averaging_percent=averaging_percent,
        initial_tp_percent=initial_tp_percent,
        breakeven_step=breakeven_step,
        stop_loss_percent=stop_loss_percent,
        use_demo=use_demo
    )
    
    logger.info(f"[SHORT_AVERAGING] Задача отправлена в Celery для {symbol}, task_id: {result.id}")
    return {
        "status": "started", 
        "symbol": symbol, 
        "strategy": "short_averaging",
        "task_id": result.id,
        "parameters": {
            "usdt_amount": usdt_amount,
            "averaging_percent": averaging_percent,
            "initial_tp_percent": initial_tp_percent,
            "breakeven_step": breakeven_step,
            "stop_loss_percent": stop_loss_percent,
            "use_demo": use_demo
        }
    }

@app.post("/stop_monitoring")
async def stop_monitoring(request: Request):
    """Останавливает мониторинг для указанного символа"""
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        try:
            text = body.decode("utf-8").strip()
        except Exception:
            text = str(body)
        if text:
            data = {"text": text}
        else:
            logger.error("[STOP_MONITORING] Некорректный или пустой запрос")
            raise HTTPException(status_code=400, detail="Некорректный или пустой JSON/text")
    
    symbol = data.get('text') or data.get('ticker')
    if symbol:
        symbol = symbol.strip().strip("'\"")
    
    if not symbol:
        logger.error("[STOP_MONITORING] Ошибка: не найден символ в payload")
        return {"error": "No symbol in payload (expected 'text' or 'ticker')"}
    

    
    result = stop_strategy_monitoring.delay(symbol)
    logger.info(f"[STOP_MONITORING] Задача на остановку мониторинга для {symbol} отправлена в Celery")
    return {"status": "stopping", "symbol": symbol, "task_id": result.id}

@app.get("/active_positions")
async def get_positions():
    """Возвращает список активных позиций"""
    result = get_active_positions.delay()
    logger.info("[ACTIVE_POSITIONS] Запрос на получение активных позиций отправлен в Celery")
    return {"status": "requested", "task_id": result.id}

@app.get("/health")
def health():
    logger.info("[HEALTH] Проверка работоспособности сервера FastAPI")
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    logger.info("[START] Запуск FastAPI сервера через uvicorn на 0.0.0.0:8000")
    uvicorn.run("fastapi_server:app", host="0.0.0.0", port=9000, reload=False)