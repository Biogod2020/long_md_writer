#!/usr/bin/env python3
"""Live Bing Images smoke probe.

This script is intentionally opt-in. It verifies that a runner can retrieve a Bing
Images result page, parse original-image/source-page metadata, download one original
image, and validate its physical bytes with Pillow. It is not run by unit tests.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import html as html_std
from io import BytesIO
import json
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

from lxml import html as lxml_html
from PIL import Image


DEFAULT_QUERY = "cardiac conduction system diagram site:commons.wikimedia.org"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0 Safari/537.36"
)
MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class BingCandidate:
    image_url: str
    source_url: str | None
    title: str | None
    thumbnail_url: str | None


@dataclass(frozen=True)
class SelectedImage:
    image_url: str
    source_url: str | None
    title: str | None
    thumbnail_url: str | None
    downloaded_path: str
    content_type: str
    byte_count: int
    width: int
    height: int
    image_format: str
    sha256: str


def build_search_url(query: str) -> str:
    return "https://www.bing.com/images/search?" + urllib.parse.urlencode(
        {
            "q": query,
            "form": "HDRSC2",
            "first": "1",
            "safeSearch": "Strict",
        }
    )


def _open(url: str, *, accept: str, referer: str | None = None, timeout: int = 30):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=headers),
        timeout=timeout,
    )


def fetch_bing_candidates(query: str) -> tuple[str, bytes, list[BingCandidate], dict[str, Any]]:
    search_url = build_search_url(query)
    with _open(search_url, accept="text/html,application/xhtml+xml") as response:
        page_bytes = response.read(MAX_PAGE_BYTES + 1)
        metadata = {
            "status": response.status,
            "content_type": response.headers.get("Content-Type", ""),
        }
    if len(page_bytes) > MAX_PAGE_BYTES:
        raise RuntimeError("Bing result page exceeded the configured byte limit")

    page_text = page_bytes.decode("utf-8", errors="replace")
    root = lxml_html.fromstring(page_text)
    candidates: list[BingCandidate] = []
    seen: set[tuple[str, str | None]] = set()
    xpath = "//a[contains(concat(' ', normalize-space(@class), ' '), ' iusc ')][@m]"
    for node in root.xpath(xpath):
        try:
            payload = json.loads(html_std.unescape(node.attrib["m"]))
        except Exception:
            continue
        image_url = payload.get("murl")
        source_url = payload.get("purl")
        if not isinstance(image_url, str) or not image_url.startswith(("http://", "https://")):
            continue
        source = source_url if isinstance(source_url, str) else None
        key = (image_url, source)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            BingCandidate(
                image_url=image_url,
                source_url=source,
                title=payload.get("t") if isinstance(payload.get("t"), str) else None,
                thumbnail_url=(
                    payload.get("turl") if isinstance(payload.get("turl"), str) else None
                ),
            )
        )
    return search_url, page_bytes, candidates, metadata


def _suffix_for(image_format: str) -> str:
    return {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
        "GIF": ".gif",
        "TIFF": ".tiff",
    }.get(image_format, ".img")


def download_first_valid(
    candidates: list[BingCandidate],
    *,
    search_url: str,
    output_dir: Path,
    max_candidates: int,
    min_width: int,
    min_height: int,
) -> tuple[SelectedImage | None, list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    for candidate in candidates[:max_candidates]:
        try:
            with _open(
                candidate.image_url,
                accept="image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                referer=search_url,
            ) as response:
                content_type = (
                    response.headers.get("Content-Type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_IMAGE_BYTES:
                    raise ValueError(f"declared image too large: {declared}")
                data = response.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError("image exceeded byte limit")
            if not content_type.startswith("image/"):
                raise ValueError(f"unexpected content type: {content_type}")

            with Image.open(BytesIO(data)) as image:
                image.verify()
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                image_format = (image.format or "").upper()
            if width < min_width or height < min_height:
                raise ValueError(f"image too small: {width}x{height}")

            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / f"selected{_suffix_for(image_format)}"
            image_path.write_bytes(data)
            return (
                SelectedImage(
                    image_url=candidate.image_url,
                    source_url=candidate.source_url,
                    title=candidate.title,
                    thumbnail_url=candidate.thumbnail_url,
                    downloaded_path=image_path.as_posix(),
                    content_type=content_type,
                    byte_count=len(data),
                    width=width,
                    height=height,
                    image_format=image_format,
                    sha256=hashlib.sha256(data).hexdigest(),
                ),
                failures,
            )
        except Exception as exc:
            failures.append(
                {
                    "image_url": candidate.image_url,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return None, failures


def run_probe(
    *,
    query: str,
    output_dir: Path,
    max_candidates: int = 40,
    min_width: int = 400,
    min_height: int = 250,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    search_url, page_bytes, candidates, page_metadata = fetch_bing_candidates(query)
    (output_dir / "search-page.html").write_bytes(page_bytes)
    selected, failures = download_first_valid(
        candidates,
        search_url=search_url,
        output_dir=output_dir,
        max_candidates=max_candidates,
        min_width=min_width,
        min_height=min_height,
    )
    result: dict[str, Any] = {
        "query": query,
        "search_url": search_url,
        "search_status": page_metadata["status"],
        "search_content_type": page_metadata["content_type"],
        "search_page_bytes": len(page_bytes),
        "candidate_count": len(candidates),
        "selected": asdict(selected) if selected else None,
        "first_failures": failures[:10],
    }
    (output_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--output", type=Path, default=Path("bing-smoke"))
    parser.add_argument("--max-candidates", type=int, default=40)
    parser.add_argument("--min-width", type=int, default=400)
    parser.add_argument("--min-height", type=int, default=250)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_probe(
        query=args.query,
        output_dir=args.output,
        max_candidates=args.max_candidates,
        min_width=args.min_width,
        min_height=args.min_height,
    )
    print("BING_IMAGE_SMOKE_RESULT=" + json.dumps(result, ensure_ascii=False))
    return 0 if result["selected"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
