from typing import Dict

class TimeTracker:
    def __init__(self):
        self.start_time: float = None
        self.total_pause_time: float = 0
        self.is_paused: bool = False
        self.pause_start_time: float = 0

    def start(self, current_time: float) -> None:
        self.start_time = current_time
        self.total_pause_time = 0
        self.is_paused = False

    def pause(self, current_time: float) -> None:
        if not self.is_paused:
            self.is_paused = True
            self.pause_start_time = current_time

    def resume(self, current_time: float) -> None:
        if self.is_paused:
            self.total_pause_time += current_time - self.pause_start_time
            self.is_paused = False

    def stop(self, current_time: float) -> Dict[str, float]:
        if self.is_paused:
            end_time = self.pause_start_time
        else:
            end_time = current_time

        total_time = end_time - self.start_time
        work_time = total_time - self.total_pause_time

        self.is_paused = True

        return {
            'start_time': self.start_time,
            'end_time': end_time,
            'total_pause_time': self.total_pause_time,
            'total_work_time': work_time
        }

    def is_running(self):
        if self.is_paused:
            return True
        else:
            return False

    def reset(self):
        self.__init__()
