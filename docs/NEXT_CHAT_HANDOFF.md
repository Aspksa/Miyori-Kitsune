# Miyori Kitsune — передача контекста следующему чату

> Источник истины для продолжения разработки. Машиночитаемый полный снимок: `docs/PROJECT_STATE.json`.

## Где проект

- GitHub: `Aspksa/Miyori-Kitsune`
- Ветка: `main`
- Текущий релиз: **v0.17.0**
- Последний функциональный релизный коммит: `5dbdb132b124aa7f227d98ca7e77ca6be591a0f6`
- Точка запуска Windows: `MiyoriKitsune.bat`
- Manifest: `version.json`

## Главная цель

Miyori Kitsune — личная AI-система пользователя, которая постепенно учится и развивается: накапливает память, опыт, навыки, модель мира, историю решений, рефлексии и собственные версии модели.

Cloud.ru — **учитель Miyori и облачная вычислительная среда**, а не сама Miyori. Сильная готовая модель Cloud.ru должна использоваться для критики, объяснений, разметки, генерации тренировочных примеров, оценки и GPU-обучения. Она не должна постоянно отвечать пользователю вместо собственного Miyori Student.

Пользователь хочет писать и получать объяснения **по-русски**.

## Ключевое решение — Teacher–Student Architecture

Пользователь подтвердил целевую архитектуру:

- **Miyori Kitsune** — собственная личная AI пользователя.
- У Miyori должны быть собственные: личность, память, World Model, навыки, история развития, рефлексии и версии модели/весов.
- **Miyori Student** — основной развиваемый мозг Miyori.
- **Cloud Teacher** — внешний сильный учитель, а не основной интеллект продукта.
- Локальная модель **не обязательна**. Miyori Student может храниться, запускаться и обучаться в облаке.
- Teacher не должен по умолчанию перехватывать обычный пользовательский чат и создавать иллюзию, что чужая модель и есть Miyori.

Целевой online flow:

`User → Miyori Memory/World Model/Skills → Miyori Student → Response`

Целевой learning flow:

`Miyori experience → Cloud Teacher → critique/labels → validated dataset → GPU training → Miyori Student candidate → evaluation → explicit approval → promote/rollback`

Cloud Teacher может:
- проверять и критиковать ответы Miyori;
- объяснять ошибки;
- размечать опыт;
- создавать supervised examples и preference pairs;
- помогать очищать training data;
- оценивать candidate-модели;
- давать teaching signals;
- использовать Cloud.ru GPU для обучения.

Cloud Teacher **не должен**:
- заменять Miyori Student как постоянный основной ответчик;
- автоматически менять личность/память Miyori;
- самостоятельно активировать новую модель;
- запускать платное GPU-обучение без явного подтверждения пользователя.

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

## Новое в v0.14.0 — Neural Core foundation

Теперь Miyori умеет выбирать runtime по активной модели в Model Registry.

- `core/neural_runtime.py` — runtime selector и локальный `llama_cpp` adapter для GGUF.
- Если локальная neural model недоступна, автоматически используется `miyori-internal-planner`.
- Neural runtime используется для обычного разговора; реальные действия по-прежнему идут только через planner + Action Gateway.
- `core/embeddings.py` — pluggable embeddings.
  - Реальные neural embeddings включаются только если `MIYORI_EMBEDDING_MODEL` указывает на локальную sentence-transformers модель.
  - Никакой модели автоматически из интернета не скачивается.
  - Без neural embeddings работает deterministic local vector fallback.
- `core/semantic_memory.py` — persistent vector index памяти.
- Memory v0.4 использует hybrid retrieval: lexical + importance + confidence + recency + vector similarity.
- `core/model_evaluation.py` — evaluation harness; оценки не могут автоматически активировать модель.
- Добавлены:
  - `GET /api/brain/models`
  - `GET /api/brain/memory/semantic`
  - `POST /api/brain/model/evaluate`
- Добавлены тесты `tests/test_neural_memory.py`.

Важно: **обученных собственных весов Miyori ещё нет**. v0.14.0 даёт инфраструктуру, которая уже умеет принять локальную GGUF-модель, подключить её, проверить и безопасно использовать.

## Новое в v0.15.0 — Cloud Teacher + Chat v1.2

