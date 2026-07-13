# Wiki Automation

Wiki publishing is optional and isolated from crawling. Documentation can be generated and
reviewed locally before any API call is made.

## Configuration

1. Copy `config/wiki_publish_map.example.json` to `config/wiki_publish_map.json`.
2. Map each local Markdown source to a page URL or slug in your own Wiki organization.
3. Set `YANDEX_WIKI_TOKEN` and `YANDEX_WIKI_CLOUD_ORG_ID` in `.env` or your secret manager.

The local map is ignored by Git because it can reveal private organization structure.

## Dry run

```bash
python scripts/publish_wiki.py --map config/wiki_publish_map.json
```

Review generated output and the proposed page list before applying changes.

## Publish

```bash
python scripts/publish_wiki.py --apply --map config/wiki_publish_map.json
```

Apply runs copy the local generated Markdown into a timestamped snapshot directory. This is
not a backup of remote page history; use the Wiki platform's revision history for rollback.
Keep runtime snapshots under `runs/`; they are ignored by Git and may contain private data.

## Generalization status

The publisher currently targets Yandex Wiki. A future publisher interface will support
local Markdown, Git repositories, generic webhooks, and other documentation systems without
changing the processing pipeline.
