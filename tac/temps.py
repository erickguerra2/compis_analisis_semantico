from __future__ import annotations

import heapq

from .quad import Temp


class TempPool:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._next = 0
        self._free: list[int] = []
        self._live: set[int] = set()
        self.maximum = 0

    def acquire(self) -> Temp:
        number = heapq.heappop(self._free) if self._free else self._allocate()
        self._live.add(number)
        self.maximum = max(self.maximum, len(self._live))
        return Temp(number)

    def _allocate(self) -> int:
        number = self._next
        self._next += 1
        return number

    def release(self, temp: Temp) -> None:
        if temp.id in self._live:
            self._live.remove(temp.id)
            heapq.heappush(self._free, temp.id)

    def live(self) -> int:
        return len(self._live)
