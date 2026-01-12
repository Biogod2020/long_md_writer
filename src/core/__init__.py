# Core module - SOTA 2.0

from .types import (
    AgentState,
    Manifest,
    SectionInfo,
    AssetEntry,
    AssetSource,
    AssetQualityLevel,
    CropMetadata,
    UniversalAssetRegistry
)

from .validators import (
    MarkdownValidator,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity
)

from .persistence import (
    ProjectProfile,
    ProfileStatus,
    ProfileManager,
    PromptSnapshot,
    InputBlueprint,
    UARCheckpoint,
    AssetDecision,
    AssetService,
    reload_profile_to_state,
    check_input_changes
)

from .gemini_client import GeminiClient

__all__ = [
    # Types
    "AgentState",
    "Manifest",
    "SectionInfo",
    "AssetEntry",
    "AssetSource",
    "AssetQualityLevel",
    "CropMetadata",
    "UniversalAssetRegistry",
    # Validators
    "MarkdownValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    # Persistence (Phase C)
    "ProjectProfile",
    "ProfileStatus",
    "ProfileManager",
    "PromptSnapshot",
    "InputBlueprint",
    "UARCheckpoint",
    "AssetDecision",
    "AssetService",
    "reload_profile_to_state",
    "check_input_changes",
    # Client
    "GeminiClient",
]
