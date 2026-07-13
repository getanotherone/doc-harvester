# Doc Harvester v2 — Полная документация (текущее состояние)

## 1. Что это и зачем нужно

`doc_harvester` — это ETL/ingest-пайплайн для наполнения RAG-корпуса документами по электротехнике и смежной нормативке.

Основная цель:
- находить релевантные источники,
- скачивать и обрабатывать документы разных форматов,
- приводить их к единой chunk-модели,
- считать quality/eval-метрики,
- загружать результаты в Yandex Disk,
- поддерживать актуальную документацию в Yandex Wiki.

Ключевой фокус текущего контура: `электротехническое оборудование`, включая каталоги и нормативные документы.

---

## 2. Что система умеет

### 2.1 Discovery (поиск источников)
- Поиск кандидатов на сайты:
  - primary: Yandex Search
  - fallback: Google Search
- Подпитка seed-источниками из research markdown-файла.
- Скоринг кандидатов по профилю (`electrical`) и базовой релевантности.
- Вывод:
  - `sources_candidates.json` (кандидаты + score)
  - `sources_approved.json` (ручной approve)

### 2.2 Crawl + ingest (файловый режим)
- Поддержка обхода дочерних страниц внутри домена.
- Фильтрация ссылок по электропрофилю (soft-filter, чтобы не терять потенциально релевантные документы).
- Скачивание и загрузка оригиналов на Yandex Disk.
- Дедупликация по SHA256.
- Поддерживаемые форматы:
  - `pdf`
  - `docx`
  - `xlsx`
  - `html/htm`
  - `xml`
- Неподдерживаемые напрямую:
  - `doc`, `xls` (нужна предварительная конвертация в `docx/xlsx`)

### 2.2b Web-скрапинг (режим `--web`)
Скрапинг HTML-контента самих веб-страниц (не файлов) — для сайтов вроде `cable.ru`, где полезная информация находится прямо на страницах.

- **Двухфазный подход**:
  1. **Фаза Discovery** — BFS-обход страниц внутри домена (до `CRAWL_MAX_PAGES_PER_SOURCE`). Собирает только URLs и отслеживает parent→child связи. HTML не кэшируется.
  2. **Фаза Processing** — обрабатывает только **leaf-страницы** (страницы без дочерних ссылок). Leaf-страницы — это конечные продуктовые/карточные страницы с полными характеристиками товара. Категории и навигационные страницы автоматически пропускаются.
- **Строгое ограничение по пути**: discovery не выходит за пределы root URL path (например, при root `/cable/` не будет обходить `/engines/` или `/pumps/`).
- **Умная очистка HTML**:
  - удаление `nav`, `header`, `footer`, `aside`
  - удаление boilerplate по class/id (cookie-баннеры, сайдбары, меню, попапы)
  - предпочтение контента `<main>` / `<article>` если достаточно содержательно
- **Двухуровневая фильтрация продуктовых страниц**:
  - URL-фильтр: автоматический пропуск коммерческих/служебных страниц (delivery, payment, about, contacts, guarantee, leasing и т.д.)
  - Контент-фильтр: скоринг текста по продуктовым/техническим терминам (сечение, напряжение, ГОСТ, мм², кг/км) vs коммерческие анти-термины (доставка, оплата, корзина). Страницы ниже порога `WEB_MIN_PRODUCT_SCORE` пропускаются.
- Дедупликация по content-hash (SHA256 HTML).
- Далее стандартный pipeline: extraction → chunking → quality gate → upload на Yandex Disk.
- `meta.json` содержит `source_type: "web_page"`.
- Работает с любым онлайн-каталогом или marketplace, не только cable.ru.

### 2.3 Извлечение текста в units (extractors.py)
- PDF:
  - page-level extraction через `pdfminer`
  - OCR fallback per page (`pdf2image + pytesseract`) для слабых страниц
  - memory-safe обработка
- DOCX/XLSX/HTML/XML:
  - извлечение структурированных блоков
  - запись в `units/*.json`
