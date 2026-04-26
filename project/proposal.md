# Примитивы синхронизации в Python, CPython и Linux

**Автор:** Сергей Мельников

**Курс:** CPython Advanced

---

## Цель

Примитивы синхронизации в Python выглядят просто, но за `Lock()` скрыта цепочка: Python → CPython C-код → pthread / `_PyParkingLot` → futex → ядро Linux. Цель проекта — пройти эту цепочку насквозь: разобрать каждый слой, показать реальное поведение через эксперименты и понять, как всё меняется в free-threading сборке (Python 3.13+).

---

## Теория

### Python-уровень

Модуль `threading` предоставляет шесть примитивов: `Lock`, `RLock`, `Condition`, `Semaphore`, `Event`, `Barrier` (плюс `BoundedSemaphore` как отдельный класс) — и `queue.Queue` как готовую thread-safe структуру поверх них. Разбираем семантику каждого, типичные паттерны и типичные ошибки: deadlock, spurious wakeup, неправильный выбор примитива.

### CPython-уровень

**GIL** реализован не как простой mutex, а как custom lock на основе `pthread_mutex_t` + `pthread_cond_t` в `ceval_gil.c`. Механизм переключения работает так: поток, ожидающий GIL, делает `pthread_cond_timedwait()` с таймаутом 5 мс. Если за это время GIL не освобождён, ожидающий поток выставляет флаг `gil_drop_request`; текущий владелец проверяет `eval_breaker` на границах инструкций и вызывает `drop_gil()`. GIL защищает внутренние структуры интерпретатора, но не пользовательские данные.

**`threading.Lock`** — это `struct lockobject` из `Modules/_threadmodule.c`, внутри которого `PyThread_type_lock` — платформозависимый тип. На Linux (CPython 3.12) цепочка вызовов выглядит так:

```
threading.Lock().acquire()
  → lock_PyThread_acquire_lock()          # Modules/_threadmodule.c
    → PyThread_acquire_lock_timed()       # Python/thread_pthread.h
      → sem_timedwait() / pthread_cond_timedwait()
        → futex(FUTEX_WAIT)              # при contention
```

В CPython 3.13t `threading.Lock` перешёл на новый механизм:

```
threading.Lock().acquire()
  → PyMutex_Lock()                        # Python/lock.c
    → _PyParkingLot_Park()                # Python/parking_lot.c
      → futex(FUTEX_WAIT)
```

### Linux-уровень

futex (Linux 2.6, 2003) — ключевой примитив ядра. При отсутствии конкуренции блокировка происходит полностью в userspace через атомарный CAS, без syscall. Только при конкуренции поток вызывает `FUTEX_WAIT` и уходит в сон; разбудивший поток вызывает `FUTEX_WAKE`. `pthread_mutex_t` в glibc реализован поверх той же логики, как и `_PyParkingLot` в CPython 3.13t.

Реальное поведение можно наблюдать через `strace -e trace=futex`: при uncontended lock futex-вызовов не будет вовсе.

### Free-threading (PEP 703, Python 3.13+)

Сборка `python3.13t` убирает GIL и вводит несколько ключевых механизмов:

- **Per-object mutex** — `ob_mutex` (`PyMutex`, 1 байт) на каждом объекте
- **Biased reference counting** — локальный счётчик ссылок без атомарных операций в common case
- **Deferred reference counting** — для immortal и часто используемых объектов
- **`_PyParkingLot`** — механизм ожидания поверх futex, заменяющий pthread_cond
- **Critical sections** (`Py_BEGIN_CRITICAL_SECTION`) — per-object locking с deadlock avoidance вместо глобального lock ordering

CPU-bound потоки впервые становятся по-настоящему параллельными. При этом отдельные операции над встроенными контейнерами (`list.append()`, `dict.__getitem__()`) остаются потокобезопасными — они защищены critical sections внутри CPython. Опасность в другом: составные операции (итерация с модификацией), которые раньше «случайно» работали из-за GIL, в 3.13t могут содержать race condition.

---

## Практика

Все эксперименты — воспроизводимый код в репозитории.

1. **Race condition** на счётчике — с lock и без, визуализация порядка операций
2. **Deadlock** — классический сценарий с двумя `RLock`, решение через lock ordering
3. **strace на Lock** — uncontended vs contended: при uncontended CAS происходит в userspace, futex-вызовов нет. При contention CPython 3.12 на Linux покажет `futex(FUTEX_WAIT_BITSET)` (через `sem_timedwait()`), а 3.13t — `futex(FUTEX_WAIT)` через `_PyParkingLot`. Разница в системных вызовах сама по себе показательна.
4. **GIL benchmark** — CPU-bound задача: 1 vs 4 потока на Python 3.12 и 3.13t
5. **Сравнение уровней** — `threading.Lock` vs `asyncio.Lock` vs `multiprocessing.Lock`. Ключевое наблюдение: `asyncio.Lock` не использует никаких системных примитивов — это чисто Python-уровневая структура на `collections.deque` + `Future`. Сравнение "на уровне ОС" для неё бессмысленно, и именно это стоит показать студентам явно.

---

## Лабораторная работа

**Bounded buffer (producer-consumer)** — реализовать двумя способами: через `threading.Condition` и через два `Semaphore` (empty + full).

**Методология замеров.** Фиксированное количество items (например, 1 000 000), варьируемые параметры: число producers (1, 2, 4), consumers (1, 2, 4), размер буфера (1, 10, 100). Throughput считается как `items / wall_clock_time`. Каждый сценарий прогоняется минимум 5 раз, берётся медиана.

**Подсчёт futex-вызовов** через `strace -c -e trace=futex`. Важное контринтуитивное наблюдение: на 3.13t futex-вызовов будет *больше*, чем на 3.12 — потому что без GIL потоки действительно работают параллельно и чаще вступают в реальный contention на Condition/Semaphore. Студентам важно понять: больше syscalls ≠ хуже, это цена настоящего параллелизма.
---

## Источники

- [PEP 703 — Making the GIL Optional](https://peps.python.org/pep-0703/)
- [py-free-threading.github.io](https://py-free-threading.github.io/) — porting guide, совместимость пакетов, debugging
- [Python threading docs](https://docs.python.org/3/library/threading.html)
- [CPython: `Python/ceval_gil.c`](https://github.com/python/cpython/blob/main/Python/ceval_gil.c)
- [CPython: `Python/thread_pthread.h`](https://github.com/python/cpython/blob/main/Python/thread_pthread.h)
- [CPython: `Python/lock.c`](https://github.com/python/cpython/blob/main/Python/lock.c)
- [CPython: `Python/parking_lot.c`](https://github.com/python/cpython/blob/main/Python/parking_lot.c)
- [CPython: `Include/internal/pycore_lock.h`](https://github.com/python/cpython/blob/main/Include/internal/pycore_lock.h)
- [Ulrich Drepper, "Futexes Are Tricky"](https://dept-info.labri.fr/~denis/Enseignement/2008-IR/Articles/01-futex.pdf)
- `man 7 futex`
