
import json
import datetime
from pathlib import Path
from typing import Optional, Union

def save_debug_log(
    workspace_path: str, 
    agent_name: str, 
    step_name: str, 
    prompt: Union[str, list], 
    response: Optional[str] = None,
    system_instruction: Optional[str] = None,
    error: Optional[str] = None
):
    """Saves raw prompt and response to a debug file for troubleshooting."""
    debug_dir = Path(workspace_path) / "debug_logs"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{timestamp}_{agent_name}_{step_name}.json"
    log_path = debug_dir / filename
    
    log_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "agent": agent_name,
        "step": step_name,
        "system_instruction": system_instruction,
        "prompt": prompt,
        "response": response,
        "error": error
    }
    
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    return log_path
