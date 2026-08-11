"""Control-plane browser evidence generated independently of Codex."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import unquote, urlparse

from lxml import html as lxml_html

from .state_store import StateStore


_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _local_path(workspace: Path, raw: str, *, base: Path | None = None) -> Path | None:
    value = unquote(raw.strip())
    parsed = urlparse(value)
    if not value or value.startswith("#") or parsed.scheme or value.startswith("//"):
        return None
    root = base if base is not None else workspace
    candidate = (root / parsed.path).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError:
        return None
    if candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _inline_css_urls(css: str, workspace: Path, base: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        raw = match.group(2).strip()
        path = _local_path(workspace, raw, base=base)
        return f'url("{_data_uri(path)}")' if path is not None else match.group(0)

    return _CSS_URL.sub(replace, css)


def _renderable_html(workspace: Path, source: str) -> str:
    """Inline local runtime resources so browser rendering needs no network or file URLs."""

    document = lxml_html.document_fromstring(source)
    head_nodes = document.xpath("//head")
    head = head_nodes[0] if head_nodes else None

    for link in list(document.xpath("//link[@href]")):
        rel = {item.casefold() for item in (link.get("rel") or "").split()}
        path = _local_path(workspace, link.get("href") or "")
        if "stylesheet" not in rel or path is None:
            continue
        css = path.read_text(encoding="utf-8")
        style = lxml_html.Element("style")
        style.text = _inline_css_urls(css, workspace, path.parent)
        link.getparent().replace(link, style)

    for script in document.xpath("//script[@src]"):
        path = _local_path(workspace, script.get("src") or "")
        if path is None:
            continue
        script.attrib.pop("src", None)
        script.text = path.read_text(encoding="utf-8")

    for element in document.xpath("//*[@src or @poster]"):
        for attribute in ("src", "poster"):
            raw = element.get(attribute)
            if not raw:
                continue
            path = _local_path(workspace, raw)
            if path is not None:
                element.set(attribute, _data_uri(path))

    for element in document.xpath("//*[@srcset]"):
        converted: list[str] = []
        for candidate in (element.get("srcset") or "").split(","):
            parts = candidate.strip().split()
            if not parts:
                continue
            path = _local_path(workspace, parts[0])
            parts[0] = _data_uri(path) if path is not None else parts[0]
            converted.append(" ".join(parts))
        element.set("srcset", ", ".join(converted))

    for style in document.xpath("//style"):
        style.text = _inline_css_urls(style.text or "", workspace, workspace)
    for element in document.xpath("//*[@style]"):
        element.set(
            "style",
            _inline_css_urls(element.get("style") or "", workspace, workspace),
        )

    if head is not None:
        marker = lxml_html.Element("meta")
        marker.set("name", "magnum-render-transport")
        marker.set("content", "set-content-local-assets-inlined")
        head.append(marker)
    return lxml_html.tostring(document, encoding="unicode", method="html")


async def render_browser_evidence(workspace: Path) -> dict[str, Any]:
    """Render canonical desktop/mobile screenshots with all external traffic blocked."""

    workspace = workspace.resolve()
    final_html = workspace / "final.html"
    qa_dir = workspace / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    report_path = qa_dir / "browser_report.json"
    desktop_path = qa_dir / "render-desktop.png"
    mobile_path = qa_dir / "render-mobile.png"

    report: dict[str, Any] = {
        "schema_version": 2,
        "producer": "python-control-plane",
        "control_plane_generated": True,
        "render_transport": "set-content-local-assets-inlined",
        "status": "fail",
        "final_html_sha256": "",
        "desktop_sha256": "",
        "mobile_sha256": "",
        "views": {},
        "console_errors": [],
        "page_errors": [],
        "request_failures": [],
        "error": None,
    }
    if final_html.is_symlink() or not final_html.is_file():
        report["error"] = "final.html is missing or is a symlink"
        StateStore.atomic_write_json(report_path, report)
        return report

    report["final_html_sha256"] = sha256_file(final_html)
    try:
        source = final_html.read_text(encoding="utf-8")
        render_source = _renderable_html(workspace, source)
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
            if not executable:
                executable = next(
                    (
                        candidate
                        for name in (
                            "chromium",
                            "chromium-browser",
                            "google-chrome",
                            "google-chrome-stable",
                        )
                        if (candidate := shutil.which(name))
                    ),
                    None,
                )
            launch_options: dict[str, Any] = {"headless": True}
            if executable:
                launch_options["executable_path"] = executable
            browser = await playwright.chromium.launch(**launch_options)
            try:
                context = await browser.new_context(java_script_enabled=True)
                page = await context.new_page()
                console_errors: list[str] = []
                page_errors: list[str] = []
                request_failures: list[str] = []

                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on(
                    "requestfailed",
                    lambda request: request_failures.append(
                        f"{request.method} {request.url}: {request.failure}"
                    ),
                )

                async def block_network(route: Any) -> None:
                    url = route.request.url
                    if url.startswith(("about:", "data:", "blob:")):
                        await route.continue_()
                    else:
                        request_failures.append(f"blocked external request: {url}")
                        await route.abort()

                await page.route("**/*", block_network)
                views = {
                    "desktop": ({"width": 1440, "height": 1000}, desktop_path),
                    "mobile": ({"width": 390, "height": 844}, mobile_path),
                }
                measurements: dict[str, Any] = {}
                for name, (viewport, screenshot_path) in views.items():
                    await page.set_viewport_size(viewport)
                    await page.set_content(render_source, wait_until="load", timeout=60_000)
                    await page.evaluate(
                        "document.fonts ? document.fonts.ready : Promise.resolve()"
                    )
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    dimensions = await page.evaluate(
                        """() => ({
                          viewportWidth: window.innerWidth,
                          viewportHeight: window.innerHeight,
                          documentWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
                          documentHeight: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
                          textLength: (document.body.innerText || '').trim().length,
                          imageCount: document.images.length,
                          brokenImages: Array.from(document.images).filter(i => !i.complete || i.naturalWidth === 0).length
                        })"""
                    )
                    dimensions["horizontalOverflow"] = (
                        dimensions["documentWidth"] > dimensions["viewportWidth"] + 2
                    )
                    measurements[name] = dimensions
                report["views"] = measurements
                report["console_errors"] = console_errors
                report["page_errors"] = page_errors
                report["request_failures"] = request_failures
                report["desktop_sha256"] = sha256_file(desktop_path)
                report["mobile_sha256"] = sha256_file(mobile_path)
                report["status"] = (
                    "pass"
                    if not console_errors
                    and not page_errors
                    and not request_failures
                    and all(
                        view["textLength"] > 100
                        and view["documentHeight"] >= view["viewportHeight"]
                        and not view["horizontalOverflow"]
                        and view["brokenImages"] == 0
                        for view in measurements.values()
                    )
                    else "fail"
                )
                await context.close()
            finally:
                await browser.close()
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["status"] = "fail"

    StateStore.atomic_write_json(report_path, report)
    return report


def render_browser_evidence_sync(workspace: Path) -> dict[str, Any]:
    return asyncio.run(render_browser_evidence(workspace))
