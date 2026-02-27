import os
import json
from pathlib import Path

def aggregate():
    base_dir = Path("workspace/v16_editorial_stress_rerun")
    log_dir = base_dir / "editorial_qa_logs"
    output_path = Path("log/audit_full_trail.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Files to collect in order
    files_to_collect = [
        ("INITIAL MERGED CONTENT (PRE-IT1)", log_dir / "content_pre_it1.md"),
    ]
    
    for i in range(1, 6):
        files_to_collect.append((f"ITERATION {i} - CRITIQUE", log_dir / f"critique_it{i}.json"))
        files_to_collect.append((f"ITERATION {i} - ADVICE", log_dir / f"advice_it{i}.json"))
        files_to_collect.append((f"ITERATION {i} - FIX RESULT", log_dir / f"fix_result_it{i}.json"))
        if i < 5:
            files_to_collect.append((f"CONTENT PRE-IT{i+1}", log_dir / f"content_pre_it{i+1}.md"))
            
    files_to_collect.append(("FINAL MERGED CONTENT", base_dir / "final_full.md"))
    
    with open(output_path, "w", encoding="utf-8") as out:
        for title, path in files_to_collect:
            out.write("\n" + "="*80 + "\n")
            out.write(f"TITLE: {title}\n")
            out.write(f"PATH: {path}\n")
            out.write("="*80 + "\n\n")
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    out.write(content)
                except Exception as e:
                    out.write(f"ERROR READING FILE: {e}")
            else:
                out.write("FILE NOT FOUND.")
            out.write("\n\n")

    print(f"✅ Aggregated audit trail created at: {output_path}")

if __name__ == "__main__":
    aggregate()
