import os

# ============================================================================
# API & Provider Configuration
# ============================================================================

# Default proxy URL (geminicli2api-async defaults to 8888)
DEFAULT_BASE_URL = os.getenv("API_URL", "http://localhost:8888")

# Default authentication password/token
DEFAULT_AUTH_PASSWORD = os.getenv("GEMINI_AUTH_PASSWORD", "123456")

# SOTA 2.1: Default providers for polling (Adjusted for 1:2 ratio)
DEFAULT_PROVIDERS = ["gemini-cli-oauth", "gemini-antigravity", "gemini-antigravity"]


# ============================================================================
# Sourcing & Fulfillment Performance (SOTA 2.1)
# ============================================================================

# Maximum concurrent browser tabs across all sourcing tasks
DEFAULT_BROWSER_CONCURRENCY = int(os.getenv("BROWSER_CONCURRENCY", "30"))

# Number of top results to prioritize in the 'Elite Pass' audit
DEFAULT_ELITE_BATCH_SIZE = 20

# VLM Audit hierarchy settings
DEFAULT_HIERARCHY_BATCH_SIZE = 10
DEFAULT_HIERARCHY_WINNERS_PER_BATCH = 2

# Global timeout for download tasks (seconds)
DEFAULT_DOWNLOAD_TIMEOUT = 15.0


# ============================================================================
# Model Selection (Centralized)
# ============================================================================

# The primary model used across all agents (Architect, Writer, Critic, etc.)
# Standardized model name (without -maxthinking suffixes)
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3-flash-preview")

# Default thinking level for Gemini 3 series models
# Options: "HIGH", "MEDIUM", "LOW", "MINIMAL"
DEFAULT_THINKING_LEVEL = "HIGH"

# SOTA 2.1: Node-specific routing preferences
# Heavy nodes: Prefer gemini-cli-oauth + HIGH thinking
NODE_PREF_HEAVY = {
    "model_provider": ["gemini-cli-oauth", "gemini-antigravity"],
    "thinking_level": "HIGH"
}

# Pro nodes: Highest intelligence for top-level architecture (Architect)
NODE_PREF_PRO = {
    "model": "gemini-3.1-pro-preview",
    "model_provider": ["gemini-cli-oauth", "gemini-antigravity"],
    "thinking_level": "HIGH"
}

# Light nodes: Prefer gemini-antigravity + MEDIUM thinking for speed
NODE_PREF_LIGHT = {
    "model_provider": ["gemini-antigravity", "gemini-cli-oauth"],
    "thinking_level": "MEDIUM"
}


# ============================================================================
# Workspace & System Settings
# ============================================================================

WORKSPACE_BASE = os.getenv("WORKSPACE_BASE", "./workspace")
DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"
# SOTA: Global toggle for browser visibility (primarily for ImageSourcing)
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "true").lower() == "true"
