# Ordo vs pypyr

## Зачем этот документ

Это честная сверка пересечения между Ordo и `pypyr`.

- **Ordo** здесь оценивается по текущим документам репозитория, а не по готовому runtime.
- **pypyr** оценивается по его официальным материалам: главная страница, pipeline structure, CLI, error handling, custom step API.

Иными словами: сравнивается **intended shape Ordo** с **реально задокументированным shape pypyr**.

## Короткий вывод

Да, пересечение **существенное**.

На внешнем уровне Ordo и pypyr оба выглядят как:

- YAML-driven local workflow runner;
- последовательность шагов;
- CLI entrypoint;
- расширение через Python-код и вызываемые операции/steps;
- инструмент для automation / repo rituals / ops tasks.

Если Ordo остановится на уровне «yaml + steps + shell/python execution», он будет **слишком близок** к pypyr.

Потенциальная отдельная ниша Ordo начинается там, где first-class становятся:

- явные `guards` как отдельная фаза;
- режимы `check / plan / execute / explain`;
- публичный contract `connector -> operation`;
- сильная structured result model;
- более жёсткая reviewable и agent-safe семантика.

## Таблица сравнения

| Аспект | Ordo | pypyr | Честная оценка |
| --- | --- | --- | --- |
| Базовая форма | Declarative local workflows | YAML pipelines / task runner | **Сильное пересечение** |
| Основной носитель сценария | Workflow file с `guards` и `steps` | Pipeline YAML со `steps`, `on_success`, `on_failure`, custom groups | **Сильное пересечение**, но shape не идентичен |
| Основная ментальная модель | Policy + orchestration + explainable contract | Step pipeline automation | **Пересечение есть**, но фокус разный |
| Локальная автоматизация | Да, это core use case | Да, прямо заявлено как core use case | **Почти прямое совпадение** |
| Shell/command execution | Планируется через connector operations (`shell.command`) | Есть built-in `cmd`, `shell`, `cmds`, `shells` | **Сильное пересечение** |
| Python extensibility | Да, через connectors/operations | Да, через custom steps `run_step(context)` | **Сильное пересечение** |
| Composability | Планируется через connectors/profiles/workflows | Есть call/jump/pype/custom step groups | **Сильное пересечение** |
| Guards как отдельная сущность | Да, отдельный top-level phase до steps | Отдельной first-class guard phase не видно; есть `run/skip/assert/swallow/retry` и error handlers | **Важное отличие Ordo** |
| Режим `check` | Да, отдельный runtime mode без effectful business steps | Аналога как first-class mode в docs не видно | **Сильное отличие Ordo** |
| Режим `plan` | Да, planned first-class mode | Аналога как first-class mode в docs не видно | **Сильное отличие Ordo** |
| Режим `explain` | Да, planned first-class mode | Есть runtime errors, logging и failure handling, но не отдельный explain mode | **Сильное отличие Ordo** |
| Structured result envelope | Заявлен как обязательный | Есть runtime context, exceptions, `runErrors`, exit code; но не видно отдельного обязательного result envelope как contract surface | **Сильное отличие Ordo** |
| Validation-first contract | У Ordo уже есть schema и жёсткая идея unknown-field failure | В официальных docs pypyr акцент на executable YAML и step semantics; явной schema-first contract surface не видно | **Отличие Ordo**, если реально довести до runtime |
| Public connector contract | Да, это ядро модели | В pypyr центральное понятие — step/module, а не connector family contract | **Сильное отличие модели** |
| Agent-safe authoring | Прямо просматривается в vision | Не выглядит основной product axis | **Вероятное отличие Ordo** |
| CI/CD / devops automation | Возможный use case, но не identity | Один из явно продвигаемых сценариев | **Частичное пересечение** |
| Loops / branching / retries | Пока только как возможные later extensions | Есть как готовые first-class decorators/features | **Сейчас преимущество pypyr по зрелости** |
| Готовая standard library | Пока нет, early skeleton | Большая built-in step library | **Сейчас преимущество pypyr по зрелости** |
| Product maturity | Concept/spec stage | Working tool с docs и CLI | **Непрямое сравнение: pypyr сильно зрелее** |

