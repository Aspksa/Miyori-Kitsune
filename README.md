# Miyori Kitsune

Локальное переносимое ядро Miyori Kitsune с адаптивным веб-интерфейсом и встроенным обновлением через GitHub.

## Быстрый запуск

1. Скопируйте папку проекта на локальный диск, внешний SSD, флешку или другой носитель.
2. На Windows запустите MiyoriKitsune.bat.
3. Ядро выберет свободный локальный порт и автоматически откроет интерфейс в браузере.
4. Для остановки закройте окно ядра или нажмите Ctrl+C.

Текущий этап требует Python 3.10+.

## Архитектура

- MiyoriKitsune.bat — единая точка запуска Windows.
- core/server.py — локальный HTTP/API слой.
- core/updater.py — проверка и установка обновлений из GitHub.
- version.json — локальная версия и канал обновлений.
- web/ — адаптивный интерфейс.
- data/, logs/, config/ — локальные пользовательские данные.
- backups/ — резервные копии перед обновлениями.

## Интерфейс

Под логотипом расположен Личный кабинет. Основные пространства: Miyori Kitsune, Рабочее пространство, Домашнее пространство, Настройки. В системной зоне отдельно находятся Обновление проекта и Мобильное приложение.

## Обновление через GitHub

Центр обновлений проверяет version.json в ветке main. Если версия отличается, Miyori скачивает ZIP ветки main, создаёт резервную копию текущих программных файлов и устанавливает новую версию.

При обновлении сохраняются .git, data, logs и config/local.json. После установки новой версии необходимо перезапустить MiyoriKitsune.bat.

## Portable mode

Ядро не использует абсолютные пути проекта: рабочий корень определяется относительно core/server.py. Папку можно переносить между дисками и носителями без перенастройки путей.


## Память Miyori

Управляемая локальная память хранится в data/memory.json. Пользователь сам добавляет записи и может отдельно включать или отключать категории памяти от активного контекста помощницы.

Категории: Проекты, Работа, Задачи, Запомнить, Предпочтения, Люди и Важные факты.


## Projects + Tasks Entity System

Проекты и задачи хранятся как отдельные сущности в `data/projects/` и `data/tasks/`. У каждой сущности есть постоянный ID, состояние и временные метки. Задачи могут быть привязаны к проектам, а память — к проекту или конкретной задаче.

## Miyori Context Resolver

`/api/context` собирает ограниченный релевантный контекст: выбранный проект, связанные задачи и разрешённые записи памяти. Это позволяет масштабировать систему до большого количества проектов без загрузки всех данных в каждый диалог.

## Miyori Action Gateway

Будущая собственная модель Miyori Kitsune получает управляемый интерфейс действий через `/api/assistant/action`, а не прямой неограниченный доступ к файлам. Базовые возможности: создавать, менять и удалять проекты и задачи, а также добавлять память. Все действия записываются в `data/assistant-audit.json`.

Удаляющие действия через Action Gateway требуют явного подтверждения. Набор возможностей можно расширять в будущих версиях без изменения модели данных.


## Miyori Brain

Собственный backend-мозг Miyori находится в `core/brain.py`. Он работает независимо от интерфейса: получает сообщение, собирает контекст через Context Resolver, формирует план и вызывает разрешённые действия через Action Gateway.

Текущий Brain Runtime локальный и не использует внешний AI API. Он умеет обрабатывать базовые команды создания проектов, задач, сохранения памяти и запросов состояния. Сессии мозга сохраняются в `data/brain/sessions/`, внутренние события — в `data/brain/brain-events.json`.

`core/brain_runtime.py` определяет стабильный контракт Model Runtime. В будущем обученная собственная модель Miyori Kitsune сможет заменить текущий внутренний планировщик, не меняя Projects, Tasks, Memory, Context Resolver и Action Gateway.

API:
- `GET /api/brain/status`
- `POST /api/brain/think`

Brain не получает прямой неограниченный доступ к файлам; любые изменения системных сущностей проходят через Action Gateway и журналируются.


## Miyori Brain Architecture v0.9

Архитектура мозга разделена на независимые backend-подсистемы и не требует дополнительных элементов интерфейса.

- `core/brain.py` — координатор Brain.
- `core/cognitive_loop.py` — цикл perception → context → plan → action → outcome → reflection → learning.
- `core/identity.py` — устойчивая идентичность и стадия развития Miyori.
- `core/world_model.py` — граф объектов и связей: проекты, задачи, память и их отношения.
- `core/reflection.py` — рефлексия по итогам действий и ошибок.
- `core/learning.py` — staged learning: observed → confirmed → retained → applied → reassessed.
- `core/skills.py` — реестр навыков и статистика их использования.
- `core/sleep_engine.py` — консолидация накопленного опыта.
- `core/brain_scheduler.py` — безопасный фоновый запуск консолидации примерно раз в 30 минут.
- `core/self_development.py` — предложения на собственное развитие.
- `core/safety_kernel.py` — политика изменений критического ядра.
- `core/brain_architecture.py` — единый снимок внутреннего состояния архитектуры.

Self-Development не имеет функции бесконтрольного `self_modify()`. Поток развития построен как proposal → sandboxed → tested → approved → applied → rollback. Для критических файлов Safety Kernel требует отдельного подтверждения; прямое self-apply отключено.

World Model хранит не только текст, а узлы и связи между сущностями. Cognitive Loop синхронизирует его из текущего контекста Projects, Tasks и Memory.

Sleep Engine не переписывает код и модель. Он консолидирует world model, рефлексии, learning items и skills и формирует рекомендации для следующего развития.

Служебные API:
- `GET /api/brain/architecture`
- `POST /api/brain/sleep`
- `GET /api/brain/development`
- `POST /api/brain/development/propose`
- `POST /api/brain/development/transition`

Эта версия является архитектурным фундаментом. Она не является доказательством сознания или биологической жизни и пока не содержит обученной нейросетевой модели; neural runtime подключается через существующий `BrainModelRuntime`.


## Cloud.ru Training Connector

Cloud.ru используется Miyori как внешняя вычислительная среда для тяжёлого обучения, а не как замена личности, памяти или Brain Architecture.

Учётные данные настраиваются в Личном кабинете:
- Key ID;
- Key Secret;
- Workspace ID;
- x-api-key;
- регион.

Секреты хранятся в `data/secrets/cloudru.json`, который находится внутри исключённой из Git пользовательской директории `data/`. На Windows Key Secret и x-api-key дополнительно защищаются Windows DPAPI и не возвращаются обратно через API после сохранения.

`core/cloudru.py` поддерживает:
- получение access token через Distributed Train service_auth;
- проверку соединения через список MT-конфигураций;
- получение training configurations;
- запуск `POST /public/v2/jobs`;
- локальный журнал запущенных training jobs.

`core/training_data.py` формирует локальный JSONL dataset-кандидат из:
- learning items со стадией confirmed/retained/applied/reassessed;
- достаточно уверенных reflection records;
- полезных пар user → Miyori из внутренних сессий Brain.

Сырые данные не отправляются в Cloud.ru автоматически. Dataset сначала создаётся локально со статусом `candidate`.

API:
- `GET /api/cloudru/status`
- `POST /api/cloudru/save`
- `POST /api/cloudru/test`
- `GET /api/cloudru/configs`
- `GET /api/cloudru/jobs`
- `GET /api/training/datasets`
- `POST /api/training/dataset/build`
- `POST /api/cloudru/training/submit`

Запуск GPU training job является отдельным явным действием. Фоновый Learning Engine и Sleep Engine не запускают платные Cloud.ru-задачи самостоятельно.
