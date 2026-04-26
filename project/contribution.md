# Репозитории для contribution

---

## python/cpython

Основной репозиторий CPython. Наиболее релевантные направления для contribution по теме:

- Issues и discussions по free-threading (тег `free-threading`) — активно развивается с Python 3.13
- Документация и тесты модулей `threading`, `_thread`, `queue`
- Баг-репорты и тесты на race conditions в стандартной библиотеке под `python3.13t`

https://github.com/python/cpython

---

## python-trio/trio

Альтернативная async-библиотека со строгой моделью структурированного параллелизма. Реализует собственные примитивы синхронизации (`trio.Lock`, `trio.Semaphore`, `trio.Event`) поверх event loop — интересно для сравнения с `threading`. Активное community, хорошо документированный процесс contribution.

https://github.com/python-trio/trio

---

## agronholm/anyio

Абстракция над asyncio и trio с единым API для примитивов синхронизации. Полезно изучить, как один интерфейс ложится на разные backend'ы.

https://github.com/agronholm/anyio

---

## benfred/py-spy

Sampling-профилировщик для Python, написанный на Rust. Работает без модификации исходника и без рестарта процесса — удобен для профилирования многопоточного кода в экспериментах. Возможные contribution: улучшение отображения thread state, поддержка free-threading сборки.

https://github.com/benfred/py-spy
