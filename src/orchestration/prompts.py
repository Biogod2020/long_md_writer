"""Stage prompts and filesystem contracts."""

from __future__ import annotations

from .models import PlanSection, QualityReport, StageName, WorkflowMode


WORKSPACE_RULES = """
You are operating inside a bounded publication workspace.

Non-negotiable rules:
1. Read AGENTS.md, inputs/manifest.json, and all relevant upstream artifacts first.
2. Never modify inputs/, .magnum/, AGENTS.md, or files outside the working directory.
3. Never create symbolic links, sockets, device files, or executable binaries.
4. Do not use remote hotlinks, remote scripts, remote stylesheets, or data/javascript/file URLs.
5. Do not claim validation passed unless you actually ran the stated command and inspected its output.
6. Preserve source uncertainty. Do not invent citations, evidence, attribution, or experimental results.
7. Write only the files allowed by the task. Keep all other workspace files unchanged.
8. Return the required structured CodexTaskResult after completing the task.
""".strip()


def _retry_block(report: QualityReport | None) -> str:
    if report is None:
        return ""
    return (
        "\nThe previous deterministic gate failed. Resolve every item below:\n"
        + report.feedback_text()
    )


def plan_prompt(mode: WorkflowMode, report: QualityReport | None = None) -> str:
    return f"""
{WORKSPACE_RULES}

Stage: PLAN
Read inputs/request.md, inputs/references/, and inputs/assets/. Produce:
- project_brief.md: a precise execution brief grounded in the supplied material;
- plan.json: schema_version 2 with project_title, audience, language, objectives,
  sections, and quality_contract.

Each section requires: id, title, objective, estimated_words, required_evidence,
and visual_opportunities. Section IDs must be filesystem-safe and unique. Build a
coherent long-form publication plan rather than fragmenting the document into many
thin sections. The target output mode is {mode.value}.

Run:
python -m src.orchestration.validate_cli --workspace . --stage plan --mode {mode.value} --json
{_retry_block(report)}
""".strip()


def draft_prompt(
    section: PlanSection,
    mode: WorkflowMode,
    report: QualityReport | None = None,
) -> str:
    return f"""
{WORKSPACE_RULES}

Stage: DRAFT ONE SECTION
Write only drafts/{section.id}.md.

Section title: {section.title}
Objective: {section.objective}
Target words: {section.estimated_words}
Required evidence: {section.required_evidence}
Visual opportunities: {section.visual_opportunities}
Final output mode: {mode.value}

Use the project brief, complete plan, and supplied references. Write a substantive,
source-grounded section with explicit uncertainty where sources are insufficient.
Use stable terminology and a single H2 heading for this section. Do not generate
asset files here. When a visual is genuinely useful, insert a machine-readable block:

:::visual {{"id":"{section.id}-figure-name","action":"GENERATE_SVG|GENERATE_MERMAID|USE_EXISTING|SEARCH_WEB","reason":"...","description":"..."}}
:::

Do not use TODOs, filler, fake citations, or unresolved bracket placeholders.
Run the draft validator for this section before returning.
{_retry_block(report)}
""".strip()


def assets_prompt(mode: WorkflowMode, report: QualityReport | None = None) -> str:
    return f"""
{WORKSPACE_RULES}

Stage: ASSET FULFILLMENT
Inspect every drafts/*.md visual directive and inputs/assets/. Resolve all directives.
Create a complete resolved copy of every draft under md/; do not modify drafts/.
Prefer reuse of suitable user assets, then deterministic SVG or Mermaid source.
Use web sourcing only when the task explicitly has network access and a real-world
image is essential. Never hotlink remote content.

Write assets/asset-manifest.json with schema_version 2 and an assets array. Every
entry must include id, source, path, caption, alt_text, provenance, licence, used_in,
and sha256. Local visual files must live under assets/. Update md/*.md so directives
are replaced by local Markdown or HTML references. Preserve the prose around them.

Run:
python -m src.orchestration.validate_cli --workspace . --stage assets --mode {mode.value} --json
{_retry_block(report)}
""".strip()


