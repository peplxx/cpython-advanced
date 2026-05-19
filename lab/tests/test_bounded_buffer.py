"""Correctness checks for both bounded-buffer implementations."""

import threading

import pytest

from lab.bounded_buffer import ConditionBoundedBuffer, SemaphoreBoundedBuffer

IMPLS = [ConditionBoundedBuffer, SemaphoreBoundedBuffer]


@pytest.mark.parametrize("impl_cls", IMPLS)
def test_single_thread_fifo(impl_cls):
    buf = impl_cls(3)
    for i in range(3):
        buf.put(i)
    assert [buf.get() for _ in range(3)] == [0, 1, 2]


@pytest.mark.parametrize("impl_cls", IMPLS)
def test_no_items_lost(impl_cls):
    buf = impl_cls(10)
    total = 5_000
    producers = 4
    consumers = 4

    sent = list(range(total))
    received: list[int] = []
    lock = threading.Lock()

    def producer(chunk):
        for x in chunk:
            buf.put(x)

    def consumer():
        while True:
            x = buf.get()
            if x is None:
                return
            with lock:
                received.append(x)

    chunk_size = total // producers
    chunks = [sent[i*chunk_size:(i+1)*chunk_size] for i in range(producers)]

    cs = [threading.Thread(target=consumer) for _ in range(consumers)]
    ps = [threading.Thread(target=producer, args=(c,)) for c in chunks]

    for t in cs: t.start()
    for t in ps: t.start()
    for t in ps: t.join()
    for _ in cs: buf.put(None)
    for t in cs: t.join()

    assert sorted(received) == sent


@pytest.mark.parametrize("impl_cls", IMPLS)
def test_capacity_never_exceeded(impl_cls):
    buf = impl_cls(2)
    sizes: list[int] = []
    lock = threading.Lock()

    orig_put = buf.put
    def tracking_put(item):
        orig_put(item)
        with lock:
            sizes.append(len(buf._buf))
    buf.put = tracking_put

    def producer():
        for i in range(500):
            buf.put(i)

    def consumer():
        for _ in range(500):
            buf.get()

    p = threading.Thread(target=producer)
    c = threading.Thread(target=consumer)
    p.start(); c.start()
    p.join();  c.join()

    assert max(sizes) <= 2
