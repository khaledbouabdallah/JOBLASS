import threading


class ScraperControl:
    """
    Manages user control over scraper execution
    Allows pause, resume, and stop operations
    """

    def __init__(self):
        self._stop_flag = threading.Event()
        self._pause_flag = threading.Event()
        self._lock = threading.Lock()

    def stop(self):
        """Signal scraper to stop execution"""
        with self._lock:
            self._stop_flag.set()

    def pause(self):
        """Signal scraper to pause execution"""
        with self._lock:
            self._pause_flag.set()

    def resume(self):
        """Resume scraper execution"""
        with self._lock:
            self._pause_flag.clear()

    def is_stopped(self) -> bool:
        """Check if stop signal is active"""
        return self._stop_flag.is_set()

    def is_paused(self) -> bool:
        """Check if pause signal is active"""
        return self._pause_flag.is_set()

    def reset(self):
        """Reset all flags"""
        with self._lock:
            self._stop_flag.clear()
            self._pause_flag.clear()

    def wait_if_paused(self, check_interval: float = 0.1):
        """
        Block execution if paused, wait until resumed or stopped

        Args:
            check_interval: How often to check pause status (seconds)
        """
        while self.is_paused() and not self.is_stopped():
            threading.Event().wait(check_interval)

    def check_should_stop(self):
        """Raise exception if stop signal is active"""
        if self.is_stopped():
            raise InterruptedError("User stopped the scraper")


# Global control instance
control = ScraperControl()
