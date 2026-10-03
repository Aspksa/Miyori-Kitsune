# Miyori Kitsune — передача контекста следующему чату

> Источник истины для продолжения разработки. Машиночитаемый полный снимок: `docs/PROJECT_STATE.json`.

## Где проект

- GitHub: `Aspksa/Miyori-Kitsune`
- Ветка: `main`
- Текущий релиз: **v0.13.0**
- Последний известный коммит до обновления handoff: `fb9768388769467360fc87eda84995a9b87f21f6`
- Точка запуска Windows: `MiyoriKitsune.bat`
- Manifest: `version.json`

## Главная цель

Miyori Kitsune — личная AI-система пользователя, которая постепенно учится и развивается: накапливает память, опыт, навыки, модель мира, историю решений, рефлексии и собственные версии модели.

Cloud.ru — только вычислительная инфраструктура для тяжёлого GPU-обучения. Он не заменяет личность/память/архитектуру Miyori.

Пользователь хочет писать и получать объяснения **по-русски**.

## UI-принцип

Не раздувать сайт множеством технических блоков. **Чат — главный интерфейс**.

Через чат должны идти:
- обычное общение;
- статусы Brain/Memory/World Model/Learning/Skills/Cloud.ru;
- проекты и задачи;
- подтверждения опасных действий;
- подготовка и контроль обучения;
- позже — инструменты и компьютерные действия.

Интерфейс должен быть профессиональным, красивым, удобным, адаптивным и компактным.

## Новое в v0.13.0 — Cognitive Foundation

- **Model Registry**: версии моделей Miyori, стадии `candidate → testing → approved → active`, контролируемая активация и foundation для rollback.
- **Memory v0.3**: importance, confidence, source и relevance retrieval по текущему запросу с учётом важности и давности.
- **Embodiment Registry**:
  - «глаза» — vision sensor, сейчас через chat-image adapter;
  - «уши» — hearing channel, пока без microphone/STT adapter;
  - «голос» — speech actuator, пока без TTS adapter;
  - «руки» — контролируемые цифровые действия через Action Gateway;
  - «ноги» — mobility channel, по умолчанию отключён до появления безопасного navigation/robotics adapter.
- Cognitive Loop теперь включает состояние органов восприятия и использует query-aware retrieval памяти.
- Self-Development получил строгую state machine: нельзя перескакивать через sandbox/test; применение всегда требует явного подтверждения.
- Safety Kernel теперь считает Brain, Memory, Model Registry и Embodiment критическими областями.
- Добавлены `tests/test_cognitive_foundation.py`.

Важно: это **архитектурные органы**, а не прямой доступ к камере/микрофону/компьютеру. Реальные hardware/tool adapters подключаются отдельно с разрешениями и аудитом.

## Что уже реализовано

### Core
- локальный сервер `core/server.py`;
- Projects + Tasks как реальные сущности;
- управляемая Memory;
- Context Resolver;
- Action Gateway;
- audit log.

### Brain Architecture
- `core/brain.py` — координатор;
- `core/brain_runtime.py` — сменный runtime contract;
- `core/cognitive_loop.py` — perception → context → plan → action → outcome → reflection → learning;
- Identity;
- World Model;
- Reflection Engine;
- Learning Engine;
- Skills Registry;
- Sleep/Consolidation Engine;
- Self-Development Engine;
- Safety Kernel.

Текущий runtime ещё **не обученная нейросеть**. Это локальный rule/planner runtime, подготовленный к замене собственным Neural Core.

### Саморазвитие
Не использовать бесконтрольный `self_modify()`.

Принятый поток:

`proposed → sandboxed → tested → approved → applied → rolled_back`

Критические изменения требуют подтверждения. Прямой self-apply отключён.

### Cloud.ru
Файл: `core/cloudru.py`.

Ключи вводятся пользователем в **Личном кабинете**, не в чат и не в GitHub.

Хранятся локально в `data/secrets/cloudru.json`.
На Windows Key Secret и x-api-key защищаются DPAPI.

Поддержано:
- service auth;
- проверка Distributed Train;
- MT configs;
- POST training jobs;
- локальная история jobs.

**Платное GPU-обучение автоматически не запускается.**

### Training Data
Файл: `core/training_data.py`.

Локальные JSONL candidate datasets строятся из:
- подтверждённых learning items;
- достаточно уверенных reflections;
- полезных пар user → Miyori из Brain-сессий.

Автоматической отправки датасетов в Cloud.ru нет.

### Чат
Chat v1.1 — основной UI.

Есть:
- реальный вызов `POST /api/brain/think`;
- лента сообщений;
- статусы Brain / World Model / Skills / Learning / Cloud.ru;
- красивые стадии обработки;
- `/status`, `/brain` и естественные запросы «как ты?»;
- встроенные Подтвердить/Отменить;
- постоянные диалоги;
- восстановление последней беседы;
- создание/переключение/переименование/удаление разговоров.

История: `data/brain/sessions/`, до 200 сообщений на диалог.

## Основные данные

- Projects: `data/projects/`
- Tasks: `data/tasks/`
- Memory: `data/memory.json`
- Audit: `data/assistant-audit.json`
- Brain sessions: `data/brain/sessions/`
- Brain events: `data/brain/brain-events.json`
- Identity: `data/brain/identity.json`
- World Model: `data/brain/world-model.json`
- Reflections: `data/brain/reflections.json`
- Learning: `data/brain/learning.json`
- Skills: `data/brain/skills.json`
- Development proposals: `data/brain/self-development/proposals.json`
- Cloud.ru secrets: `data/secrets/cloudru.json`
- Training datasets: `data/training/datasets/`

## Важное правило работы с GitHub

Ранее был инцидент: commit `41ee...` с неправильной atomic tree-операцией удалил несколько файлов.

Поэтому:
1. Перед изменением получить свежий SHA файла из `main`.
2. Использовать **per-file create/update**.
3. Не использовать `create_tree` без крайней необходимости.
4. Не делать force reset.
5. После серии изменений проверять актуальные файлы в `main`.

## Известные технические долги

- нет полноценной локальной аутентификации/сессии;
- mutating localhost API потенциально CSRF-sensitive;
- updater ещё нуждается в ZIP-slip validation, hash/signature verification, atomic install и rollback API;
- JSON-хранилища позже нужно мигрировать в SQLite;
- Neural Core пока отсутствует;
- полноценный semantic retrieval/embeddings пока отсутствуют.

## Что делать дальше

Наиболее логичный следующий этап — **Neural Runtime + настоящая semantic memory**:

1. Реальный neural backend за контрактом `BrainModelRuntime`.
2. Tokenizer/model artifact contract.
3. Embeddings и vector semantic retrieval.
4. Context budget + fusion памяти, World Model и навыков.
5. Evaluation harness.
6. Подключение image/screen perception adapter.
7. Затем microphone/STT и TTS adapters.
8. После этого — расширение «рук» через sandboxed computer/file tools.
9. Cloud.ru training orchestration: estimate → budget → confirm → train → evaluate → approve → promote/rollback.

Перед новым изменением сначала прочитать:
- `docs/PROJECT_STATE.json`
- этот файл
- `version.json`
- свежие коммиты `main`.

Не переписывать уже существующую архитектуру с нуля.