- Web HTML (для `--web` режима):
  - `extract_web_html_blocks()` — очистка от chrome (nav/footer/boilerplate)
  - `extract_html_string_to_units()` — обёртка для работы из строки (без файла)

### 2.4 Chunking v2
- Иерархический chunking на основе `units`.
- Token-aware лимиты:
  - `target_tokens = 1000`
  - `max_tokens = 1200`
- No-split правила:
  - не рвём `table` блоки
  - не рвём `normative` блоки
- Логи и артефакты:
  - `chunks/*.json`
  - `chunks_minimal/*.json`
  - `chunking_log.json`

### 2.5 Stage 3 minimal model (расширенный)
Минимальные чанки содержат:
- `document`
- `page`
- `section`
- `chunk_index`
- `text`
- `doc_type`
- `vendor`
- `standard_id`
- `year`
- `lang`
- `source_type`
- `quality_status`

### 2.6 Quality Gate + Quarantine
- Для каждого документа считается `quality_gate.json`.
- Метрики качества:
  - empty ratio
  - tiny ratio
  - duplicate ratio
  - noisy ratio
- Если `quality_status=warn` и включён блокирующий режим:
  - документ уходит в `_quarantine/<document_id>`
  - в основной `_processed` не попадает

### 2.7 Retrieval Auto-Eval
- Фиксированный набор инженерных вопросов (20 штук):
  - `config/eval_questions_electrical.json`
- Считается retrieval-метрика hit-rate (top-k).
- Отчёты:
  - `runs/auto_eval_<timestamp>.json`
  - `runs/auto_eval_latest.json`

### 2.8 Backfill из Yandex Disk
- Дозаполнение уже загруженных ранее файлов:
  - скачивание с Disk
  - extraction + chunking + minimal
  - quality gate
  - upload в `_processed` или `_quarantine`
- Поддерживает параллельную обработку (`--workers`).

### 2.9 Wiki automation
- Автогенерация markdown-страниц wiki (`wiki/out`) из шаблонов + фактических логов.
- Публикация/обновление страниц в Yandex Wiki через API:
  - dry-run
  - apply
  - create-missing
- Автоматический snapshot локальных wiki-страниц перед apply.

---

## 3. Архитектура пайплайна

### 3.1 High-level поток
1. Discovery (опционально) -> `sources_candidates.json`.
2. Ручной approve -> `sources_approved.json` (с указанием `mode`: `"files"` или `"web"`).
3. Ingest (два режима):
   - **Файловый режим** (`--files` / `mode: "files"`):
     - crawl страниц → отбор файлов
     - download + upload оригинала
     - hash dedup
     - extraction → `units`
   - **Веб-режим** (`--web` / `mode: "web"`):
     - **Фаза 1 — Discovery**: BFS-crawl для сбора URLs (без кэширования HTML), отслеживание parent→child связей, строгое ограничение по root path
     - Определение leaf-страниц (без дочерних ссылок) — это продуктовые карточки
     - **Фаза 2 — Processing** (только leaf-страницы):
       - URL-фильтрация (пропуск коммерческих страниц)
       - fetch HTML → очистка от навигации и boilerplate
       - контент-фильтрация (скоринг по продуктовым терминам)
       - content-hash dedup
       - extraction → `units`
   - Далее общий pipeline: chunking → `chunks` + `chunks_minimal` → quality gate → route в `_processed` или `_quarantine`
4. Auto-eval.
5. Build docs.
6. Publish wiki (по команде).

### 3.2 Основные модули
- `scraper.py` — основной ingest pipeline: `ingest_page()` (файлы) + `ingest_web()` (веб-страницы), CLI с argparse.
- `pdf_extractor_v2.py` — PDF extraction + OCR fallback.
- `extractors.py` — DOCX/XLSX/HTML/XML extraction + `extract_web_html_blocks()` для веб-скрапинга.
- `chunker.py` — chunking v2 + minimal model.
- `quality_eval.py` — quality gate + auto-eval + quality_status propagation.
- `yandex.py` — API-обвязка для Yandex Disk.
- `scripts/discover_sources.py` — discovery.
- `scripts/backfill_from_yandex.py` — backfill.
- `scripts/build_wiki.py` — сборка wiki markdown из шаблонов + метрик.
- `scripts/publish_wiki.py` — публикация wiki через API.

