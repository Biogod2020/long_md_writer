from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from dsh_bing_search.service import (
    find_in_webpage,
    open_web,
    search_images_web,
    search_web,
)


async def run(operation: str, payload: dict[str, Any]) -> Any:
    if operation == "search":
        return await search_web(
            payload["query"],
            count=payload.get("count", 8),
            offset=payload.get("offset", 0),
            market=payload.get("market", "en-US"),
            safe_search=payload.get("safe_search", "Moderate"),
        )
    if operation == "search_images":
        return await search_images_web(
            payload["query"],
            count=payload.get("count", 8),
            market=payload.get("market", "en-US"),
            provider=payload.get("provider", "auto"),
        )
    if operation == "open":
        return await open_web(payload["url"], max_chars=payload.get("max_chars", 24000))
    if operation == "find":
        return await find_in_webpage(
            payload["url"],
            payload["pattern"],
            max_matches=payload.get("max_matches", 5),
            context_chars=payload.get("context_chars", 700),
        )
    raise ValueError(f"unknown search operation: {operation}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: search-tool.py OPERATION")
    payload = json.load(sys.stdin)
    result = asyncio.run(run(sys.argv[1], payload))
    sys.stdout.write(result.model_dump_json())


if __name__ == "__main__":
    main()
