import logging
from typing import Dict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TimeTracker:
    def __init__(self):
        self.start_time: float = 0
        self.total_pause_time: float = 0
        self.is_paused: bool = False
        self.pause_start_time: float = 0

    def start(self, current_time: float) -> None:
        self.start_time = current_time
        self.total_pause_time = 0
        self.is_paused = False
        logger.debug(f"Timer started at {self.start_time}")

    def pause(self, current_time: float) -> None:
        if not self.is_paused:
            self.is_paused = True
            self.pause_start_time = current_time
            logger.debug(f"Timer paused at {self.pause_start_time}")

    def resume(self, current_time: float) -> None:
        if self.is_paused:
            self.total_pause_time += current_time - self.pause_start_time
            self.is_paused = False
            logger.debug(f"Timer resumed. Total pause time: {self.total_pause_time}")

    def stop(self, current_time: float) -> Dict[str, float]:
        if self.is_paused:
            end_time = self.pause_start_time
        else:
            end_time = current_time

        total_time = end_time - self.start_time
        work_time = total_time - self.total_pause_time

        logger.debug(f"Timer stopped. Start: {self.start_time}, End: {end_time}, Total: {total_time}, Work: {work_time}")

        return {
            'start_time': self.start_time,
            'end_time': end_time,
            'total_pause_time': self.total_pause_time,
            'total_work_time': work_time
        }
