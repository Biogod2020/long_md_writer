import streamlit as st
import os
import json
import uuid
import base64
from pathlib import Path

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest
from src.agents.clarifier_agent import ClarifierAgent
from src.agents.outline_agent import OutlineAgent
from src.agents.techspec_agent import TechSpecAgent
from src.agents.refiner_agent import RefinerAgent
from src.orchestration.workflow_full import compile_full_workflow

# 页面配置
st.set_page_config(
    page_title="Magnum Opus HTML Agent",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .reportview-container { background: #0e1117; }
    h1 {
        background: linear-gradient(45deg, #FF4B4B, #FF9100);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3rem;
        font-weight: bold;
    }
    .step-active { color: #FF4B4B; font-weight: bold; }
    .step-done { color: #00CC00; }
</style>
""", unsafe_allow_html=True)

# 侧边栏配置
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/artificial-intelligence.png", width=64)
    st.title("Configuration")
    
    api_base = st.text_input("API Base URL", value="http://localhost:7860")
    auth_token = st.text_input("Auth Token", type="password", value="123456")
    
    st.divider()
    
    workspace_root = st.text_input("Workspace Root", value="./workspace")
    job_id_input = st.text_input("Job ID (Optional)", placeholder="Auto-generated if empty")
    
    st.divider()
    if st.button("🗑️ Reset All State"):
        st.session_state.clear()
        st.rerun()

# 初始化 Session State
if "manifest" not in st.session_state:
    st.session_state.manifest = None
if "agent_state" not in st.session_state:
    st.session_state.agent_state = None
if "current_step" not in st.session_state:
    st.session_state.current_step = 1
if "clarifying_questions" not in st.session_state:
    st.session_state.clarifying_questions = None
if "clarification_answers" not in st.session_state:
    st.session_state.clarification_answers = {}
if "workflow_app" not in st.session_state:
    client = init_client()
    st.session_state.workflow_app = compile_full_workflow(client)
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())[:8]
if "last_node" not in st.session_state:
    st.session_state.last_node = None

# 辅助函数
def init_client():
    return GeminiClient(api_base_url=api_base, auth_token=auth_token)

def get_job_id():
    return job_id_input.strip() or str(uuid.uuid4())[:8]

# 主标题
st.title("🧬 Magnum Opus HTML Agent")
st.caption("Human-in-the-Loop Content Generation System")

# 进度条
steps = ["1. Project Scope", "2. Architecture Design", "3. Production"]
curr = st.session_state.current_step
cols = st.columns(3)
for i, col in enumerate(cols):
    step_num = i + 1
    with col:
        if step_num == curr:
            st.info(f"📍 {steps[i]}")
        elif step_num < curr:
            st.success(f"✅ {steps[i]}")
        else:
            st.text(f"⬜ {steps[i]}")

st.divider()

# ==========================================
# STEP 1: Project Scope (Clarification & Refinement)
# ==========================================
if st.session_state.current_step == 1:
    
    # 1.0: 初始输入
    if st.session_state.agent_state is None:
        st.subheader("📝 Step 1.0: Raw Materials & Instructions")
        col_input, col_ref = st.columns(2)
        with col_input:
            uploaded_files = st.file_uploader(
                "Upload Materials",
                type=['txt', 'md', 'json', 'png', 'jpg', 'jpeg', 'webp'],
                accept_multiple_files=True
            )
            additional_instructions = st.text_area("User Goal / Instructions", height=150)
        with col_ref:
            reference_docs_input = st.text_area("External Reference", height=300)

        if st.button("🚀 Start Project Analysis"):
            job_id = get_job_id()
            workspace_path = Path(workspace_root) / job_id
            
            # Create workspace
            workspace_path.mkdir(parents=True, exist_ok=True)
            (workspace_path / "md").mkdir(exist_ok=True)
            (workspace_path / "html").mkdir(exist_ok=True)
            (workspace_path / "assets").mkdir(exist_ok=True)

            # Process inputs
            combined_text = [f"# Instructions\n{additional_instructions}\n"]
            images = []
            if uploaded_files:
                for uf in uploaded_files:
                    if "image" in uf.type:
                        b64 = base64.b64encode(uf.getvalue()).decode('utf-8')
                        images.append({"inlineData": {"mimeType": uf.type, "data": b64}})
                    else:
                        combined_text.append(f"## File: {uf.name}\n{uf.getvalue().decode('utf-8')}\n")
            
            state = AgentState(
                job_id=job_id,
                workspace_path=str(workspace_path),
                raw_materials="\n".join(combined_text) + (("\n\n" + reference_docs_input) if reference_docs_input else ""),
                images=images
            )
            st.session_state.agent_state = state
            
            # Run until Clarifier finishes (stops at refiner)
            with st.spinner("🤖 Analyzing and clarifying..."):
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                for event in st.session_state.workflow_app.stream(state.model_dump(), config=config):
                    st.session_state.last_node = list(event.keys())[0]
                    # Update state from graph
                    node_state = list(event.values())[0]
                    st.session_state.agent_state = AgentState(**node_state)
                st.rerun()

    # 1.1: 澄清问题
    elif not st.session_state.agent_state.project_brief:
        st.subheader("💡 Step 1.1: Clarifying Questions")
        questions = st.session_state.agent_state.clarifier_questions
        
        answers = {}
        for q in questions:
            answers[q['id']] = st.text_input(q['question'], key=f"q_{q['id']}")
        
        if st.button("✨ Submit Answers & Generate Brief"):
            # Update state with answers
            st.session_state.agent_state.clarifier_answers = answers
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            st.session_state.workflow_app.update_state(config, st.session_state.agent_state.model_dump())
            
            with st.spinner("🤖 Generating Project Brief..."):
                # Resume: this will run refiner and stop at review_brief
                for event in st.session_state.workflow_app.stream(None, config=config):
                    st.session_state.last_node = list(event.keys())[0]
                    node_state = list(event.values())[0]
                    st.session_state.agent_state = AgentState(**node_state)
                st.rerun()

    # 1.2: 审核 Brief
    else:
        st.subheader("📝 Step 1.2: Review Project Brief")
        brief = st.text_area("Generated Project Brief", value=st.session_state.agent_state.project_brief, height=400)
        feedback = st.text_area("Feedback / Refinement (Optional)", placeholder="What should be changed?")
        
        col_refine, col_pass = st.columns(2)
        with col_refine:
            if st.button("🔄 Apply Feedback & Regenerate"):
                if not feedback:
                    st.warning("Please provide feedback.")
                else:
                    st.session_state.agent_state.user_brief_feedback = feedback
                    st.session_state.agent_state.brief_approved = False
                    config = {"configurable": {"thread_id": st.session_state.thread_id}}
                    st.session_state.workflow_app.update_state(config, st.session_state.agent_state.model_dump())
                    
                    with st.spinner("🤖 Refining Brief..."):
                        for event in st.session_state.workflow_app.stream(None, config=config):
                            st.session_state.last_node = list(event.keys())[0]
                            node_state = list(event.values())[0]
                            st.session_state.agent_state = AgentState(**node_state)
                        st.rerun()
        
        with col_pass:
            if st.button("✅ Approved - Next to Outline"):
                st.session_state.agent_state.project_brief = brief # Save any edits
                st.session_state.agent_state.brief_approved = True
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                st.session_state.workflow_app.update_state(config, st.session_state.agent_state.model_dump())
                
                with st.spinner("🤖 Designing Outline..."):
                    # Resume: stop at review_outline
                    for event in st.session_state.workflow_app.stream(None, config=config):
                        st.session_state.last_node = list(event.keys())[0]
                        node_state = list(event.values())[0]
                        st.session_state.agent_state = AgentState(**node_state)
                    st.session_state.current_step = 2
                    st.rerun()

# ==========================================
# STEP 2: Architecture Design (Outline & Tech Spec)
# ==========================================
elif st.session_state.current_step == 2:
    st.subheader("🧐 Step 2.1: Outline Review")
    
    manifest = st.session_state.agent_state.manifest
    st.markdown(f"### Title: {manifest.project_title}")
    
    # Display sections in a table
    sections_data = [{"ID": s.id, "Title": s.title, "Summary": s.summary} for s in manifest.sections]
    st.table(sections_data)
    
    feedback = st.text_area("Outline Feedback", placeholder="Change section order, add more depth, etc.")
    
    col_refine, col_pass = st.columns(2)
    with col_refine:
        if st.button("🔄 Refine Outline"):
            if not feedback:
                st.warning("Please provide feedback.")
            else:
                st.session_state.agent_state.user_outline_feedback = feedback
                st.session_state.agent_state.outline_approved = False
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                st.session_state.workflow_app.update_state(config, st.session_state.agent_state.model_dump())
                
                with st.spinner("🤖 Re-designing Outline..."):
                    for event in st.session_state.workflow_app.stream(None, config=config):
                        st.session_state.last_node = list(event.keys())[0]
                        node_state = list(event.values())[0]
                        st.session_state.agent_state = AgentState(**node_state)
                    st.rerun()

    with col_pass:
        if st.button("✅ Approved - Finalize & Start Production"):
            st.session_state.agent_state.outline_approved = True
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            st.session_state.workflow_app.update_state(config, st.session_state.agent_state.model_dump())
            
            with st.spinner("🤖 Finalizing Tech Spec & Starting Production..."):
                # Resume: will run techspec and then enter the production loop
                # Since production is automated, we switch to step 3 and stream there
                st.session_state.current_step = 3
                st.rerun()

# ==========================================
# STEP 3: Production
# ==========================================
elif st.session_state.current_step == 3:
    st.subheader("⚙️ Step 3: Production Pipeline")
    
    state = st.session_state.agent_state
    st.info(f"Producing: {state.manifest.project_title}")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.container()
    
    if st.button("▶️ Launch Production"):
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        try:
            with st.spinner("AI Hive-Mind is building your document..."):
                # Stream remaining nodes
                for event in st.session_state.workflow_app.stream(None, config=config):
                    node_name = list(event.keys())[0]
                    node_state = list(event.values())[0]
                    s = AgentState(**node_state)
                    st.session_state.agent_state = s
                    
                    status_text.text(f"Currently: {node_name}")
                    
                    with log_container:
                        if node_name == "writer":
                            done = len(s.completed_md_sections)
                            total = len(s.manifest.sections)
                            st.text(f"✍️ Wrote section {done}/{total}: {s.manifest.sections[done-1].title}")
                            progress_bar.progress(done / total * 0.4)
                        elif node_name == "transformer":
                            done = len(s.completed_html_sections)
                            total = len(s.manifest.sections)
                            st.text(f"🔄 Transformed {done}/{total}")
                            progress_bar.progress(0.5 + (done / total * 0.4))
                        elif node_name == "visual_qa":
                            st.success("🔍 Visual QA check performed")
                            if s.vqa_needs_reassembly:
                                st.warning("🛠️ Repairs applied, re-assembling...")
                            progress_bar.progress(0.95)
                        elif node_name == "assembler":
                             st.success("✅ Assembly complete")
                    
                st.balloons()
                st.success("Mission Accomplished!")
                
                # Show results
                if st.session_state.agent_state.final_html_path:
                    with open(st.session_state.agent_state.final_html_path, "r") as f:
                        html = f.read()
                    st.download_button("📥 Download Final HTML", html, "final.html", "text/html")
                    st.components.v1.html(html, height=1000, scrolling=True)
                    
        except Exception as e:
            st.error(f"Production Error: {e}")
            st.exception(e)

if st.button("🗑️ Start New Project"):
    st.session_state.clear()
    st.rerun()
