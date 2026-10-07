"""Read-only PEMF program catalog, shared by REST and MCP."""

import json
import os
import re
import unicodedata
from pathlib import Path

from flask import Flask, Response, jsonify, request

app = Flask(__name__)

OPENAI_APPS_CHALLENGE_TOKEN = (
    "Mus-ndCB2Yigi1XiG5UzqFG7hiLe4cOXbux7vHQh3nA"
)


@app.get("/.well-known/openai-apps-challenge")
def openai_apps_challenge():
    """Serve the exact public token for OpenAI domain verification."""
    return Response(
        OPENAI_APPS_CHALLENGE_TOKEN,
        status=200,
        content_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


CATALOG_PATH = Path(__file__).resolve().with_name("programs_cleaned.json")
with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
    programs = json.load(catalog_file)


def normalize_program(program):
    """Support original catalog records and older editor exports without rewriting data."""
    categories = program.get("Categories")
    if not isinstance(categories, list):
        categories = program.get("Category", program.get("category", ""))
        categories = categories.split(",") if isinstance(categories, str) else []
    categories = list(
        dict.fromkeys(
            c.strip()
            for c in categories
            if isinstance(c, str) and c.strip()
        )
    )
    return {
        "Program Title": program.get(
            "Program Title", program.get("title", "")
        ),
        "Full URL": program.get("Full URL", program.get("url", "")),
        "Category": ", ".join(categories),
        "Categories": categories,
    }


catalog = [normalize_program(p) for p in programs]

PLURALS = {
    "vitamins": "vitamin",
    "acids": "acid",
    "meridians": "meridian",
    "nerves": "nerve",
}

QUERY_ALIASES = {
    "backpain": ("back pain", "lower back", "lumbar"),
    "back pain": ("back pain", "lower back", "lumbar"),
    "hrv": ("hrv", "heart rate variability"),
    "spine": ("spine", "spinal", "neurospinal"),
}


def words(value):
    normalized = unicodedata.normalize("NFKD", value.casefold())
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return tuple(PLURALS.get(token, token) for token in tokens)


indexed_catalog = [
    (
        p,
        words(p["Program Title"]),
        words(" ".join(p["Categories"])),
    )
    for p in catalog
]


def search_catalog(query, category=None, limit=None):
    """Require all query tokens; rank exact title phrases above category matches."""
    query = query.strip()
    if not query or len(query) > 300:
        return []

    original = words(query)
    if not original:
        return []

    variants = QUERY_ALIASES.get(" ".join(original), (query,))
    variants = list(
        dict.fromkeys([original] + [words(v) for v in variants])
    )
    category_tokens = set(words(category)) if category else set()

    matches = []
    seen_urls = set()

    for program, title_tokens, category_words in indexed_catalog:
        if category_tokens and not category_tokens.issubset(
            set(category_words)
        ):
            continue

        best_score = None

        for variant_index, tokens in enumerate(variants):
            query_set = set(tokens)
            if not query_set.issubset(
                set(title_tokens) | set(category_words)
            ):
                continue

            phrase = " ".join(tokens)
            title = " ".join(title_tokens)
            phrase_match = f" {phrase} " in f" {title} "

            score = (
                1000 * (title == phrase)
                + 500 * phrase_match
                + 100 * query_set.issubset(set(title_tokens))
                + 20 * len(query_set & set(title_tokens))
                - 10 * variant_index
            )
            best_score = (
                score
                if best_score is None
                else max(best_score, score)
            )

        if (
            best_score is not None
            and program["Full URL"] not in seen_urls
        ):
            seen_urls.add(program["Full URL"])
            matches.append(
                (
                    best_score,
                    len(title_tokens),
                    program["Program Title"].casefold(),
                    program,
                )
            )

    matches.sort(
        key=lambda match: (-match[0], match[1], match[2])
    )
    results = [match[3] for match in matches]
    return results if limit is None else results[:limit]


def catalog_stats():
    return {
        "program_count": len(catalog),
        "unique_url_count": len(
            {
                p["Full URL"]
                for p in catalog
                if p["Full URL"]
            }
        ),
        "categories": sorted(
            {
                c
                for p in catalog
                for c in p["Categories"]
            }
        ),
        "scope": (
            "AskGenie searchable catalog, not a count of every "
            "program in the PEMF Healing App"
        ),
    }


@app.get("/programs")
def get_programs():
    query = request.args.get("q", "").strip()

    if len(query) > 300:
        return jsonify(
            {"error": "q must contain at most 300 characters"}
        ), 400

    limit = request.args.get("limit")
    if limit is not None:
        try:
            limit = int(limit)
        except ValueError:
            return jsonify(
                {"error": "limit must be an integer from 1 to 100"}
            ), 400

        if not 1 <= limit <= 100:
            return jsonify(
                {"error": "limit must be an integer from 1 to 100"}
            ), 400

    return jsonify(
        search_catalog(query, request.args.get("category"), limit)
    )


@app.get("/programs/stats")
def get_program_stats():
    return jsonify(catalog_stats())


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "version": "1.1.0",
            "program_count": len(catalog),
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Preserve the existing start command and expose REST + MCP.
    uvicorn.run(
        "mcp_server:asgi_app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
    )
