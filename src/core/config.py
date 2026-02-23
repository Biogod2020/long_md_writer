import os

# ============================================================================
# API & Provider Configuration
# ============================================================================

# Default proxy URL (AIClient-2-API defaults to 3000)
DEFAULT_BASE_URL = os.getenv("API_URL", "http://localhost:3000")

# Default authentication password/token
DEFAULT_AUTH_PASSWORD = os.getenv("GEMINI_AUTH_PASSWORD", "123456")


# ============================================================================
# Model Selection (Centralized)
# ============================================================================

# The primary model used across all agents (Architect, Writer, Critic, etc.)
# Standardized model name (without -maxthinking suffixes)
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3-flash-preview")

# Default thinking level for Gemini 3 series models
# Options: "HIGH", "MEDIUM", "LOW", "MINIMAL"
DEFAULT_THINKING_LEVEL = "HIGH"


# ============================================================================
# Workspace & System Settings
# ============================================================================

WORKSPACE_BASE = os.getenv("WORKSPACE_BASE", "./workspace")
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"
