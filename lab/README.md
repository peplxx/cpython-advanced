# Lab: Bounded Buffer (Producer-Consumer)

Реализация классической задачи bounded buffer двумя способами:

- **`ConditionBoundedBuffer`** — `threading.Condition` + `deque`
- **`SemaphoreBoundedBuffer`** — два `threading.Semaphore` (empty + full) + `Lock` + `deque`

## Структура

```
lab/
├── bounded_buffer.py    # обе реализации
├── benchmark.py         # throughput sweep (producers × consumers × capacity)
├── strace_bench.py      # подсчёт futex syscalls (Linux only)
├── tests/               # корректность: FIFO, no-loss, capacity не превышена
└── results/             # JSON-результаты по версиям CPython
```

## Методология

Параметры (см. `proposal.md` → "Лабораторная работа"):

- **total items**: 1 000 000 (по умолчанию)
- **producers**: 1, 2, 4
- **consumers**: 1, 2, 4
- **capacity**: 1, 10, 100
- **runs per scenario**: 5, метрика — медиана

Throughput = `items / median_wall_clock_time`.

## Запуск

Sweep на текущем интерпретаторе:

```bash
python -m lab.benchmark --output lab/results/benchmark_local.json
```

Sweep по всем версиям CPython (через nox из директории `lab/`):

```bash
cd lab && nox -s benchmark
```

Подсчёт futex syscalls (Linux):

```bash
cd lab && nox -s strace
```

Корректность:

```bash
cd lab && nox -s tests
```

## Ожидаемое наблюдение

На `python3.13t` (free-threading) futex-вызовов будет **больше**, чем на `python3.13` с GIL, — потому что без GIL потоки реально работают параллельно и чаще вступают в contention на Condition/Semaphore. Это цена настоящего параллелизма, а не регресс.