def publish_prompt(mode: WorkflowMode, report: QualityReport | None = None) -> str:
    html_requirements = """
Also create final.html as a fully self-contained, responsive publication. Use only
local assets and inline CSS/JS. Do not include forms, iframes, object/embed elements,
meta refresh, inline event handlers, remote resources, or active URL schemes. Include
accessible semantic structure, print styles, readable tables/code/math, and mobile
layout. final.html must faithfully represent final.md.
""" if mode == WorkflowMode.HTML else ""
    return f"""
{WORKSPACE_RULES}

Stage: PUBLISH
Merge md/*.md in exact plan order into final.md. Remove accidental repetition,
normalize cross-section terminology, preserve all source caveats, and ensure every
plan objective is addressed. Do not collapse substantive sections merely to shorten
the document. All assets must remain local and valid.
{html_requirements}

Run:
python -m src.orchestration.validate_cli --workspace . --stage publish --mode {mode.value} --json
{_retry_block(report)}
""".strip()


def qa_audit_prompt(mode: WorkflowMode, report: QualityReport | None = None) -> str:
    return f"""
{WORKSPACE_RULES}

Stage: INDEPENDENT ADVERSARIAL AUDIT
Do not modify manuscript or asset files. Audit inputs/, project_brief.md, plan.json,
md/, assets/, final.md, and final.html when present. Write only
qa/audit-findings.json with schema_version 2, review_role "independent_auditor",
artifact hashes, dimension scores, critical_issues, repair_instructions, and
unsupported_claims.

Audit factual/source fidelity, plan coverage, logical continuity, terminology,
quantitative consistency, visual usefulness, accessibility, provenance, citation
hygiene, responsive rendering risks, and security. Be specific and evidence-based.
Do not manufacture findings merely to appear critical.

Target mode: {mode.value}
{_retry_block(report)}
""".strip()


def qa_repair_prompt(mode: WorkflowMode, report: QualityReport | None = None) -> str:
    return f"""
{WORKSPACE_RULES}

Stage: QA REPAIR
Read qa/audit-findings.json and the latest deterministic quality report. Repair the
smallest necessary set of md/*.md, assets/*, final.md, and final.html when applicable.
Do not modify the audit report or browser evidence. Re-run publish validation and
leave the workspace in a coherent state.

Target mode: {mode.value}
{_retry_block(report)}
""".strip()


def qa_verify_prompt(mode: WorkflowMode, report: QualityReport | None = None) -> str:
    browser_note = (
        "Read qa/browser_report.json and the attached canonical desktop/mobile screenshots."
        if mode == WorkflowMode.HTML
        else "No browser evidence is required in Markdown mode."
    )
    return f"""
{WORKSPACE_RULES}

Stage: FRESH INDEPENDENT VERIFICATION
Do not modify manuscript, HTML, assets, audit findings, or browser evidence. Review
the current artifacts from scratch. {browser_note}

Write only qa_report.json with:
- schema_version: 2
- review_role: "independent_verifier"
- status: pass|fail
- summary
- audit_findings_sha256
- final_md_sha256
- final_html_sha256 (empty in Markdown mode)
- browser_report_sha256 (empty in Markdown mode)
- dimensions: accuracy, completeness, coherence, visual_quality, rendering,
  citation_hygiene, each with score and findings
- critical_issues
- repairs_verified
- commands_run

Use status=pass only when no critical issue remains and deterministic validation
passes. Never fabricate browser evidence or source support.

Target mode: {mode.value}
{_retry_block(report)}
""".strip()


def allowed_paths_for_stage(stage: StageName, mode: WorkflowMode) -> list[str]:
    if stage == StageName.PLAN:
        return ["project_brief.md", "plan.json"]
    if stage == StageName.DRAFT:
        return ["drafts/**"]
    if stage == StageName.ASSETS:
        return ["md/**", "assets/**"]
    if stage == StageName.PUBLISH:
        paths = ["final.md"]
        if mode == WorkflowMode.HTML:
            paths.append("final.html")
        return paths
    if stage == StageName.QA:
        paths = ["md/**", "assets/**", "final.md", "qa/audit-findings.json", "qa_report.json"]
        if mode == WorkflowMode.HTML:
            paths.append("final.html")
        return paths
    raise ValueError(stage)


def required_outputs_for_stage(stage: StageName, mode: WorkflowMode) -> list[str]:
    if stage == StageName.PLAN:
        return ["project_brief.md", "plan.json"]
    if stage == StageName.DRAFT:
        return []
    if stage == StageName.ASSETS:
        return ["assets/asset-manifest.json"]
    if stage == StageName.PUBLISH:
        outputs = ["final.md"]
        if mode == WorkflowMode.HTML:
            outputs.append("final.html")
        return outputs
    if stage == StageName.QA:
        return ["qa/audit-findings.json", "qa_report.json"]
    raise ValueError(stage)
