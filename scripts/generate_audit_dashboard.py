import json
import os
import base64
from pathlib import Path

def generate(job_id):
    ws = Path(f"workspaces/workspace/{job_id}")
    if not ws.exists(): return "Workspace not found."
    
    def b64_encode(text):
        return base64.b64encode(text.encode('utf-8')).decode('utf-8')

    manifest = json.loads((ws / "manifest.json").read_text()) if (ws / "manifest.json").exists() else {}
    sections_b64 = {f.name: b64_encode(f.read_text()) for f in ws.glob("md/*.md")}
    
    bp_map = {
        "BP1": "BP-2", "BP2": "review_brief", "BP3": "review_outline",
        "BP4": "techspec", "BP5": "BP-6", "BP6": "markdown_review"
    }

    snapshot_data = []
    snapshot_dirs = sorted(list(ws.glob("snapshots/*")), key=os.path.getmtime)
    for sd in snapshot_dirs:
        state_file = sd / "state.json"
        if state_file.exists():
            snapshot_data.append({"id": sd.name, "state_b64": b64_encode(state_file.read_text())})

    html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>🧬 SOTA 7.0 Aether Ultra</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg: #020408; --panel: rgba(10, 14, 20, 0.95); --border: rgba(34, 211, 238, 0.15);
            --accent: #00f2ff; --purple: #a78bfa; --gold: #fbbf24; --text: #f1f5f9; --meta: #475569;
        }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
        
        body::before {
            content: ''; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: 
                radial-gradient(circle at 50% 50%, rgba(0, 242, 255, 0.05), transparent 70%),
                linear-gradient(var(--border) 1px, transparent 1px), 
                linear-gradient(90deg, var(--border) 1px, transparent 1px);
            background-size: 100% 100%, 50px 50px, 50px 50px;
            pointer-events: none; z-index: -1;
        }

        #topo-header { 
            height: 300px; background: rgba(0,0,0,0.85); border-bottom: 1px solid var(--border);
            backdrop-filter: blur(20px); display: flex; align-items: center; justify-content: center;
            padding: 0 60px; position: relative; box-shadow: 0 10px 40px rgba(0,0,0,0.6); overflow: hidden;
        }
        
        /* 修复 V6.1 的裁剪问题：使用 Flexbox 居中 + 动态缩放 */
        .mermaid { transform: scale(1.1); transform-origin: center; width: 100%; }

        #core-layout { flex: 1; display: flex; overflow: hidden; }
        
        #sidebar { 
            width: 360px; background: var(--panel); border-right: 1px solid var(--border);
            display: flex; flex-direction: column;
        }
        .brand-zone { padding: 40px 30px; border-bottom: 1px solid var(--border); }
        .brand-zone h1 { 
            margin: 0; font-family: 'Orbitron', sans-serif; font-size: 18px; letter-spacing: 4px; 
            color: var(--accent); text-shadow: 0 0 20px rgba(0, 242, 255, 0.5);
            animation: pulse 4s infinite alternate;
        }
        @keyframes pulse { from { opacity: 0.7; } to { opacity: 1; text-shadow: 0 0 30px var(--accent); } }

        #viewport { flex: 1; overflow-y: auto; padding: 80px; position: relative; scroll-behavior: smooth; }
        
        .artifact-btn { 
            padding: 20px 30px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.03);
            font-size: 12px; color: var(--meta); transition: 0.4s; text-transform: uppercase; letter-spacing: 1px;
        }
        .artifact-btn:hover { background: rgba(0, 242, 255, 0.05); color: var(--accent); padding-left: 40px; }
        .artifact-btn.active { border-left: 4px solid var(--accent); background: rgba(0, 242, 255, 0.08); color: var(--accent); }

        .glass-card { 
            background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border); 
            backdrop-filter: blur(15px); border-radius: 20px; padding: 50px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
            animation: slideUp 0.6s cubic-bezier(0.23, 1, 0.32, 1);
        }
        @keyframes slideUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }

        .intent-card { 
            background: rgba(251, 191, 36, 0.02); border: 1px solid var(--gold); 
            border-left: 8px solid var(--gold); padding: 30px; border-radius: 12px; margin: 50px 0;
        }
        .action-badge { background: var(--gold); color: #000; font-weight: 900; font-size: 10px; padding: 4px 12px; border-radius: 100px; }

        .markdown-body { font-size: 18px; line-height: 1.9; color: #cbd5e1; }
        .markdown-body h1 { font-family: 'Orbitron', sans-serif; color: var(--accent); font-weight: 300; font-size: 2.5em; margin-bottom: 40px; }
        
        pre { background: #000; padding: 25px; border-radius: 12px; border: 1px solid var(--border); color: #818cf8; overflow-x: auto; font-family: 'JetBrains Mono'; }

        /* 强化节点交互 */
        .node rect { stroke-width: 2px !important; transition: 0.3s !important; }
        .node:hover rect { filter: drop-shadow(0 0 15px var(--accent)) !important; stroke-width: 3px !important; }
    </style>
</head>
<body>
    <div id="topo-header">
        <pre class="mermaid">
graph LR
    BP1(BP-1 INDEXER)
    BP2(BP-2 REFINER)
    BP3(BP-3 ARCHITECT)
    BP4(BP-4 TECHSPEC)
    BP5(BP-5 WRITER)
    BP6(BP-6 MD QA)
    BP8(BP-8 ASSET GEN)
    BP10(BP-10 FINAL)

    BP1 --> BP2 --> BP3 --> BP4 --> BP5 --> BP6 --> BP8 --> BP10
    
    style BP1 fill:#0a0e14,stroke:#00f2ff,color:#fff
    style BP2 fill:#0a0e14,stroke:#00f2ff,color:#fff
    style BP3 fill:#0a0e14,stroke:#00f2ff,color:#fff
    style BP4 fill:#0a0e14,stroke:#00f2ff,color:#fff
    style BP5 fill:#0a0e14,stroke:#00f2ff,color:#fff
    style BP6 fill:#0a0e14,stroke:#00f2ff,color:#fff
        </pre>
    </div>

    <div id="core-layout">
        <div id="sidebar">
            <div class="brand-zone"><h1>AETHER ULTRA 7.0</h1></div>
            <div id="stream-status" style="padding:20px 30px; font-size:9px; color:var(--meta); text-transform:uppercase; letter-spacing:3px">Stream: Idle</div>
            <div id="artifact-list"></div>
        </div>
        <div id="viewport">
            <div style="height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; opacity:0.3">
                <div style="font-size:80px; margin-bottom:30px">🛡️</div>
                <h2 style="font-family:'Orbitron'; letter-spacing:10px">SYSTEM ARMED</h2>
                <p style="font-family:'JetBrains Mono'; font-size:11px">READY TO DECODE SOTA DATASTREAM</p>
            </div>
        </div>
    </div>

    <script>
        function decode(b64) { return decodeURIComponent(escape(atob(b64))); }
        const store = { manifest: DATA_MANIFEST, sections: DATA_SECTIONS, snapshots: DATA_SNAPSHOTS, bpMap: DATA_BP_MAP };

        document.addEventListener('click', function(e) {
            const node = e.target.closest('.node');
            if (node) {
                const label = node.querySelector('.nodeLabel')?.innerText || "";
                const bpId = label.split(' ')[0].replace('-', '');
                initializeDataStream(bpId, node);
            }
        });

        function initializeDataStream(bpId, nodeEl) {
            const keyword = store.bpMap[bpId];
            const list = document.getElementById('artifact-list');
            document.getElementById('stream-status').innerText = "Streaming: " + bpId;
            list.innerHTML = "";
            
            document.querySelectorAll('.node').forEach(n => n.style.opacity = "0.3");
            nodeEl.style.opacity = "1";

            store.snapshots.forEach(snap => {
                if(snap.id.includes(keyword)) {
                    const div = document.createElement('div');
                    div.className = 'artifact-btn';
                    div.innerHTML = `<b>CORE SNAPSHOT</b><br>${snap.id}`;
                    div.onclick = () => renderState(snap.state_b64);
                    list.appendChild(div);
                }
            });

            if(bpId === 'BP3' || bpId === 'BP4') {
                const div = document.createElement('div');
                div.className = 'artifact-btn'; div.innerHTML = "<b>BLUEPRINT DATA</b><br>manifest.json";
                div.onclick = renderBlueprint; list.appendChild(div);
            }

            if(bpId === 'BP5') {
                Object.keys(store.sections).forEach(name => {
                    const div = document.createElement('div');
                    div.className = 'artifact-btn';
                    div.innerHTML = "<b>SEMANTIC OBJECT</b><br>" + name;
                    div.onclick = () => renderSection(name);
                    list.appendChild(div);
                });
            }
        }

        function renderState(b64) {
            const state = JSON.parse(decode(b64));
            document.getElementById('viewport').innerHTML = `<div class='glass-card'><h1>Logical Core State</h1><pre>${JSON.stringify(state, null, 2)}</pre></div>`;
        }

        function renderBlueprint() {
            let html = "<div class='glass-card'><h1>Strategic Blueprint</h1>";
            store.manifest.sections.forEach(s => {
                html += `<div style='border-bottom:1px solid rgba(255,255,255,0.05); padding:30px 0'>
                    <div style='display:flex; justify-content:space-between; align-items:center'>
                        <h3 style='margin:0; font-family:Orbitron; letter-spacing:1px'>${s.title}</h3>
                        <code style='color:var(--accent)'>${s.id}</code>
                    </div>
                    <p style='color:var(--meta); font-size:15px; margin:20px 0'>${s.summary}</p>
                    <span class='action-badge' style='background:rgba(0,242,255,0.1); color:var(--accent); border:1px solid var(--accent)'>${s.metadata.namespace}</span>
                </div>`;
            });
            html += "</div>";
            document.getElementById('viewport').innerHTML = html;
        }

        function renderSection(name) {
            const raw = decode(store.sections[name]);
            let processed = raw.replace(/:::visual\s*(\\{[\\s\\S]*?\\})([\\s\\S]*?):/g, (m, j, c) => {
                try {
                    let clean = j.trim(); if(!clean.endsWith("}")) clean += "}";
                    const cfg = JSON.parse(clean);
                    return `<div class='intent-card'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:20px'>
                            <strong style='color:var(--gold); letter-spacing:2px'>VISUAL_INTENT</strong>
                            <span class='action-badge'>${cfg.action}</span>
                        </div>
                        <div style='font-size:16px; color:#fff; margin-bottom:15px'>${cfg.description}</div>
                        <div style='font-size:13px; color:var(--meta); border-top:1px solid rgba(251,191,36,0.1); padding-top:15px'>SOURCE_CONTEXT: ${c.trim()}</div>
                    </div>`;
                } catch(e) { return m; }
            });
            document.getElementById('viewport').innerHTML = `<div class='glass-card'><div class='markdown-body'>${marked.parse(processed)}</div></div>`;
        }

        mermaid.initialize({ startOnLoad: true, theme: 'dark', securityLevel: 'loose', flowchart: { useMaxWidth: false } });
    </script>
</body>
</html>
"""
    final_html = html_template.replace("DATA_MANIFEST", json.dumps(manifest))
    final_html = final_html.replace("DATA_SECTIONS", json.dumps(sections_b64))
    final_html = final_html.replace("DATA_SNAPSHOTS", json.dumps(snapshot_data))
    final_html = final_html.replace("DATA_BP_MAP", json.dumps(bp_map))
    
    output_path = ws / "aether_ultra_v7.html"
    output_path.write_text(final_html)
    return str(output_path.absolute())

if __name__ == "__main__":
    import sys
    print(generate(sys.argv[1] if len(sys.argv) > 1 else "test_sota2_fresh"))