---

## 4. Структура данных и артефакты

### 4.1 Локальные данные (`datasets`)
Для документа обычно создаётся:
- `units/*.json`
- `chunks/*.json`
- `chunks_minimal/*.json`
- `extraction_log.json`
- `chunking_log.json`
- `quality_gate.json`
- `meta.json` или `meta_backfill.json`

### 4.2 Yandex Disk
Оригиналы:
- `/datasets/specs/<source>/<date>/<filename>`

Обработанные результаты:
- `/datasets/specs/<source>/<date>/_processed/<document_id>/...`

Quarantine:
- `/datasets/specs/<source>/<date>/_quarantine/<document_id>/...`

### 4.3 Runs
- `runs/ingest_*.json` — манифесты ingest-run.
- `runs/backfill_from_yandex.json` — отчёт backfill.
- `runs/auto_eval_*.json` + `auto_eval_latest.json`.
- `runs/wiki_publish_*.json` — отчёты публикации wiki.
- `runs/wiki_snapshots/<timestamp>` — snapshot перед wiki apply.

---

## 5. Запуск (основные сценарии)

### 5.1 Подготовка окружения
```bash
cd "$PROJECT_ROOT"
bash scripts/setup_venv311.sh
```

### 5.2 Базовый ingest (файлы из approved sources)
```bash
bash scripts/run_ingest.sh
# или напрямую:
python src/scraper.py
```

### 5.2b Web-скрапинг (страницы сайта)
```bash
# Скрапить конкретный сайт:
python src/scraper.py --web https://cable.ru/cable/

# Скрапить конкретный сайт в файловом режиме:
python src/scraper.py --files https://example.com/catalog/

# Автоматический режим — обрабатывает все approved sources с учётом поля mode:
python src/scraper.py
```
Для добавления веб-источника в `sources_approved.json`, укажите `"mode": "web"`:
```json
{"url": "https://cable.ru/cable/", "approved": true, "priority": 1, "mode": "web"}
```

### 5.3 Discovery
```bash
bash scripts/run_discovery.sh
bash scripts/run_discovery.sh --profile electrical --top-n 80 --limit-per-query 30
```

### 5.4 Backfill
```bash
bash scripts/run_backfill_yandex.sh --limit 20 --workers 4
```

### 5.5 Quality + eval
```bash
bash scripts/run_quality_eval.sh
bash scripts/run_quality_eval.sh --refresh-quality
```

### 5.6 Rechunk миграция для старых данных
```bash
bash scripts/run_rechunk.sh
bash scripts/run_quality_eval.sh --refresh-quality
```

### 5.7 Сборка wiki markdown (локально)
```bash
bash scripts/run_docs.sh
```

### 5.8 Публикация в Yandex Wiki
```bash
# dry-run
bash scripts/run_publish_wiki.sh

# apply
bash scripts/run_publish_wiki.sh --apply
```

### 5.9 Полный цикл
```bash
bash scripts/run_all.sh
```

---

## 6. Переменные окружения

### 6.1 Обязательные
- `YANDEX_DISK_TOKEN` — доступ к Yandex Disk API.
- `YANDEX_WIKI_TOKEN` — доступ к Yandex Wiki API (для публикации).
- `YANDEX_WIKI_CLOUD_ORG_ID` — org id для wiki API.

### 6.2 Рекомендуемые/опциональные
- `YANDEX_WIKI_API_BASE` (default: `https://api.wiki.yandex.net`)
- `CRAWL_CHILD_PAGES` (`1|0`)
- `CRAWL_MAX_PAGES_PER_SOURCE` (default `120`)
- `ELECTRICAL_ONLY` (`1|0`)
- `ELECTRICAL_SCORE_THRESHOLD` (default `2`)
- `FOLLOW_CHILD_SCORE_THRESHOLD` (default `0`)
- `QUALITY_GATE_BLOCK_WARN` (`1|0`, default `1`)
- `QUARANTINE_SUBDIR` (default `_quarantine`)
- `BACKFILL_WORKERS` (default `1`)
- `CHUNK_JSON_INDENT` (default `0`, compact json)
- `QUALITY_MIN_TOKENS`
- `QUALITY_MAX_EMPTY_RATIO`
- `QUALITY_MAX_TINY_RATIO`
- `QUALITY_MAX_DUPLICATE_RATIO`
- `QUALITY_MAX_NOISY_RATIO`

