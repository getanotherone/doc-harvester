# Documentation Automation

Documentation publishing is optional and isolated from crawling. Markdown can be generated,
reviewed, and previewed locally before an external API call changes content.

The same batch workflow supports local output, Yandex Wiki, Confluence Cloud, Notion, and
installed third-party publishers.

For a first-time Notion setup, follow the step-by-step
[Notion dry-run guide](notion-dry-run.md). It starts with a read-only connection test and
keeps the real write test separate.

## Configuration

1. Copy `config/wiki_publish_map.example.json` to `config/wiki_publish_map.json`.
2. Set the map's top-level `publisher` or pass `--publisher`.
3. Map every Markdown `source` to a provider-specific `destination`.
4. Store only the selected provider's credentials in `.env` or a secret manager.

The local map is ignored by Git because destinations can reveal private organization
structure. The historical `slug` field remains accepted for Yandex maps, but new maps
should use `destination`.

```json
{
  "publisher": "notion",
  "pages": [
    {
      "source": "wiki/out/01-roadmap.md",
      "destination": "page:01234567-89ab-cdef-0123-456789abcdef",
      "title": "Roadmap"
    }
  ]
}
```

## Dry run

```bash
python scripts/publish_docs.py --map config/wiki_publish_map.json
```

Dry-run mode performs target lookup where applicable and reports `would_update`,
`would_create`, or `missing`. It does not write page content.

## Apply

```bash
python scripts/publish_docs.py --apply --map config/wiki_publish_map.json
```

Add `--create-missing` only when the map intentionally contains creation targets. Apply
runs copy generated Markdown into a timestamped local snapshot and retain content hashes to
skip unchanged pages. Snapshots are not backups of remote revision history.

`scripts/publish_wiki.py` remains as a compatibility wrapper around `publish_docs.py`.

## Single-page examples

```bash
# Yandex Wiki slug
doc-harvester publish wiki/out/page.md docs/page --publisher yandex-wiki

# Confluence page title lookup/update
doc-harvester publish wiki/out/page.md 'title:Roadmap' --publisher confluence --apply

# Confluence child creation
doc-harvester publish wiki/out/page.md 'parent:123456/Roadmap' \
  --publisher confluence --apply --create-missing

# Notion existing page replacement
doc-harvester publish wiki/out/page.md 'page:01234567-89ab-cdef-0123-456789abcdef' \
  --publisher notion --apply

# Notion child creation
doc-harvester publish wiki/out/page.md 'parent:01234567-89ab-cdef-0123-456789abcdef' \
  --publisher notion --title Roadmap --apply --create-missing
```

## Access control

Automation updates content only. It does not modify access lists, sharing links, groups,
guests, or public visibility. Before apply mode:

- grant the API connection only the pages or spaces it needs;
- ensure a creation parent has the intended private permissions;
- use least-privilege service credentials;
- rely on the documentation service's revision history for rollback.

## Dependencies

The batch script loads `.env` through the `wiki` extra. Confluence additionally needs its
Markdown converter:

```bash
python -m pip install -e '.[wiki]'
python -m pip install -e '.[wiki,confluence]'
```
