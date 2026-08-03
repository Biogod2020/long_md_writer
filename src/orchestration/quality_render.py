"""Publication, HTML security, browser evidence, and QA verification gates."""

from __future__ import annotations

from pathlib import Path
import re

from lxml import html as lxml_html

from .models import CheckResult, QualityReport, StageName, WorkflowMode
from .quality_common import (
    ACTIVE_SCHEME,
    CSS_URL,
    REMOTE,
    build_report,
    check,
    count_words,
    load_plan,
    placeholder_count,
    publication_metrics,
    read_json,
    safe_local,
    sha256_file,
)
from .quality_content import assets_report


def _html_checks(workspace: Path, path: Path) -> list[CheckResult]:
    try:
        source = path.read_text(encoding="utf-8")
        document = lxml_html.document_fromstring(source)
    except Exception as exc:
        return [check("publish.html_parse", False, f"invalid HTML: {exc}")]
    title = document.xpath("string(//title)").strip()
    body_text = " ".join(document.xpath("string(//body)").split())
    checks = [
        check("publish.html_title", bool(title), "HTML requires a title"),
        check("publish.html_semantics", bool(document.xpath("//main|//article")) and bool(document.xpath("//h1")), "HTML requires main/article and h1"),
        check("publish.html_content", count_words(body_text) >= 100, "HTML must contain substantive text"),
        check("publish.html_no_active_embeds", not document.xpath("//iframe|//object|//embed|//form|//meta[translate(@http-equiv,'REFSH','refsh')='refresh']"), "forms, embeds, and meta refresh are forbidden"),
    ]
    handlers = [name for element in document.iter() for name in element.attrib if name.casefold().startswith("on")]
    checks.append(check("publish.html_no_inline_handlers", not handlers, "inline event handlers are forbidden"))
    remote: list[str] = []; unsafe: list[str] = []; broken: list[str] = []
    for element in document.iter():
        for attribute in ("src", "href", "poster", "action", "formaction"):
            raw = element.get(attribute)
            if not raw or raw.startswith("#"):
                continue
            if REMOTE.match(raw): remote.append(raw)
            elif ACTIVE_SCHEME.match(raw) or raw.startswith("data:"): unsafe.append(raw)
            elif safe_local(workspace, raw) is None: broken.append(raw)
        remote.extend(url for _, url in CSS_URL.findall(element.get("style") or "") if REMOTE.match(url))
    for style in document.xpath("//style"):
        remote.extend(url for _, url in CSS_URL.findall(style.text or "") if REMOTE.match(url))
    checks.extend([
        check("publish.html_no_remote_resources", not remote, "remote resources are forbidden", resources=sorted(set(remote))),
        check("publish.html_safe_schemes", not unsafe, "active/data URL schemes are forbidden", resources=sorted(set(unsafe))),
        check("publish.html_local_resources", not broken, "local runtime resources must resolve", resources=sorted(set(broken))),
    ])
    return checks


def publish_report(workspace: Path, mode: WorkflowMode) -> QualityReport:
    plan, error = load_plan(workspace)
    checks: list[CheckResult] = [check("publish.plan", plan is not None, error or "plan is valid")]
    final_md = workspace / "final.md"
    exists = final_md.is_file() and not final_md.is_symlink()
    checks.append(check("publish.final_md", exists, "final.md must exist"))
    words = 0
    if exists:
        text = final_md.read_text(encoding="utf-8"); words = count_words(text)
        target = sum(section.estimated_words for section in plan.sections) if plan else 0
        minimum = max(100, int(target * 0.75))
        checks.extend([
            check("publish.length", words >= minimum, f"final.md has {words} words; requires at least {minimum}"),
            check("publish.placeholders", placeholder_count(text) == 0, "final.md may not contain placeholders"),
            check("publish.no_directives", ":::visual" not in text, "final.md may not contain unresolved visual directives"),
        ])
        if plan:
            coverage = sum(bool(re.search(rf"^##\s+{re.escape(section.title)}\s*$", text, re.M | re.I)) for section in plan.sections)
            checks.append(check("publish.section_coverage", coverage == len(plan.sections), "all planned section headings must appear", present=coverage, expected=len(plan.sections)))
    if mode == WorkflowMode.HTML:
        final_html = workspace / "final.html"
        checks.append(check("publish.final_html", final_html.is_file() and not final_html.is_symlink(), "final.html must exist"))
        if final_html.is_file(): checks.extend(_html_checks(workspace, final_html))
    return build_report(StageName.PUBLISH, checks, {"word_count": words})


