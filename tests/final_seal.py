from src.core.merger import split_merged_document
from pathlib import Path

def seal_project(job_id: str):
    ws = Path(f"workspace/{job_id}")
    merged = ws / "final_full.md"
    audited_dir = ws / "audited_md"
    
    print(f"📦 Sealing project {job_id}...")
    if split_merged_document(str(merged), str(audited_dir)):
        print(f"✨ Success! Final SOTA artifacts are ready at: {audited_dir.absolute()}")
        print(f"🚀 Combined document: {merged.absolute()}")
        print(f"🎨 Localized resources: {(ws / 'resource').absolute()}")
    else:
        print("❌ Sealing failed.")

if __name__ == "__main__":
    seal_project("sota2_20260223_220554")
