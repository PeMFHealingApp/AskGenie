"""Official MCP SDK transport mounted alongside the existing Flask REST API."""

import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.applications import Starlette
from starlette.middleware.wsgi import WSGIMiddleware
from starlette.routing import Mount

from api import app, catalog, catalog_stats, search_catalog

mcp = FastMCP(
    "AskGenie",
    instructions="Search the live PEMF program catalog. Use exact returned URLs. Catalog titles are not evidence of clinical efficacy.",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["ask-genie.onrender.com", "localhost:*", "127.0.0.1:*"],
        allowed_origins=["https://ask-genie.onrender.com", "https://chatgpt.com", "https://chat.openai.com"],
    ),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def search_programs(
    query: Annotated[str, Field(min_length=1, max_length=300)],
    category: Annotated[str | None, Field(max_length=100)] = None,
    limit: Annotated[int, Field(ge=1, le=50)] = 5,
) -> dict[str, Any]:
    """Find programs by topic or exact title. All query terms must match. Use category as a separate filter, e.g. amino-acid or vitamins. Retry a simpler term if empty. URLs are returned verbatim from the catalog; verify selected links before presenting them."""
    if not query.strip():
        raise ValueError("query must not be blank")
    matches = search_catalog(query, category)
    return {"query": query, "category": category, "total_matches": len(matches), "programs": matches[:limit]}


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def get_catalog_stats() -> dict[str, Any]:
    """Get the current searchable catalog count and category filters. This count does not represent every program in the entire PEMF Healing App."""
    return catalog_stats()


ALLOWED_PROGRAM_HOSTS = {"www.epemf.app", "epemf.app"}


def validate_program_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_PROGRAM_HOSTS or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError("Only HTTPS program links on epemf.app are allowed")


class ProgramRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_program_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True), structured_output=True)
def verify_program_link(url: Annotated[str, Field(min_length=1, max_length=2000)]) -> dict[str, Any]:
    """Check HTTP reachability of one exact catalog URL. Never accepts arbitrary websites. HTTP success does not verify subscription access, playback, or medical effectiveness."""
    if not any(p["Full URL"] == url for p in catalog):
        raise ValueError("URL must exactly match a Full URL returned by search_programs")
    validate_program_url(url)
    opener = urllib.request.build_opener(ProgramRedirectHandler())
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AskGenie/1.1"})
        with opener.open(req, timeout=8) as response:
            return {"url": url, "reachable": 200 <= response.status < 300, "http_status": response.status, "final_url": response.url}
    except urllib.error.HTTPError as error:
        return {"url": url, "reachable": False, "http_status": error.code}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return {"url": url, "reachable": False, "http_status": None, "error": "Link verification could not complete"}


@asynccontextmanager
async def lifespan(application):
    async with mcp.session_manager.run():
        yield


asgi_app = Starlette(
    routes=[Mount("/mcp", app=mcp.streamable_http_app()), Mount("/", app=WSGIMiddleware(app))],
    lifespan=lifespan,
)
