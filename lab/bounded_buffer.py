"""Bounded buffer (producer-consumer): two implementations.

- ConditionBoundedBuffer: single `threading.Condition` protecting a deque.
- SemaphoreBoundedBuffer:  `empty` + `full` semaphores plus a `Lock` for the deque.

Both expose the same `put(item)` / `get()` API.
"""

import collections
import threading


class ConditionBoundedBuffer:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._buf: collections.deque = collections.deque()
        self._cond = threading.Condition()

    def put(self, item) -> None:
        with self._cond:
            while len(self._buf) >= self.capacity:
                self._cond.wait()
            self._buf.append(item)
            self._cond.notify()

    def get(self):
        with self._cond:
            while not self._buf:
                self._cond.wait()
            item = self._buf.popleft()
            self._cond.notify()
            return item


class SemaphoreBoundedBuffer:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._buf: collections.deque = collections.deque()
        self._mutex = threading.Lock()
        self._empty = threading.Semaphore(capacity)
        self._full  = threading.Semaphore(0)

    def put(self, item) -> None:
        self._empty.acquire()
        with self._mutex:
            self._buf.append(item)
        self._full.release()

    def get(self):
        self._full.acquire()
        with self._mutex:
            item = self._buf.popleft()
        self._empty.release()
        return item


IMPLS = {
    "condition": ConditionBoundedBuffer,
    "semaphore": SemaphoreBoundedBuffer,
}