def _browser_checks(workspace: Path) -> list[CheckResult]:
    path = workspace / "qa" / "browser_report.json"
    if not path.is_file() or path.is_symlink():
        return [check("qa.browser_report", False, "browser report is missing")]
    try: report = read_json(path)
    except Exception as exc: return [check("qa.browser_report", False, f"invalid browser report: {exc}")]
    desktop = workspace / "qa" / "render-desktop.png"; mobile = workspace / "qa" / "render-mobile.png"
    return [
        check("qa.browser_producer", report.get("producer") == "python-control-plane" and report.get("control_plane_generated") is True, "browser evidence must be control-plane generated"),
        check("qa.browser_status", report.get("status") == "pass", "browser rendering must pass", error=report.get("error")),
        check("qa.browser_html_hash", (workspace / "final.html").is_file() and report.get("final_html_sha256") == sha256_file(workspace / "final.html"), "browser report must bind current final.html"),
        check("qa.browser_desktop_hash", desktop.is_file() and report.get("desktop_sha256") == sha256_file(desktop), "desktop screenshot must be current"),
        check("qa.browser_mobile_hash", mobile.is_file() and report.get("mobile_sha256") == sha256_file(mobile), "mobile screenshot must be current"),
        check("qa.browser_errors", not report.get("console_errors") and not report.get("page_errors") and not report.get("request_failures"), "browser run must have no errors or blocked requests"),
    ]


def qa_report(workspace: Path, mode: WorkflowMode) -> QualityReport:
    checks = publish_report(workspace, mode).checks + assets_report(workspace, mode).checks
    audit = workspace / "qa" / "audit-findings.json"; verifier = workspace / "qa_report.json"
    checks.extend([
        check("qa.audit", audit.is_file() and not audit.is_symlink(), "independent audit report is required"),
        check("qa.verifier", verifier.is_file() and not verifier.is_symlink(), "independent verifier report is required"),
    ])
    if mode == WorkflowMode.HTML: checks.extend(_browser_checks(workspace))
    if audit.is_file() and verifier.is_file():
        try:
            audit_data = read_json(audit); data = read_json(verifier)
            checks.extend([
                check("qa.audit_role", audit_data.get("review_role") == "independent_auditor" and audit_data.get("schema_version") == 2, "audit must identify an independent auditor"),
                check("qa.verifier_role", data.get("review_role") == "independent_verifier" and data.get("schema_version") == 2, "verifier must identify an independent verifier"),
                check("qa.verdict", data.get("status") == "pass" and not data.get("critical_issues"), "verifier must pass with zero critical issues"),
                check("qa.audit_hash", data.get("audit_findings_sha256") == sha256_file(audit), "verifier must bind the current audit"),
                check("qa.md_hash", data.get("final_md_sha256") == sha256_file(workspace / "final.md"), "verifier must bind current final.md"),
            ])
            if mode == WorkflowMode.HTML:
                checks.extend([
                    check("qa.html_hash", data.get("final_html_sha256") == sha256_file(workspace / "final.html"), "verifier must bind current final.html"),
                    check("qa.browser_hash", data.get("browser_report_sha256") == sha256_file(workspace / "qa" / "browser_report.json"), "verifier must bind browser evidence"),
                ])
            dimensions = data.get("dimensions", {})
            required = {"accuracy", "completeness", "coherence", "visual_quality", "rendering", "citation_hygiene"}
            scores = [dimensions.get(name, {}).get("score", 0) for name in required]
            checks.append(check("qa.dimensions", required <= set(dimensions) and all(isinstance(score, (int, float)) and score >= 85 for score in scores), "all verifier dimensions must score at least 85"))
        except Exception as exc:
            checks.append(check("qa.report_contract", False, f"invalid QA report contract: {exc}"))
    return build_report(StageName.QA, checks, publication_metrics(workspace))
