# Remarks

Наблюдения и интерпретации, которые не очевидны из кода, но важны для понимания результатов.

---

## 01. Race Condition

**Главное наблюдение: GIL не защищает от гонок.**

Паттерн `read → sleep → write` не атомарен даже в CPython. `CONTEXT_SWITCH_DELAY = 0.001 s` искусственно форсирует переключение контекста между чтением и записью, гарантируя потерю обновлений.

| Случай                  | Результат       | Почему                                                           |
|-------------------------|-----------------|------------------------------------------------------------------|
| threading / unsafe      | < expected      | GIL отпускается на `time.sleep` — другой поток перезаписывает   |
| threading / safe        | == expected     | `with lock` делает всю тройку read-sleep-write атомарной         |
| processes / unsafe      | < expected      | Процессы реально параллельны, `Value(lock=False)` не защищает   |
| processes / safe        | == expected     | `multiprocessing.Lock` синхронизирует доступ к shared memory     |

**Почему GIL не помогает:** GIL защищает отдельные байткод-инструкции, но не последовательность операций. `time.sleep()` явно отпускает GIL — между `current = counter[0]` и `counter[0] = current + 1` другой поток успевает прочитать и записать то же значение.

**Multiprocessing:** `multiprocessing.Value` живёт в разделяемой памяти (`mmap`). Без `lock=True` или явного `Lock` процессы читают и пишут одновременно на уровне ОС — GIL тут вообще не при чём, у каждого процесса свой.