## Где пересечение реально опасно

Опасная зона для Ordo:

1. YAML-файл описывает шаги.
2. Шаги в основном сводятся к shell/python/cmd.
3. Выполнение идёт последовательно из CLI.
4. Расширение идёт через Python code units.

Это уже очень близко к тому, как pypyr сам себя описывает.

Если Ordo быстро придёт к MVP вида:

- `steps:`
- `shell.command`
- `python.call`
- чуть-чуть conditions/retries

то внешне это будет читаться как **pypyr-подобный tool с другой терминологией**.

## Где у Ordo может быть реальная отдельная ниша

Ordo перестаёт быть «ещё одним YAML runner», если удерживает следующие границы:

### 1. Guards — не decorator, а отдельная фаза политики

У pypyr контроль потока в основном встроен в step execution model.

У Ordo guard задуман как отдельный semantic layer:

- без intended side effects;
- проверяется до steps;
- влияет на explainability и safety.

Это не косметика, а другой execution contract.

### 2. `check / plan / execute / explain` — это ядро, а не побочный UX

Если эти режимы будут реально first-class и дадут machine-readable output, Ordo начнёт отличаться не синтаксисом, а моделью исполнения.

### 3. Connector family contract важнее ad hoc step modules

У Ordo сильная идея семейства операций с общими prerequisites, bootstrap и shared context.

Это другой центр тяжести, чем «произвольный Python step + decorators».

### 4. Structured result обязателен

Если результат Ordo стабильно выражает:

- guard outcomes;
- executed/skipped steps;
- machine-readable codes;
- human explanation;

то это уже ближе к contract runtime, чем к обычному pipeline runner.

### 5. Human + agent reviewability

Если Ordo реально проектируется под agent-authored workflows с предсказуемой семантикой и минимизацией скрытой shell-магии, это тоже отдельный продуктовый вектор.

## Где pypyr сейчас объективно сильнее

Сейчас, по доступным материалам, pypyr сильнее как готовый инструмент:

- зрелый CLI;
- много built-in steps;
- loops / retries / conditional execution уже готовы;
- error handling уже оформлен;
- extensibility через Python простая и рабочая.

То есть если задача — **сегодня автоматизировать локальные pipelines**, pypyr уже решает большой класс проблем.

## Практический вывод для Ordo

### Если цель — просто local YAML automation

Тогда пересечение с pypyr слишком большое, и Ordo рискует выглядеть как дублирование.

### Если цель — explainable contract runtime для human+agent workflows

Тогда проект может быть оправдан, но только если это проявится в первых working slices:

- отдельные guards;
- check/plan/explain как реальный runtime surface;
- resolver по connector operations;
- structured results как норма, а не лог после факта.

## Bottom line

Честный ответ:

- **Да, Ordo и pypyr заметно пересекаются.**
- **На уровне MVP они могут оказаться слишком похожими.**
- **У Ordo есть шанс на отдельную нишу только через более строгую contract/explainability модель.**

Если эта модель не станет главным отличием реализации, а останется только в документах, сравнение с pypyr будет не в пользу Ordo.

## Источники

### Ordo

- `README.md`
- `docs/format.md`
- `meta/vision.md`
- `meta/product-shape.md`
- `meta/model/connector/contract.md`
- `meta/errors-and-results.md`
- `meta/domain/runtime.md`

### pypyr

- https://pypyr.io/
- https://pypyr.io/docs/pipelines/pipeline-structure/
- https://pypyr.io/docs/cli/run-a-pipeline/
- https://pypyr.io/docs/getting-started/error-handling/
- https://pypyr.io/docs/api/step/
