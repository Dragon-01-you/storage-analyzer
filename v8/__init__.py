"""Storage Analyzer v8 - Industrial-grade, AI-Brain driven.

Eight core modules:
  1. AI Brain        (intent + cognitive labeling)
  2. Engine Core     (funnel scan + plugin registry)
  3. Evolution       (foolproof proposals + whitelist health)
  4. Safeguard       (hard-block + tiered deletion)
  5. Scan Cache      (incremental SQLite cache)
  6. Audit           (JSON Lines tamper-evident log)
  7. Duplicates      (3-stage duplicate detector)
  8. History         (trend forecasting)

Data contracts are Pydantic v2 in types.py.
"""
from .types import (
    ScanConfig,
    DirectorySummary,
    CleanEntry,
    WhitelistRule,
    CognitiveLabel,
    LabelSource,
    RiskLevel,
    SafetyTier,
    DeletionMode,
    _human_bytes,
)
from .ai_brain import AIBrain, IntentParser, CognitiveAdapter
from .engine_core import FunnelScanner, PluginRegistry
from .evolution import EvolutionEngine, WhitelistStore, FoolproofProposer
from .safeguard import SafeDeleter, ProtectedPaths, ProtectedPathError
from .platform_paths import PlatformPaths
from .scan_cache import ScanCache
from .audit import AuditLogger
from .duplicates import DuplicateDetector, DuplicateGroup, DuplicateFile
from .history import HistoryStore, Forecaster, DiskSnapshot, Forecast, take_all_snapshots
from .orchestrator import Orchestrator, OrchestratorResult

__all__ = [
    # Core types
    "ScanConfig", "DirectorySummary", "CleanEntry", "WhitelistRule",
    "CognitiveLabel", "LabelSource", "RiskLevel", "SafetyTier", "DeletionMode",
    "_human_bytes",
    # Modules
    "AIBrain", "IntentParser", "CognitiveAdapter",
    "FunnelScanner", "PluginRegistry",
    "EvolutionEngine", "WhitelistStore", "FoolproofProposer",
    "SafeDeleter", "ProtectedPaths", "ProtectedPathError",
    "PlatformPaths",
    "ScanCache",
    "AuditLogger",
    "DuplicateDetector", "DuplicateGroup", "DuplicateFile",
    "HistoryStore", "Forecaster", "DiskSnapshot", "Forecast",
    "Orchestrator", "OrchestratorResult",
]

__version__ = "8.1.0"

