"""Minimal Streamlit front-end; the workflow remains entirely in src/orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.orchestration.models import WorkflowMode, WorkflowRequest
from src.orchestration.openai_workflow import run_publication_workflow


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise SystemExit("Install streamlit to use the GUI: pip install streamlit") from exc

    st.set_page_config(page_title="Magnum Opus", layout="wide")
    st.title("Magnum Opus")
    intent = st.text_area("Publication request", height=240)
    mode = st.selectbox("Output", ["html", "markdown"])
    output = st.text_input("Workspace base", "./workspace")
    job_id = st.text_input("Job ID (optional)")
    auto = st.checkbox("Auto-approve gates", value=False)
    network = st.checkbox("Allow network for asset sourcing", value=False)
    if st.button("Run", type="primary", disabled=not intent.strip()):
        request = WorkflowRequest(
            user_intent=intent,
            output_base=Path(output),
            job_id=job_id or None,
            mode=WorkflowMode(mode),
            auto_approve=auto,
            allow_network=network,
        )
        with st.spinner("Running bounded agent workflow..."):
            result = asyncio.run(run_publication_workflow(request))
        st.json(result.model_dump(mode="json"))


if __name__ == "__main__":
    main()
