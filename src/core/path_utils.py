import os
from pathlib import Path
from typing import Optional

def get_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Find the project root directory by searching upwards for anchor files.
    Anchors: .git, manifest.json
    """
    if start_path is None:
        start_path = Path(os.getcwd())
    
    current_path = start_path.resolve()
    
    # Root level of the system
    root_node = Path(current_path.root)
    
    while current_path != root_node:
        # Check for anchors
        if (current_path / ".git").exists():
            return current_path
        if (current_path / "manifest.json").exists():
            return current_path
        
        # Move up
        parent_path = current_path.parent
        if parent_path == current_path:
            break
        current_path = parent_path
        
    # Default to current working directory if no root found
    return Path(os.getcwd()).resolve()

WORKSPACE_ROOT = Path("workspaces")

def get_workspace_dir(name: str) -> Path:
    """
    Get the path to a workspace directory, ensuring it is under the WORKSPACE_ROOT.
    
    Args:
        name: The name of the workspace (e.g., 'workspace', 'workspace_debug', 'workspace_test').
        
    Returns:
        Path object pointing to the standardized workspace directory.
    """
    # Special case for legacy 'workspace' which should be 'workspaces/workspace'
    if name == "workspace":
        return WORKSPACE_ROOT / "workspace"
    
    # If the name already contains the root, don't double up
    if name.startswith("workspaces/"):
        return Path(name)
        
    return WORKSPACE_ROOT / name