**Источники:**
- [Python GIL docs](https://docs.python.org/3/glossary.html#term-global-interpreter-lock) — GIL защищает объектную модель, не пользовательские критические секции
- [multiprocessing.Value](https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Value) — shared memory через `ctypes`

---

## 02. Deadlock

**Главное наблюдение: дедлок — детерминированное следствие циклической зависимости замков.**

**Почему `threading.Barrier` а не `time.sleep`:** `sleep` делает дедлок вероятным, но не гарантированным — при быстром CPU один поток может захватить оба замка до старта второго. `Barrier(N)` гарантирует, что все потоки держат свой первый замок *одновременно* перед попыткой захватить второй. Дедлок воспроизводится на 100%.

**Условия Коффмана:** все четыре выполняются одновременно:
1. **Mutual exclusion** — RLock может держать только один поток
2. **Hold-and-wait** — T1 держит A и ждёт B; T2 держит B и ждёт A
3. **No preemption** — замок нельзя отобрать
4. **Circular wait** — T1 → A → B → T1, T2 → B → A → T2

**Три потока (A→B, B→C, C→A):** цикл из трёх вершин — та же логика, только граф ожидания длиннее. Достаточно разорвать одно ребро (T3 берёт A перед C вместо C перед A).

**Фикс — глобальный порядок замков:** если все потоки захватывают замки в одном порядке (A < B < C), circular wait невозможен по определению — граф ожидания становится ациклическим DAG.

```
Дедлок:  T1: A→B,  T2: B→A      ← цикл
Фикс:    T1: A→B,  T2: A→B      ← нет цикла
```

**Источники:**
- [Coffman conditions — Wikipedia](https://en.wikipedia.org/wiki/Deadlock#Coffman_conditions)
- [threading.Barrier](https://docs.python.org/3/library/threading.html#threading.Barrier) — синхронизационная точка для N потоков

---

## 03. strace — uncontended vs contended

**Наблюдение:** Python 3.13t показывает наименьшую стоимость захвата при `threads=1` (~70 ns), но наибольшую при `threads=8` (~783 ns) — обгоняя даже 3.12.

**Почему:** В [proposal.md](proposal.md) сказано:

> на 3.13t futex-вызовов будет *больше*, чем на 3.12 — потому что без GIL потоки действительно работают параллельно и чаще вступают в реальный contention

Версии с GIL (3.12, 3.13) выглядят лучше при высокой конкуренции не потому, что их lock быстрее, а потому что GIL сам сериализует потоки ещё до того, как они добираются до пользовательского замка. Реального параллельного contention меньше → меньше futex-вызовов.

В 3.13t потоки работают по-настоящему параллельно → каждый захват замка сопровождается реальным `futex(FUTEX_WAIT)` / `FUTEX_WAKE` → latency растёт сильнее.

**Источники:**
- [PEP 703 — Making the GIL Optional](https://peps.python.org/pep-0703/) — описывает `_PyParkingLot` и почему per-object locking увеличивает реальный contention
- [Free threading HOWTO — Python docs](https://docs.python.org/3/howto/free-threading-python.html) — официальное руководство по free-threaded сборке

---

## 04. GIL benchmark

**Ожидаемое поведение:** 3.12 и 3.13 (с GIL) — плоские линии, 3.13t и 3.14t (без GIL) — убывающие кривые с ростом потоков.

**Неожиданное наблюдение:** Python 3.14 (с GIL) ведёт себя как free-threaded сборка — wall time падает с ~0.27s (1 поток) до ~0.06s (8 потоков), аналогично 3.14t.

**Гипотеза:** Python 3.14 включает экспериментальный JIT-компилятор. Горячий цикл `total += i * i` компилируется в нативный код, который может выполняться без удержания GIL или с существенно более коротким интервалом между его освобождениями — что и даёт эффект, похожий на параллелизм.

**Источники:**
- [PEP 744 — JIT Compilation](https://peps.python.org/pep-0744/) — описывает copy-and-patch JIT, добавленный в CPython 3.13+
- [What's New in Python 3.14](https://docs.python.org/3.14/whatsnew/3.14.html) — список изменений интерпретатора

---

## 05. Lock levels

Три примитива образуют чёткую иерархию стоимости (uncontended, 1 поток):

| Lock                   | ~ns/acquire | Уровень             |
|------------------------|-------------|---------------------|
| `threading.Lock`       | 52–96 ns    | userspace CAS       |
| `asyncio.Lock`         | 183–313 ns  | Python interpreter  |
| `multiprocessing.Lock` | 773–833 ns  | kernel semaphore    |

**Главное наблюдение: нет syscalls ≠ быстро.**
`asyncio.Lock` не делает ни одного syscall, но в 3–6 раз медленнее `threading.Lock` — вся стоимость это Python-уровень: `async/await` machinery, `collections.deque`, `Future`. Интерпретатор сам по себе дорог.

**`multiprocessing.Lock` почти не меняется между версиями Python** (~773–833 ns) — потому что стоимость определяется ядром (семафор), а не интерпретатором. Python здесь лишь тонкая обёртка.

**`threading.Lock` заметно ускорился** от 3.12/3.13 (~90–96 ns) до 3.14 (~52 ns) — улучшения в реализации замка на уровне CPython.

**Источники:**
- [asyncio.Lock source](https://github.com/python/cpython/blob/main/Lib/asyncio/locks.py) — реализация на `collections.deque` + `Future`, без единого syscall
- [threading.Lock (C)](https://github.com/python/cpython/blob/main/Modules/_threadmodule.c) — `PyThread_acquire_lock` → futex

---

## 05b. Lock Contention — масштабирование под нагрузкой

**Эксперимент:** каждый из трёх примитивов тестируется при 1–7 параллельных workers, результат — ns/acquire (wall-time лучшего worker'а / iterations).

### threading.Lock

- **GIL-версии (3.12, 3.13):** latency растёт умеренно — с ~80–100 ns при 1 worker до ~200–400 ns при 7. GIL сам сериализует потоки ещё до того, как они достигают lock: реального параллельного contention меньше → меньше `futex(FUTEX_WAIT)`.
- **Без GIL (3.13t, 3.14t):** кривая растёт агрессивнее — к 7 workers latency может достигать 600–900 ns. Потоки работают по-настоящему параллельно → каждый промах по lock вызывает `futex(FUTEX_WAIT)` в ядре.
- **3.14 / 3.14t заметно быстрее 3.12 / 3.13** при малом числе workers — улучшения в реализации `_PyParkingLot` и JIT снижают накладные расходы на стороне интерпретатора.

**Вывод:** без GIL threading.Lock раскрывает истинную стоимость ядерного futex при contention; GIL-версии «прячут» этот эффект.

### asyncio.Lock

- Практически не зависит от числа workers: кривая почти горизонтальна.
- Причина: asyncio — кооперативный однопоточный цикл событий. Никакого параллельного contention нет, «ожидание» это просто постановка корутины в очередь deque и возврат управления event loop — нет syscall, нет переключения контекста.
- Стоимость (~200–350 ns) определяется накладными расходами Python-уровня (`async/await`, `Future.add_done_callback`), а не числом задач.

**Вывод:** для IO-bound задач asyncio масштабируется идеально по числу «workers», но базовая стоимость acquire выше threading.Lock при 1 worker.

### multiprocessing.Lock

- Самый крутой рост: от ~800–1000 ns при 1 worker до 3000–6000 ns при 7.
- Каждый acquire — это `sem_wait()` → `futex` в ядре, даже без contention. При нескольких процессах добавляется IPC-overhead (cross-process semaphore).
- Почти не зависит от версии Python: стоимость определяется ядром, интерпретатор лишь тонкая обёртка.

**Вывод:** multiprocessing.Lock уместен только когда нужен настоящий memory isolation; использовать его как «быстрый» примитив нельзя.

### Общий вывод

| Примитив              | При 1 worker | При 7 workers | Рост (×) | Чувствителен к GIL? |
|-----------------------|-------------|---------------|----------|---------------------|
| `threading.Lock`      | ~80–100 ns  | ~200–900 ns   | 2.5–9×   | Да (без GIL — хуже) |
| `asyncio.Lock`        | ~200–350 ns | ~200–350 ns   | ~1×      | Нет                 |
| `multiprocessing.Lock`| ~800–1000 ns| ~3000–6000 ns | 4–6×     | Нет                 |

**Источники:**
- [Futex man page](https://man7.org/linux/man-pages/man2/futex.2.html) — `FUTEX_WAIT` / `FUTEX_WAKE` семантика
- [PEP 703 — Making the GIL Optional](https://peps.python.org/pep-0703/) — `_PyParkingLot`, per-object locking
- [asyncio event loop](https://docs.python.org/3/library/asyncio-eventloop.html) — кооперативное планирование задач