### 6.3 Web-режим
- `WEB_CRAWL_DELAY_SEC` (default `1.0`) — задержка между запросами при web-crawl
- `WEB_MIN_CONTENT_BLOCKS` (default `3`) — минимум контентных блоков для обработки страницы
- `WEB_MIN_PRODUCT_SCORE` (default `2`) — порог product_spec_score для обработки страницы

---

## 7. Как работает quality и quarantine

1. После chunking считается `quality_gate.json`.
2. `status` определяется как:
   - `pass`, если все проверки ок
   - `warn`, если хотя бы одна проверка нарушена
3. При `QUALITY_GATE_BLOCK_WARN=1`:
   - `warn` -> upload в `_quarantine`
   - `pass` -> upload в `_processed`
4. `quality_status` синхронизируется в:
   - `chunks/*.json`
   - `chunks_minimal/*.json`

---

## 8. Вики-автоматизация (отдельно)

### 8.1 Что автоматизируется
- Сборка страниц из шаблонов (`wiki/content`) и актуальных метрик (`runs + datasets logs`) в `wiki/out`.
- Публикация `wiki/out/*.md` в конкретные страницы Yandex Wiki по карте `config/wiki_publish_map.json`.

### 8.2 Карта публикации
Локальный `config/wiki_publish_map.json` создаётся из публичного шаблона
`config/wiki_publish_map.example.json`:
- `source` — имя markdown-файла в `wiki/out`.
- `slug` — путь страницы в Wiki (можно указать и полный URL; скрипт нормализует).
- `title` — заголовок страницы при update/create.

### 8.3 Режимы публикации
- Dry-run: показывает, что будет обновлено, без записи.
- Apply: обновляет страницы.
- Apply + create-missing: создаёт отсутствующие страницы.

### 8.4 Безопасность
- Перед `--apply` автоматически делается snapshot:
  - `runs/wiki_snapshots/<timestamp>`
- Отчёт о публикации пишется в:
  - `runs/wiki_publish_<mode>_<timestamp>.json`

---

## 9. Ограничения и текущие допущения

- `doc/xls` не обрабатываются напрямую.
- Discovery использует HTML-скрапинг поисковой выдачи (может зависеть от изменений вёрстки/антибот-защиты).
- OCR для очень тяжёлых PDF может быть ресурсозатратным.
- Эвристики `doc_type/vendor/standard_id/year/lang` не являются идеальными NER-моделями, а быстрыми rule-based инференсами.
- Web-режим: URL-фильтр и product_spec_score — эвристики, заточенные под электротехнику. Для других доменов потребуется расширение словарей.
- Web-режим: JavaScript-рендеринг не поддерживается (используется обычный HTTP GET). SPA-сайты могут выдавать пустой контент.
- Web-режим: leaf-определение основано на наличии дочерних ссылок в рамках BFS-лимита. Если BFS не успевает обойти все страницы, некоторые категории могут быть ошибочно приняты за leaf-страницы.
- Web-режим: `CRAWL_MAX_PAGES_PER_SOURCE` ограничивает фазу Discovery (BFS), но количество leaf-страниц для обработки не ограничено.

---

## 10. Рекомендуемый рабочий процесс

1. `run_discovery` -> ревью `sources_candidates.json`.
2. Аппрув в `sources_approved.json`.
3. `run_ingest`.
4. `run_quality_eval`.
5. `run_docs`.
6. `run_publish_wiki.sh` (dry-run -> apply).

Для миграции старого корпуса:
1. `run_rechunk`.
2. `run_quality_eval --refresh-quality`.
3. `run_docs`.
4. `run_publish_wiki.sh --apply`.