- Добавлен `core/teacher_gateway.py`.
- Cloud Teacher использует отдельный Foundation Models API Key и работает через `https://foundation-models.api.cloud.ru/v1`.
- Foundation Models key и GPU Training credentials разделены.
- Teacher **не меняет и не подменяет** ответ Miyori: сначала отвечает Miyori Brain/Student, затем Teacher при необходимости создаёт отдельный teaching signal.
- Автопроверка выключена по умолчанию, потому что каждый review расходует токены.
- В чате после ответа доступна кнопка **«Проверить Teacher»**.
- Teacher feedback показывается отдельным сообщением с подписью Cloud Teacher.
- Пользователь выбирает **«В обучение»** или **«Не использовать»**.
- Только `accepted_for_training=true` teacher-feedback попадает в следующий training dataset.
- Чат показывает pipeline trace: runtime мозга, тип retrieval памяти и факт Teacher review.
- Верхний status strip теперь отдельно показывает: мозг, память, мир, навыки, учителя и обучение.
- В Личном кабинете появились отдельные настройки Foundation Models Teacher и GPU Training.
- Добавлены regression tests безопасности Teacher.

## Новое в v0.16.0 — Cloud-hosted Miyori Student

Теперь у Miyori есть отдельный runtime для **собственного облачного Student**, размещаемого в Cloud.ru Evolution ML Inference.

Архитектура:
- **Miyori Student** — основной генеративный мозг обычного диалога.
- **Cloud Teacher** — отдельный учитель для critique/labels/training signals.
- Teacher никогда автоматически не становится Student.

Student:
- runtime: `cloud_ml_inference`;
- endpoint: только HTTPS `*.inference.cloud.ru`;
- OpenAI-compatible `/v1/chat/completions`;
- отдельный API Token хранится только в локальном secrets-файле;
- получает релевантную память, project/task context и последние сообщения текущего диалога;
- реальные действия всё равно выполняются только через planner + Action Gateway.

Lifecycle:
`save/register candidate → test endpoint → evaluation → explicit promote → active → rollback`

Evaluation:
- проверка идентичности Miyori;
- работа с памятью/контекстом;
- честность о невыполненных действиях;
- action grounding;
- минимальный score для активации: **0.75**;
- активация только по явному подтверждению пользователя.

Версии Student изолированы:
- конфигурации endpoint/model/token сохраняются по version;
- active vN продолжает работать, пока candidate vN+1 тестируется;
- нельзя изменить endpoint/model активной версии без нового номера version;
- rollback может вернуть предыдущую активную модель и её сохранённую конфигурацию.

В Личном кабинете появились:
- ML Inference endpoint;
- Student model;
- Student version;
- Student API Token;
- включение Student;
- **Проверить Student**;
- **Оценить candidate**;
- **Активировать**;
- **Откатить мозг**.

Важно: код runtime готов, но фактический ML Inference instance ещё нужно создать в Cloud.ru и вставить его endpoint/token в Личный кабинет. Сама система не создаёт платный GPU-инференс автоматически.

## Ключевой UI-принцип после v0.17.0

Пользователь прямо указал, что прежний интерфейс был перегружен и непонятен.

**Нельзя возвращать техническую панель на главный экран.**

Главный чат должен выглядеть как обычный личный AI:
- Miyori;
- Память;
- Диалоги;
- сообщения;
- поле ввода.

На главном экране не показывать:
- Brain version;
- Planner / Runtime;
- Student / Candidate / LoRA;
- World Model counters;
- Skills counters;
- Teacher/Training counters;
- pipeline trace;
- технический context strip;
- версии компонентов.

Cloud.ru показывать человеческими шагами:
1. **Подключить учителя**
2. **Подключить мозг Miyori**
3. **Обучение — позже**

Технические поля можно хранить в **«Дополнительных настройках»**. Действия показывать прогрессивно: сначала подключение, затем проверка качества, затем использование, затем rollback только если он доступен.

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

Наиболее логичный следующий этап — **guided Cloud.ru setup без технических терминов**:

1. Сохранить текущий human-first UI.
2. По возможности сделать создание Student instance через Miyori одной кнопкой.
3. Перед любым платным ресурсом показать простую стоимость и запросить подтверждение.
4. После подключения: «Проверить мозг» → «Проверить качество» → «Использовать».
5. Затем строить первый реальный learning cycle, не добавляя developer dashboard в основной чат.
6. Eyes/Ears/Hands также подключать через простые пользовательские действия, а не технические панели.

Перед новым изменением сначала прочитать:
- `docs/PROJECT_STATE.json`
- этот файл
- `version.json`
- свежие коммиты `main`.

Не переписывать уже существующую архитектуру с нуля.
