from __future__ import annotations

import os
import time
from typing import Dict, Any

import psutil

class GreenSystemTracker:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = 0.0
        self.start_cpu = 0.0
        self.peak_rss = 0

    def start(self) -> None:
        self.start_time = time.perf_counter()
        self.start_cpu = self.process.cpu_times().user + self.process.cpu_times().system
        self.peak_rss = self.process.memory_info().rss

    def sample(self) -> None:
        rss = self.process.memory_info().rss
        if rss > self.peak_rss:
            self.peak_rss = rss

    def stop(self) -> Dict[str, Any]:
        end_cpu = self.process.cpu_times().user + self.process.cpu_times().system
        cpu_time = end_cpu - self.start_cpu

        rss = self.process.memory_info().rss
        if rss > self.peak_rss:
            self.peak_rss = rss

        return {
            "cpu_time_s": round(cpu_time, 3),
            "memory_mb": round(rss / (1024 * 1024), 2),
            "peak_memory_mb": round(self.peak_rss / (1024 * 1024), 2),
            "cpu_percent": psutil.cpu_percent(interval=0.1)
        }