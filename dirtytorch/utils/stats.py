# short_desc: helper for calculating score and time, etc...
from dataclasses import dataclass
from typing import Optional, Union, Callable
from time import perf_counter


class Statistic:
    def __float__(self):
        return self.summarize()

    def __str__(self):
        return str(float(self))

    def __repr__(self):
        return str(self)

    def __add__(self, x):
        return self.append(x)


def add(x, y):
    return x + y


def prod(x, y):
    return x * y


@dataclass
class ReduceStatistic(Statistic):
    mode: Callable = add
    accumulate: Union[float, int, bool] = 0

    def summarize(self):
        return self.accumulate

    def append(self, x):
        self.accumulate = self.mode(self.accumulate, x)
        return self.accumulate


@dataclass
class MaxStatistic(Statistic):
    current: float = -1

    def append(self, x):
        if x > self.current:
            self.current = x
            return True
        else:
            return False

    def summarize(self):
        return self.current


@dataclass
class AverageStatistic(Statistic):
    acc: float = 0
    count: int = 0
    mean: Optional[float] = None

    def summarize(self):
        if self.count == 0:
            return self.mean
        self.mean = self.acc / self.count
        self.acc = 0
        self.count = 0
        return self.mean

    def append(self, x):
        self.acc += x
        self.count += 1


@dataclass
class TimerStatistic:
    stats: Statistic

    def summarize(self):
        return self.stats.summarize()

    def __enter__(self):
        self.start_time = perf_counter()

    def __exit__(self, *a):
        delta = perf_counter() - self.start_time
        self.stats.append(delta)


def TotalTimer():
    return TimerStatistic(ReduceStatistic(add))


def AverageTimer():
    return TimerStatistic(AverageStatistic())


@dataclass
class Benchmark:
    desc: str = "Time"
    print_function: Callable = print

    def __enter__(self):
        self.start_time = perf_counter()

    def __exit__(self, *a):
        end_time = perf_counter()
        delta = end_time - self.start_time
        self.print_function(f"{self.desc}: {delta:8f}(s)")
