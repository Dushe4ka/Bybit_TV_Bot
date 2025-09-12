from pybit.unified_trading import HTTP
from logger_config import setup_logger
from config import API_KEY, API_SECRET
import asyncio
import time
from typing import Dict, Optional, Callable
import threading

logger = setup_logger(__name__)

class PositionMonitor:
    """Класс для мониторинга позиций и управления состоянием сделок"""
    
    def __init__(self):
        self.session = HTTP(api_key=API_KEY, api_secret=API_SECRET, testnet=False)
        self.active_positions: Dict[str, Dict] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.stop_callbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
    
    def add_position(self, symbol: str, entry_price: float, qty: float, side: str = "Sell"):
        """Добавляет позицию для мониторинга"""
        with self._lock:
            self.active_positions[symbol] = {
                'entry_price': entry_price,
                'qty': qty,
                'side': side,
                'status': 'open',
                'last_check': time.time()
            }
            logger.info(f"[PositionMonitor] Добавлена позиция для мониторинга: {symbol}")
    
    def remove_position(self, symbol: str):
        """Удаляет позицию из мониторинга"""
        with self._lock:
            if symbol in self.active_positions:
                del self.active_positions[symbol]
                logger.info(f"[PositionMonitor] Позиция удалена из мониторинга: {symbol}")
    
    def set_stop_callback(self, symbol: str, callback: Callable):
        """Устанавливает callback для остановки мониторинга"""
        self.stop_callbacks[symbol] = callback
    
    async def check_position_status(self, symbol: str) -> bool:
        """Проверяет статус позиции через API Bybit"""
        try:
            response = self.session.get_positions(
                category="linear",
                symbol=symbol
            )
            
            if response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                for position in positions:
                    if position.get("symbol") == symbol:
                        qty = float(position.get("size", 0))
                        if qty == 0:
                            logger.info(f"[PositionMonitor] Позиция {symbol} закрыта (qty=0)")
                            return False
                        else:
                            # Обновляем информацию о позиции
                            with self._lock:
                                if symbol in self.active_positions:
                                    self.active_positions[symbol]['qty'] = qty
                                    self.active_positions[symbol]['last_check'] = time.time()
                            return True
            return False
        except Exception as e:
            logger.error(f"[PositionMonitor] Ошибка при проверке позиции {symbol}: {e}")
            return True  # В случае ошибки считаем позицию открытой
    
    async def monitor_position(self, symbol: str):
        """Мониторит позицию и вызывает callback при закрытии"""
        logger.info(f"[PositionMonitor] Начинаем мониторинг позиции: {symbol}")
        
        while True:
            try:
                # Проверяем статус позиции
                is_open = await self.check_position_status(symbol)
                
                if not is_open:
                    logger.info(f"[PositionMonitor] Позиция {symbol} закрыта, останавливаем мониторинг")
                    
                    # Вызываем callback для остановки
                    if symbol in self.stop_callbacks:
                        try:
                            self.stop_callbacks[symbol]()
                        except Exception as e:
                            logger.error(f"[PositionMonitor] Ошибка в callback для {symbol}: {e}")
                    
                    # Удаляем из мониторинга
                    self.remove_position(symbol)
                    break
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(5)  # Проверяем каждые 5 секунд
                
            except asyncio.CancelledError:
                logger.info(f"[PositionMonitor] Мониторинг позиции {symbol} отменен")
                break
            except Exception as e:
                logger.error(f"[PositionMonitor] Ошибка в мониторинге позиции {symbol}: {e}")
                await asyncio.sleep(10)  # При ошибке ждем дольше
    
    def start_monitoring(self, symbol: str, loop: asyncio.AbstractEventLoop):
        """Запускает мониторинг позиции в отдельной задаче"""
        if symbol in self.monitoring_tasks:
            logger.warning(f"[PositionMonitor] Мониторинг для {symbol} уже запущен")
            return
        
        task = loop.create_task(self.monitor_position(symbol))
        self.monitoring_tasks[symbol] = task
        logger.info(f"[PositionMonitor] Запущен мониторинг позиции: {symbol}")
    
    def stop_monitoring(self, symbol: str):
        """Останавливает мониторинг позиции"""
        if symbol in self.monitoring_tasks:
            task = self.monitoring_tasks[symbol]
            task.cancel()
            del self.monitoring_tasks[symbol]
            logger.info(f"[PositionMonitor] Остановлен мониторинг позиции: {symbol}")
    
    def get_active_positions(self) -> Dict[str, Dict]:
        """Возвращает список активных позиций"""
        with self._lock:
            return self.active_positions.copy()
    
    def is_position_open(self, symbol: str) -> bool:
        """Проверяет, открыта ли позиция для символа"""
        with self._lock:
            return symbol in self.active_positions

# Глобальный экземпляр монитора позиций
position_monitor = PositionMonitor() 