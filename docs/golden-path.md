# Credential-free golden path

This walkthrough validates the universal pipeline locally without accounts, tokens, cloud
services, or remote writes. It deliberately keeps each stage separate so you can inspect
its output before continuing.

## 1. Prepare the project

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
mkdir -p /tmp/doc-harvester-golden-path
```

If `.venv` already exists, activate it instead of recreating it. The commands below refuse
to overwrite previous outputs, so use a new work directory for another run.

## 2. Start the synthetic documentation site

In a second terminal, from the repository root:

```bash
python3 -m http.server 8765 \
  --bind 127.0.0.1 \
  --directory examples/golden-path/site
```

Keep this terminal open. The server is reachable only from your computer. The fixture has
HTML, XML, text, and one robots-protected page. Automated E2E coverage additionally serves
synthetic PDF, DOCX, and XLSX fixtures.

## 3. Crawl into a manifest

In the first terminal:

```bash
doc-harvester source crawl http://127.0.0.1:8765/ \
  --delay 0 --limit 20 \
  --output /tmp/doc-harvester-golden-path/crawl.json
```

Open `crawl.json` in your editor. It should contain four resources and report one
robots-protected URL. Full resource URLs are intentionally present in manifests; review
them before sharing a real crawl report.

## 4. Process and inspect

```bash
doc-harvester source process \
  /tmp/doc-harvester-golden-path/crawl.json \
  --output /tmp/doc-harvester-golden-path/dataset

doc-harvester source inspect \
  /tmp/doc-harvester-golden-path/dataset
```

Inspection prints counts, formats, and quality findings without document bodies or source
URLs. A quality warning is review information; it is not silently hidden or automatically
published.

## 5. Store locally

```bash
doc-harvester source store \
  /tmp/doc-harvester-golden-path/dataset \
  --storage local \
  --local-root /tmp/doc-harvester-golden-path/storage \
  --destination tutorial/run-001
```

This validates the dataset again and copies it only to the explicit local storage root.
Running the command again without `--overwrite` must fail and preserve the stored copy.

## 6. Render and preview publication

Select a processed index from the inspection result, then run:

```bash
doc-harvester source render \
  /tmp/doc-harvester-golden-path/dataset \
  --document-index 0 \
  --output /tmp/doc-harvester-golden-path/review.md

doc-harvester publish \
  /tmp/doc-harvester-golden-path/review.md \
  tutorial/review \
  --publisher local \
  --local-root /tmp/doc-harvester-golden-path/published
```

Open `review.md` and inspect its content and quality status. The final command is a dry run:
it should report `would_create` and must not create the publication. Adding `--apply` is a
separate decision and is outside this golden-path test.

## 7. Verify the restart boundary

Run the processing command from step 4 again with the same output path. It should fail with
`output already exists` before fetching anything. The original manifest and dataset remain
the checkpoint from which inspection, storage, or rendering can be repeated safely.

Stop the local web server with `Ctrl+C` when finished. The entire work directory is
disposable and contains no credentials, but it may still contain source URLs and extracted
text; review it before retaining or sharing it.
