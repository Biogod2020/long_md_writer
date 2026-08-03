from pathlib import Path

import pytest

from src.orchestration.browser_probe import render_browser_evidence


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_real_browser_probe(tmp_path: Path) -> None:
    text = "Reliable local publication evidence. " * 80
    (tmp_path / "final.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Probe</title>"
        "<style>html{overflow-x:hidden}body{margin:0}main{max-width:70ch;margin:auto;padding:2rem;box-sizing:border-box}</style>"
        f"</head><body><main><h1>Probe</h1><p>{text}</p></main></body></html>",
        encoding="utf-8",
    )
    report = await render_browser_evidence(tmp_path)
    assert report["status"] == "pass", report
    assert (tmp_path / "qa" / "render-desktop.png").is_file()
    assert (tmp_path / "qa" / "render-mobile.png").is_file()
