# Test a Notion Connection Safely

This walkthrough verifies that `doc-harvester` can authenticate with Notion and see one
specific page. The first test is a dry run: it makes a read-only API request and does not
change the page or upload the selected Markdown file.

## 1. Create the Python environment and install the publishing dependency

From the repository root, create a Python 3.11 virtual environment. You only need to run
the first command once:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[wiki]'
```

After activation, the beginning of the terminal prompt normally shows `(.venv)`. The
`python` command becomes available inside this environment. In a new terminal session,
run only `source .venv/bin/activate` to reactivate it.

## 2. Create a Notion connection

1. Open the [Notion Developer portal](https://www.notion.so/profile/integrations).
2. Open **Connections** and select **+ New connection**.
3. For **Connection name**, enter a name such as `doc-harvester-test`.
4. For **Authentication method**, select **Access token**. Do not select OAuth: OAuth is
   intended for an application that asks multiple users to authorize their own Notion
   workspaces, while this test is a local script connecting directly to your workspace.
5. For **Where to install**, select the workspace that contains the Notion test page.
6. Select **Create connection**.
7. After creation, open **Configuration** and enable **Read content**. You do not need
   update or insert capabilities for the first dry run.
8. Copy the **Installation access token**. Treat it like a password.

Creating an internal connection normally requires the Notion **Workspace Owner** role. If
you are not an owner, ask an owner to create the connection or use a personal access token
with read-content capability.

## 3. Give the connection access to one test page

Create or choose a harmless Notion page, for example `doc-harvester connection test`.
Then grant the connection access using either method:

- In the Developer portal, open the connection's **Content access** tab, choose
  **Edit access**, and select the test page.
- In Notion, open the page, select `•••` in the top-right, then **Connections**,
  **Add connection**, and select `doc-harvester-test`.

A new connection has no page access until you do this. Sharing a parent page also gives
the connection access to its child pages.

## 4. Put the token in the local `.env`

If `.env` does not exist yet, create it from the example:

```bash
cp .env.example .env
```

The leading dot makes `.env` a hidden file on macOS. The simplest reliable way to edit it
is with the Terminal text editor `nano`:

```bash
nano .env
```

Use the arrow keys to find `NOTION_TOKEN=` and paste the token immediately after the `=`:

```dotenv
NOTION_TOKEN=your_installation_access_token
```

Then save and close the file:

1. Press **Control+O** (the letter O) to save.
2. Press **Return** to confirm the `.env` filename.
3. Press **Control+X** to exit `nano`.

To confirm that the file exists without displaying its secret contents, run:

```bash
ls -l .env
```

If you prefer Finder, open the repository folder and press **Command+Shift+.** (period) to
show hidden files. Press the same shortcut again when you want to hide them.

Do not add quotes or spaces around the token. `.env` is ignored by Git; never paste the
token into the JSON map, a command, an issue, or a commit.

## 5. Copy the page ID

Open the test page in Notion and use **Copy link**. The page ID is the 32-character string
at the end of the page URL, before any query parameters. For example:

```text
https://www.notion.so/doc-harvester-test-0123456789abcdef0123456789abcdef?pvs=4
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

Both forms are accepted:

```text
0123456789abcdef0123456789abcdef
01234567-89ab-cdef-0123-456789abcdef
```

## 6. Create the local publish map

This file does not come with the repository because it contains your private Notion page
ID. First confirm that the terminal is in the `doc-harvester` repository:

```bash
pwd
```

The output should end with `/doc-harvester`. To check without relying on a personal
filesystem path, run:

```bash
basename "$PWD"
```

The output must be `doc-harvester`.

Now create and open the map in this repository's `config` folder:

```bash
nano config/wiki_publish_map.json
```

Paste the following content, replacing the example ID with the ID from your page:

```json
{
  "publisher": "notion",
  "pages": [
    {
      "source": "README.md",
      "destination": "page:01234567-89ab-cdef-0123-456789abcdef",
      "title": "doc-harvester connection test"
    }
  ]
}
```

Save it by pressing **Control+O**, **Return**, and then **Control+X**.

Confirm that the file exists:

```bash
ls -l config/wiki_publish_map.json
```

Then check that its JSON syntax is valid:

```bash
python -m json.tool config/wiki_publish_map.json
```

The validation command should print the formatted JSON without an error. This file is
ignored by Git because real destinations can reveal private workspace structure.

## 7. Run the read-only connection test

Run this command exactly as shown. Do **not** add `--apply`:

```bash
python scripts/publish_docs.py --map config/wiki_publish_map.json
```

The command prints the path of a JSON report under `runs/`. Open that report and find the
result for `README.md`.

Success looks like this:

```json
{
  "provider": "notion",
  "destination": "page:01234567-89ab-cdef-0123-456789abcdef",
  "status": "would_update"
}
```

The one-line terminal summary may count this preview as `skipped=1`; that only means no
write was applied. The JSON report's `would_update` status is the connection-test result.

`would_update` means all of the following worked:

- Python loaded the token from `.env`;
- Notion accepted the token;
- the connection can see the target page;
- the destination ID is valid.

The dry run does not compare or upload the Markdown content. It only verifies that the
existing target can be reached.

## Troubleshooting

### `NOTION_TOKEN is required`

Confirm that the file is named `.env`, is in the repository root, and contains a non-empty
`NOTION_TOKEN=` value. Run the command from the repository root.

### `No such file or directory: 'config/wiki_publish_map.json'`

The local publish map has not been created yet. Return to step 6, run
`nano config/wiki_publish_map.json`, paste the JSON map, replace the example page ID, and
save the file.

### `401 Unauthorized`

The token is invalid, expired, or was copied incorrectly. Copy the installation access
token again from the connection's **Configuration** tab. If the token was exposed, refresh
it in Notion and replace the value in `.env`.

### `403 Forbidden`

Enable **Read content** in the connection's capabilities. The Notion user granting access
must also have permission to read the page.

### `missing` or `404 Client Error`

Notion uses `404` both for a wrong page ID and for a page that the connection cannot see.
Check the ID, then add the connection to that exact page or one of its parents.

### `ModuleNotFoundError: No module named 'dotenv'`

Activate the intended virtual environment and install the publishing dependency again:

```bash
python3.11 -m venv .venv  # only if .venv does not exist
source .venv/bin/activate
python -m pip install -e '.[wiki]'
```

## Optional: perform a real write test

Only continue after the dry-run report says `would_update`. The following command replaces
the test page's body with the contents of `README.md` and may also rename the page from the
map's `title` value:

```bash
python scripts/publish_docs.py --map config/wiki_publish_map.json --apply
```

Before running it, enable **Update content** for the connection and use a disposable page.
Do not test apply mode on a page containing child pages, child databases, or content you
need to keep. The publisher intentionally does not request Notion's option for deleting
child content, so Notion should reject unsafe full-page replacement rather than remove it.

Creating a new child page is a separate test. It requires **Insert content**, a
`parent:<page-id>` destination, and both `--apply` and `--create-missing`.

## Official Notion references

- [Internal connections](https://developers.notion.com/guides/get-started/internal-connections)
- [Connection capabilities](https://developers.notion.com/reference/capabilities)
- [Working with Markdown content](https://developers.notion.com/guides/data-apis/working-with-markdown-content)
