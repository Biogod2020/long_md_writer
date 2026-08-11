#!/usr/bin/env python3
"""Live Bing Images smoke probe with relevance and source constraints.

This script is intentionally opt-in. It verifies that a runner can retrieve Bing
Images result pages, rank candidates against the requested subject, enforce any
``site:`` restriction, download an original image, and validate its bytes with
Pillow. A merely downloadable but irrelevant image is a failure.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import html as html_std
from io import BytesIO
import json
from pathlib import Path
import re
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
SITE_PATTERN = re.compile(r"(?:^|\s)site:([^\s]+)", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
GENERIC_TERMS = {
    "a",
    "an",
    "and",
    "diagram",
    "figure",
    "image",
    "images",
    "illustration",
    "of",
    "the",
    "to",
}


@dataclass(frozen=True)
class BingCandidate:
    image_url: str
    source_url: str | None
    title: str | None
    thumbnail_url: str | None


@dataclass(frozen=True)
class RankedCandidate:
    candidate: BingCandidate
    relevance_score: int
    matched_terms: tuple[str, ...]
    query_used: str
    search_url: str


@dataclass(frozen=True)
class SelectedImage:
    image_url: str
    source_url: str | None
    title: str | None
    thumbnail_url: str | None
    query_used: str
    search_url: str
    relevance_score: int
    matched_terms: tuple[str, ...]
    downloaded_path: str
    content_type: str
    byte_count: int
    width: int
    height: int
    image_format: str
    sha256: str


def build_search_url(query: str) -> str:
    # Do not pass a ``form`` token: it can bind the request to stale UI state.
    return "https://www.bing.com/images/search?" + urllib.parse.urlencode(
        {
            "q": query,
            "first": "1",
            "count": "100",
            "mkt": "en-US",
            "setlang": "en-US",
            "cc": "US",
            "adlt": "strict",
        }
    )


def _open(url: str, *, accept: str, referer: str | None = None, timeout: int = 30):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
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


def _site_constraint(query: str) -> str | None:
    match = SITE_PATTERN.search(query)
    return match.group(1).strip(".").casefold() if match else None


def _base_query(query: str) -> str:
    return " ".join(SITE_PATTERN.sub(" ", query).replace('"', " ").split())


def _query_terms(query: str) -> tuple[str, ...]:
    terms = {
        token.casefold()
        for token in TOKEN_PATTERN.findall(_base_query(query))
        if len(token) >= 3 and token.casefold() not in GENERIC_TERMS
    }
    return tuple(sorted(terms))


def _query_variants(query: str) -> list[str]:
    base = _base_query(query)
    site = _site_constraint(query)
    variants = [query]
    if site:
        variants.append(f"{base} Wikimedia Commons")
    variants.append(base)
    if re.search(r"\bcardiac\b", base, re.IGNORECASE):
        variants.append(
            re.sub(r"\bcardiac\b", "heart", base, flags=re.IGNORECASE)
            + " anatomy illustration Wikimedia Commons"
        )
    output: list[str] = []
    for value in variants:
        value = " ".join(value.split())
        if value and value not in output:
            output.append(value)
    return output


def _host(url: str | None) -> str:
    if not url:
        return ""
    try:
        return (urllib.parse.urlsplit(url).hostname or "").casefold().strip(".")
    except ValueError:
        return ""


def _matches_site(candidate: BingCandidate, site: str | None) -> bool:
    if not site:
        return True
    hosts = {_host(candidate.source_url), _host(candidate.image_url)}
    accepted = {site}
    if site == "commons.wikimedia.org":
        accepted.update({"upload.wikimedia.org", "wikimedia.org"})
    return any(
        host == domain or host.endswith("." + domain)
        for host in hosts
        for domain in accepted
        if host
    )


def rank_candidates(
    candidates: list[BingCandidate],
    *,
    original_query: str,
    query_used: str,
    search_url: str,
) -> list[RankedCandidate]:
    terms = _query_terms(original_query)
    site = _site_constraint(original_query)
    minimum_overlap = min(2, len(terms))
    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        if not _matches_site(candidate, site):
            continue
        searchable = " ".join(
            value for value in (candidate.title, candidate.source_url, candidate.image_url) if value
        ).casefold()
        matched = tuple(term for term in terms if term in searchable)
        if len(matched) < minimum_overlap:
            continue
        score = len(matched) * 3
        if site:
            score += 10
        if candidate.title:
            title = candidate.title.casefold()
            score += sum(1 for term in matched if term in title)
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                relevance_score=score,
                matched_terms=matched,
                query_used=query_used,
                search_url=search_url,
            )
        )
    return sorted(ranked, key=lambda item: item.relevance_score, reverse=True)


def _suffix_for(image_format: str) -> str:
    return {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
        "GIF": ".gif",
        "TIFF": ".tiff",
    }.get(image_format, ".img")


def download_first_valid(
    candidates: list[RankedCandidate],
    *,
    output_dir: Path,
    max_candidates: int,
    min_width: int,
    min_height: int,
) -> tuple[SelectedImage | None, list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    for ranked in candidates[:max_candidates]:
        candidate = ranked.candidate
        try:
            with _open(
                candidate.image_url,
                accept="image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                referer=ranked.search_url,
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
                    query_used=ranked.query_used,
                    search_url=ranked.search_url,
                    relevance_score=ranked.relevance_score,
                    matched_terms=ranked.matched_terms,
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
    attempts: list[dict[str, Any]] = []
    combined: list[RankedCandidate] = []
    for index, query_used in enumerate(_query_variants(query), start=1):
        search_url, page_bytes, candidates, page_metadata = fetch_bing_candidates(query_used)
        (output_dir / f"search-page-{index:02d}.html").write_bytes(page_bytes)
        ranked = rank_candidates(
            candidates,
            original_query=query,
            query_used=query_used,
            search_url=search_url,
        )
        combined.extend(ranked)
        attempts.append(
            {
                "query": query_used,
                "search_url": search_url,
                "status": page_metadata["status"],
                "content_type": page_metadata["content_type"],
                "page_bytes": len(page_bytes),
                "candidate_count": len(candidates),
                "relevant_candidate_count": len(ranked),
                "top_relevant": [
                    {
                        "title": item.candidate.title,
                        "source_url": item.candidate.source_url,
                        "image_url": item.candidate.image_url,
                        "score": item.relevance_score,
                        "matched_terms": item.matched_terms,
                    }
                    for item in ranked[:5]
                ],
            }
        )

    deduplicated: dict[tuple[str, str | None], RankedCandidate] = {}
    for item in combined:
        key = (item.candidate.image_url, item.candidate.source_url)
        previous = deduplicated.get(key)
        if previous is None or item.relevance_score > previous.relevance_score:
            deduplicated[key] = item
    ranked_candidates = sorted(
        deduplicated.values(),
        key=lambda item: item.relevance_score,
        reverse=True,
    )
    selected, failures = download_first_valid(
        ranked_candidates,
        output_dir=output_dir,
        max_candidates=max_candidates,
        min_width=min_width,
        min_height=min_height,
    )
    result: dict[str, Any] = {
        "query": query,
        "required_site": _site_constraint(query),
        "query_terms": _query_terms(query),
        "attempts": attempts,
        "relevant_candidate_count": len(ranked_candidates),
        "selected": asdict(selected) if selected else None,
        "first_download_failures": failures[:10],
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
