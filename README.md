# AskGenie

Read-only search API and MCP tools for the PEMF Healing App program catalog.

## Run and deploy

```sh
pip install -r requirements.txt
python api.py
```

The existing `python api.py` start command now starts Uvicorn and serves both the Flask REST routes and the official MCP SDK. It uses Render's `PORT` environment variable, defaulting to 5000 locally. An explicit alternative start command is `uvicorn mcp_server:asgi_app --host 0.0.0.0 --port "$PORT"`. A Flask-only entry point such as `flask run` will not expose MCP.

Keep the existing Render service and its connected main branch. After deployment, check `/health` for version `1.1.0` and initialize the MCP endpoint at `https://ask-genie.onrender.com/mcp/`. The MCP transport is stateless Streamable HTTP with JSON responses, and all tools are read-only. Only the existing public catalog is exposed; no account credentials or private user data are required.

## REST compatibility

- `GET /programs?q=vascular%20flow`: returns the existing JSON array format with exact source titles and URLs. All meaningful query terms must match a title or category. Exact title phrases rank first. The original category array is returned as `Categories`, with a comma-separated `Category` display field for older callers.
- `GET /programs?q=collagen&category=amino-acid&limit=5`: uses a separate category filter and an optional result limit from 1 to 100.
- `GET /programs/stats`: returns the current searchable catalog count and category values. This is not a platform-wide program count.
- `GET /health`: health check and backend version.

Blank and unmatched queries return an empty array. Search does not fabricate links or silently broaden every multiword query to unrelated single-word matches. Explicit aliases support backpain, back pain, HRV, and spine searches. Catalog records using the older lowercase editor fields or singular `Category` remain readable.

## MCP tools

Connect a Streamable HTTP client to `/mcp/`:

- `search_programs(query, category=None, limit=5)`: ranked matches, category metadata, and total match count. Limit is 1 to 50.
- `get_catalog_stats()`: live count and available category filters.
- `verify_program_link(url)`: checks HTTP reachability for an exact catalog URL. It rejects arbitrary URLs and redirects outside the permitted epemf.app hosts. Reachability does not establish subscription access, playback, or clinical effectiveness.

`luma-plugin/` contains the source for the existing Luma Assist plugin, with its original identity, icon, and skill. Its MCP configuration targets this same service, rather than a new backend. Plugin publishing remains a separate Plugin Creator operation.

## Validation

```sh
python -m unittest discover -s tests -v
```

Tests cover search precision, ranking, category filters, aliases, exact URL preservation, legacy schema compatibility, catalog counts, REST compatibility, MCP initialization and tool calls, input validation, and restricted link verification.
