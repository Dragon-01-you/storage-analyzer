"""v8 test suite.

Run:  python -m pytest tests/test_v8.py -v
"""
from __future__ import annotations
import os
import sys
import tempfile
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Make pydantic available
try:
    from pydantic import ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    pytest.skip("pydantic not installed", allow_module_level=True)

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from v8 import (
    ScanConfig, DirectorySummary, CleanEntry, WhitelistRule,
    CognitiveLabel, LabelSource, RiskLevel, SafetyTier, DeletionMode,
    AIBrain, IntentParser, CognitiveAdapter,
    FunnelScanner, PluginRegistry,
    EvolutionEngine, WhitelistStore, FoolproofProposer,
    SafeDeleter, ProtectedPaths, ProtectedPathError,
)
from v8.platform_paths import PlatformPaths
from v8.scan_cache import ScanCache
from v8.audit import AuditLogger
from v8.duplicates import DuplicateDetector, DuplicateGroup
from v8.history import HistoryStore, Forecaster, DiskSnapshot, take_snapshot
from v8.orchestrator import Orchestrator
from v8.safeguard import RECYCLE_THRESHOLD_BYTES


# ===========================================================================
# types.py
# ===========================================================================

def test_scan_config_excludes_root_paths():
    with pytest.raises(ValidationError):
        ScanConfig(exclude_paths=[Path("C:\\")])
    with pytest.raises(ValidationError):
        ScanConfig(exclude_paths=[Path("/")])


def test_scan_config_hard_mode_requires_consent():
    with pytest.raises(ValidationError):
        ScanConfig(
            deletion_mode=DeletionMode.HARD,
            require_explicit_consent_for=[],
        )


def test_scan_config_dry_run_is_default():
    cfg = ScanConfig()
    assert cfg.deletion_mode is DeletionMode.DRY_RUN


def test_directory_summary_total_mb():
    s = DirectorySummary(path=Path("/foo"), total_bytes=5 * 1024 * 1024)
    assert abs(s.total_mb - 5.0) < 0.01


def test_clean_entry_user_facing_prompt_no_tech_jargon():
    s = DirectorySummary(path=Path("/x/y/node_modules"), total_bytes=200 * 1024 * 1024)
    label = CognitiveLabel(
        source=LabelSource.LEVEL_1_FINGERPRINT,
        human_readable_label="Node.js project deps",
        human_readable_risk="reinstall to restore",
        confidence=0.9,
        technical_name="node_modules",
        technical_path="/x/y/node_modules",
        suggested_action="review",
    )
    e = CleanEntry(id="x", summary=s, label=label, risk_level=RiskLevel.LOW)
    prompt = e.user_facing_prompt
    assert "node_modules" not in prompt


# ===========================================================================
# ai_brain.py
# ===========================================================================

def test_intent_parser_drive_extraction():
    p = IntentParser()
    cfg = p.parse("clean C drive, keep Genshin")
    assert any("C:" in str(p_) for p_ in cfg.target_paths)
    assert any("genshin" in str(p_).lower() or "原神" in str(p_) for p_ in cfg.exclude_paths)


def test_intent_parser_no_drive_means_all_drives():
    p = IntentParser()
    cfg = p.parse("clean computer")
    assert len(cfg.target_paths) >= 1


def test_intent_parser_hard_mode_keyword():
    p = IntentParser()
    cfg = p.parse("clean C --execute")
    assert cfg.deletion_mode is DeletionMode.HARD


def test_cognitive_adapter_level1_vmware_vmdk():
    s = DirectorySummary(
        path=Path(r"D:\VMware\Kali.vmdk"),
        total_bytes=14 * 1024**3,
        file_count=1,
        feature_files=["Kali.vmdk"],
    )
    entry = CognitiveAdapter().label(s)
    assert entry.label.source is LabelSource.LEVEL_1_FINGERPRINT
    assert "vmdk" not in entry.label.human_readable_label.lower()
    assert "VMware" in entry.label.human_readable_label
    assert entry.risk_level is RiskLevel.HIGH
    assert entry.label.suggested_action == "ask_user"


def test_cognitive_adapter_level1_setup_exe():
    s = DirectorySummary(
        path=Path(r"C:\Users\x\Downloads\setup.exe"),
        total_bytes=50 * 1024**2,
        file_count=1,
        feature_files=["setup.exe"],
    )
    entry = CognitiveAdapter().label(s)
    assert "setup" not in entry.label.human_readable_label.lower()
    assert entry.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH)


def test_cognitive_adapter_level3_fallback():
    s = DirectorySummary(
        path=Path(r"D:\some\random\dir"),
        total_bytes=500 * 1024**2,
        file_count=100,
    )
    entry = CognitiveAdapter().label(s)
    assert entry.label.source is LabelSource.LEVEL_3_FALLBACK
    assert entry.risk_level is RiskLevel.MEDIUM


def test_cognitive_adapter_never_displays_tech_suffixes_in_label():
    tech_names = [".tmp", ".iso", ".dll", ".vmdk", ".cache"]
    s = DirectorySummary(
        path=Path(r"C:\test.tmp"),
        total_bytes=100,
        file_count=1,
    )
    entry = CognitiveAdapter().label(s)
    for tech in tech_names:
        assert tech not in entry.label.human_readable_label


def test_cognitive_adapter_browser_cache_l1():
    s = DirectorySummary(
        path=Path(r"C:\Users\me\AppData\Local\Google\Chrome\User Data\Default\Cache"),
        total_bytes=500 * 1024**2,
        file_count=1000,
    )
    entry = CognitiveAdapter().label(s)
    assert entry.label.source is LabelSource.LEVEL_1_FINGERPRINT
    assert entry.risk_level is RiskLevel.NONE


def test_cognitive_adapter_wechat_cache_l1():
    s = DirectorySummary(
        path=Path(r"C:\Users\me\Documents\WeChat Files\xwechat_files\FileStorage\Cache"),
        total_bytes=2 * 1024**3,
        file_count=5000,
    )
    entry = CognitiveAdapter().label(s)
    assert entry.label.source is LabelSource.LEVEL_1_FINGERPRINT
    assert entry.risk_level is RiskLevel.NONE


def test_cognitive_adapter_steam_shader_cache_l1():
    s = DirectorySummary(
        path=Path(r"C:\Program Files (x86)\Steam\shadercache"),
        total_bytes=1 * 1024**3,
        file_count=500,
    )
    entry = CognitiveAdapter().label(s)
    assert entry.label.source is LabelSource.LEVEL_1_FINGERPRINT
    assert entry.risk_level is RiskLevel.NONE


# ===========================================================================
# safeguard.py
# ===========================================================================

def test_protected_windows_system32():
    pp = ProtectedPaths()
    assert pp.is_protected(r"C:\Windows\System32\evil.dll")


def test_protected_users_dir_not_protected():
    pp = ProtectedPaths()
    assert not pp.is_protected(r"C:\Users\me\Documents\file.txt")


def test_protected_assert_raises():
    pp = ProtectedPaths()
    with pytest.raises(ProtectedPathError):
        pp.assert_not_protected(r"C:\Windows\System32")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX paths not applicable on Windows")
def test_protected_posix():
    pp = ProtectedPaths()
    assert pp.is_protected("/etc/passwd")
    assert pp.is_protected("/usr/bin/python3")
    assert not pp.is_protected("/home/user/file.txt")


def test_safe_deleter_dry_run():
    pp = ProtectedPaths()
    deleter = SafeDeleter(pp)
    s = DirectorySummary(path=Path(r"C:\temp\junk.tmp"), total_bytes=1000)
    e = CleanEntry(
        id="d", summary=s,
        label=CognitiveLabel(
            source=LabelSource.LEVEL_1_FINGERPRINT,
            human_readable_label="temp junk", human_readable_risk="", confidence=1.0,
            technical_name="junk.tmp", technical_path="x", suggested_action="delete_safely",
        ),
        risk_level=RiskLevel.NONE,
    )
    ok, msg, freed = deleter.delete_entry(e, DeletionMode.DRY_RUN)
    assert ok
    assert "[dry-run]" in msg


def test_safe_deleter_blocks_protected_path():
    deleter = SafeDeleter(ProtectedPaths())
    s = DirectorySummary(path=Path(r"C:\Windows\System32\evil.dll"), total_bytes=100)
    e = CleanEntry(
        id="p", summary=s,
        label=CognitiveLabel(
            source=LabelSource.LEVEL_1_FINGERPRINT,
            human_readable_label="x", human_readable_risk="", confidence=1.0,
            technical_name="x", technical_path="x", suggested_action="delete_safely",
        ),
        risk_level=RiskLevel.NONE,
    )
    with pytest.raises(ProtectedPathError):
        deleter.delete_entry(e, DeletionMode.HARD)


# ===========================================================================
# evolution.py
# ===========================================================================

def test_whitelist_health_check_overdue():
    rule = WhitelistRule(
        id="x", path_pattern="C:\\foo",
        human_readable_reason="r", created_at=datetime.now() - timedelta(days=60),
        last_reviewed_at=datetime.now() - timedelta(days=60),
        baseline_size_bytes=100,
    )
    assert rule.is_overdue_for_review


def test_whitelist_health_check_bloated():
    rule = WhitelistRule(
        id="x", path_pattern="C:\\foo",
        human_readable_reason="r", created_at=datetime.now(),
        last_reviewed_at=datetime.now(),
        baseline_size_bytes=100 * 1024**2,
        current_size_bytes=6 * 1024**3,
    )
    assert rule.is_bloated


def test_whitelist_consequence_warning_includes_growth():
    rule = WhitelistRule(
        id="x", path_pattern="C:\\foo",
        human_readable_reason="r", created_at=datetime.now(),
        last_reviewed_at=datetime.now(),
        baseline_size_bytes=100 * 1024**2,
        current_size_bytes=1 * 1024**3,
    )
    warning = rule.consequence_warning()
    assert len(warning) > 0


def test_foolproof_proposer_default_is_no_proposal():
    store = WhitelistStore()
    p = FoolproofProposer(store)
    s = DirectorySummary(path=Path(r"D:\foo"), total_bytes=200 * 1024**2)
    e = CleanEntry(
        id="x", summary=s,
        label=CognitiveLabel(
            source=LabelSource.LEVEL_1_FINGERPRINT,
            human_readable_label="test", human_readable_risk="", confidence=1.0,
            technical_name="x", technical_path="x", suggested_action="review",
        ),
        risk_level=RiskLevel.MEDIUM,
    )
    p.record_skip(e)
    p.record_skip(e)
    assert p.maybe_propose(e) is None


def test_foolproof_proposer_triggers_after_n_skips():
    store = WhitelistStore()
    p = FoolproofProposer(store)
    s = DirectorySummary(path=Path(r"D:\foo"), total_bytes=200 * 1024**2)
    e = CleanEntry(
        id="x", summary=s,
        label=CognitiveLabel(
            source=LabelSource.LEVEL_1_FINGERPRINT,
            human_readable_label="test", human_readable_risk="", confidence=1.0,
            technical_name="x", technical_path="x", suggested_action="review",
        ),
        risk_level=RiskLevel.MEDIUM,
    )
    for _ in range(3):
        p.record_skip(e)
    proposal = p.maybe_propose(e)
    assert proposal is not None


def test_foolproof_proposer_never_proposes_high_risk():
    store = WhitelistStore()
    p = FoolproofProposer(store)
    s = DirectorySummary(path=Path(r"D:\foo"), total_bytes=200 * 1024**2)
    e = CleanEntry(
        id="x", summary=s,
        label=CognitiveLabel(
            source=LabelSource.LEVEL_1_FINGERPRINT,
            human_readable_label="test", human_readable_risk="", confidence=1.0,
            technical_name="x", technical_path="x", suggested_action="ask_user",
        ),
        risk_level=RiskLevel.HIGH,
    )
    for _ in range(10):
        p.record_skip(e)
    assert p.maybe_propose(e) is None


# ===========================================================================
# End-to-end smoke test
# ===========================================================================

def test_end_to_end_no_crash(tmp_path):
    (tmp_path / "AppData" / "Local" / "Temp").mkdir(parents=True)
    (tmp_path / "AppData" / "Local" / "Temp" / "junk.tmp").write_bytes(b"\0" * 1024)
    cfg = ScanConfig(
        target_paths=[tmp_path],
        deep=True,
        deletion_mode=DeletionMode.DRY_RUN,
    )
    brain = AIBrain()
    scanner = FunnelScanner(cfg)
    summaries = scanner.scan()
    entries = brain.label_all(summaries)
    assert isinstance(entries, list)


# ===========================================================================
# v8.1 — PlatformPaths
# ===========================================================================

def test_platform_paths_resolves():
    paths = PlatformPaths.resolve()
    assert len(paths.temp_dirs) > 0
    assert len(paths.dev_caches) > 0
    assert len(paths.browser_caches) > 0
    assert len(paths.ide_caches) > 0


def test_platform_paths_all_scannable():
    paths = PlatformPaths.resolve()
    scannable = paths.all_scannable()
    assert all(isinstance(p, Path) for p in scannable)


# ===========================================================================
# v8.1 — ScanCache
# ===========================================================================

def test_scan_cache_roundtrip(tmp_path):
    db = tmp_path / "test-cache.sqlite"
    cache = ScanCache(db)
    (tmp_path / "test_dir").mkdir()
    s = DirectorySummary(
        path=tmp_path / "test_dir",
        total_bytes=1024 * 1024,
        file_count=42,
        feature_files=["package.json"],
        feature_dirs=["node_modules"],
    )
    cache.put(s)
    cached = cache.get(tmp_path / "test_dir")
    assert cached is not None
    assert cached.total_bytes == 1024 * 1024
    assert cached.file_count == 42
    cache.close()


def test_scan_cache_stats(tmp_path):
    db = tmp_path / "test-cache.sqlite"
    cache = ScanCache(db)
    stats = cache.stats()
    assert stats["entries"] == 0
    cache.close()


def test_scan_cache_clear(tmp_path):
    db = tmp_path / "test-cache.sqlite"
    cache = ScanCache(db)
    (tmp_path / "x").mkdir()
    s = DirectorySummary(path=tmp_path / "x", total_bytes=100, file_count=1)
    cache.put(s)
    assert cache.stats()["entries"] == 1
    deleted = cache.clear()
    assert deleted == 1
    assert cache.stats()["entries"] == 0
    cache.close()


# ===========================================================================
# v8.1 — AuditLogger
# ===========================================================================

def test_audit_chain_integrity(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    audit = AuditLogger(audit_file)
    s = DirectorySummary(path=Path("/test"), total_bytes=100)
    label = CognitiveLabel(
        source=LabelSource.LEVEL_1_FINGERPRINT,
        human_readable_label="test", human_readable_risk="", confidence=1.0,
        technical_name="x", technical_path="x", suggested_action="review",
    )
    e = CleanEntry(id="t", summary=s, label=label, risk_level=RiskLevel.LOW)
    audit.log_action("TEST1", e, "first entry")
    audit.log_action("TEST2", e, "second entry")
    audit.log_action("TEST3", None, "third entry")
    broken = audit.verify_chain()
    assert len(broken) == 0


def test_audit_chain_detects_tamper(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    audit = AuditLogger(audit_file)
    s = DirectorySummary(path=Path("/test"), total_bytes=100)
    label = CognitiveLabel(
        source=LabelSource.LEVEL_1_FINGERPRINT,
        human_readable_label="test", human_readable_risk="", confidence=1.0,
        technical_name="x", technical_path="x", suggested_action="review",
    )
    e = CleanEntry(id="t", summary=s, label=label, risk_level=RiskLevel.LOW)
    audit.log_action("TEST", e, "first")
    audit.log_action("TEST", e, "second")
    audit.log_action("TEST", e, "third")

    # Tamper: rewrite file, removing the second entry (breaks chain)
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    # Keep first and third, drop second — chain should break at third
    tampered = [lines[0], lines[2]]
    audit_file.write_text("\n".join(tampered) + "\n", encoding="utf-8")

    audit2 = AuditLogger(audit_file)
    broken = audit2.verify_chain()
    assert len(broken) > 0


# ===========================================================================
# v8.1 — DuplicateDetector
# ===========================================================================

def test_duplicate_detector_finds_dupes(tmp_path):
    content = b"hello world " * 100000
    f1 = tmp_path / "file1.bin"
    f2 = tmp_path / "sub" / "file2.bin"
    f2.parent.mkdir()
    f1.write_bytes(content)
    f2.write_bytes(content)

    detector = DuplicateDetector(min_size_bytes=1024)
    groups = detector.scan([tmp_path])
    assert len(groups) == 1
    assert groups[0].count == 2
    assert groups[0].wasted_bytes == len(content)


def test_duplicate_detector_ignores_different_files(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"x" * 2000)
    f2.write_bytes(b"y" * 2000)

    detector = DuplicateDetector(min_size_bytes=1024)
    groups = detector.scan([tmp_path])
    assert len(groups) == 0


def test_duplicate_detector_skips_small_files(tmp_path):
    f1 = tmp_path / "tiny1.txt"
    f2 = tmp_path / "tiny2.txt"
    f1.write_bytes(b"hi")
    f2.write_bytes(b"hi")

    detector = DuplicateDetector(min_size_bytes=1024)
    groups = detector.scan([tmp_path])
    assert len(groups) == 0


# ===========================================================================
# v8.1 — History / Forecast
# ===========================================================================

def test_history_roundtrip(tmp_path):
    hist_file = tmp_path / "history.jsonl"
    store = HistoryStore(hist_file)
    snap = DiskSnapshot(
        timestamp=1000.0, drive="C:\\",
        total_bytes=100 * 1024**3, used_bytes=60 * 1024**3, free_bytes=40 * 1024**3,
    )
    store.record(snap)
    loaded = store.load(drive="C:\\")
    assert len(loaded) == 1
    assert loaded[0].free_bytes == 40 * 1024**3


def test_forecaster_basic():
    fc = Forecaster()
    base = 1000000.0
    snapshots = [
        DiskSnapshot(
            timestamp=base + i * 86400, drive="C:\\",
            total_bytes=100 * 1024**3,
            used_bytes=(50 + i) * 1024**3,
            free_bytes=(50 - i) * 1024**3,
        )
        for i in range(3)
    ]
    result = fc.forecast(snapshots)
    assert result is not None
    assert result.days_until_full is not None
    assert result.days_until_full > 0
    # 48 days with 1GB/day growth at 50GB free: not urgent (>30 days)
    assert not result.is_urgent


def test_forecaster_stable_disk():
    fc = Forecaster()
    base = 1000000.0
    snapshots = [
        DiskSnapshot(
            timestamp=base + i * 86400, drive="C:\\",
            total_bytes=100 * 1024**3,
            used_bytes=50 * 1024**3,
            free_bytes=50 * 1024**3,
        )
        for i in range(5)
    ]
    result = fc.forecast(snapshots)
    assert result is not None
    assert result.days_until_full is None


def test_take_snapshot():
    snap = take_snapshot("C:\\")
    if snap is not None:
        assert snap.total_bytes > 0
        assert snap.free_bytes > 0
        assert snap.usage_pct > 0


# ===========================================================================
# v8.1 — Intent Parser enhancements
# ===========================================================================

def test_intent_parser_deep_mode():
    p = IntentParser()
    cfg = p.parse("deep clean C drive")
    assert cfg.deep is True
    assert cfg.min_size_mb == 10


def test_intent_parser_duplicate_mode():
    p = IntentParser()
    cfg = p.parse("find duplicates")
    assert cfg.include_duplicates is True


def test_intent_parser_old_files_mode():
    p = IntentParser()
    cfg = p.parse("find old files")
    assert cfg.include_old_files is True


# ===========================================================================
# v8.1 — Orchestrator integration
# ===========================================================================

def test_orchestrator_end_to_end(tmp_path):
    (tmp_path / "Temp").mkdir()
    (tmp_path / "Temp" / "junk.tmp").write_bytes(b"\0" * 1024)
    cfg = ScanConfig(
        target_paths=[tmp_path],
        deletion_mode=DeletionMode.DRY_RUN,
        min_size_mb=1,
    )
    orch = Orchestrator()
    result = orch.run(cfg, use_cache=False, record_history=False)
    assert isinstance(result.entries, list)
    assert result.scan_duration_s >= 0
    assert result.bytes_freed == 0


# ===========================================================================
# v8 — SafeDeleter deletion logic tests
# ===========================================================================


def _make_entry(path: Path, size: int, risk: RiskLevel = RiskLevel.LOW, entry_id: str = "t") -> CleanEntry:
    """Helper to build a CleanEntry pointing at *path* with *size* bytes."""
    s = DirectorySummary(path=path, total_bytes=size, file_count=1)
    label = CognitiveLabel(
        source=LabelSource.LEVEL_1_FINGERPRINT,
        human_readable_label="test item",
        human_readable_risk="",
        confidence=1.0,
        technical_name=path.name,
        technical_path=str(path),
        suggested_action="delete_safely",
    )
    return CleanEntry(id=entry_id, summary=s, label=label, risk_level=risk)


def test_safe_deleter_recycle_small_file(tmp_path):
    """Files under 100MB should be moved (recycled), not permanently deleted."""
    target = tmp_path / "small_junk.tmp"
    target.write_bytes(b"\0" * 1024)

    deleter = SafeDeleter(ProtectedPaths(), quarantine_dir=tmp_path / "q")
    entry = _make_entry(target, size=1024, risk=RiskLevel.LOW)

    ok, msg, freed = deleter.delete_entry(entry, DeletionMode.SOFT)

    assert ok is True
    assert freed > 0
    assert not target.exists(), "original file should have been moved away"
    # The file should now live somewhere under the quarantine dir tree
    recycled = list((tmp_path / "q" / "RecycleBin").rglob(target.name))
    assert len(recycled) == 1, "file should be in the RecycleBin sub-quarantine"


def test_safe_deleter_quarantine_large_file(tmp_path):
    """Files >= 100MB should be quarantined, not recycled."""
    target = tmp_path / "large_blob.bin"
    # Create a sparse-like large file without actually writing 100MB of data
    with open(target, "wb") as f:
        f.seek(RECYCLE_THRESHOLD_BYTES)
        f.write(b"\0")

    deleter = SafeDeleter(ProtectedPaths(), quarantine_dir=tmp_path / "q")
    entry = _make_entry(target, size=RECYCLE_THRESHOLD_BYTES, risk=RiskLevel.LOW)

    ok, msg, freed = deleter.delete_entry(entry, DeletionMode.SOFT)

    assert ok is True
    assert freed > 0
    assert not target.exists(), "original file should have been moved away"
    quarantined = list((tmp_path / "q" / "Quarantine").rglob(target.name))
    assert len(quarantined) == 1, "file should be in the Quarantine sub-directory"


def test_safe_deleter_wipe_requires_hard_mode(tmp_path):
    """HIGH-risk entries routed to WIPE tier must be rejected under SOFT mode."""
    target = tmp_path / "dangerous.dat"
    target.write_bytes(b"sensitive" * 100)

    deleter = SafeDeleter(ProtectedPaths(), quarantine_dir=tmp_path / "q")
    entry = _make_entry(target, size=800, risk=RiskLevel.HIGH)

    ok, msg, freed = deleter.delete_entry(entry, DeletionMode.SOFT)

    assert ok is False
    assert "WIPE requires" in msg
    assert freed == 0
    assert target.exists(), "file must NOT be deleted when wipe is refused"


def test_safe_deleter_wipe_with_hard_mode(tmp_path):
    """HIGH-risk entries should be permanently wiped under HARD mode."""
    target = tmp_path / "dangerous.dat"
    file_size = 4096
    target.write_bytes(b"\0" * file_size)

    deleter = SafeDeleter(ProtectedPaths(), quarantine_dir=tmp_path / "q")
    entry = _make_entry(target, size=file_size, risk=RiskLevel.HIGH)

    ok, msg, freed = deleter.delete_entry(entry, DeletionMode.HARD)

    assert ok is True
    assert freed > 0
    assert not target.exists(), "file should be permanently deleted"


def test_safe_deleter_dry_run_never_deletes(tmp_path):
    """DRY_RUN mode must never touch the filesystem."""
    target = tmp_path / "keep_me.tmp"
    target.write_bytes(b"important data")

    deleter = SafeDeleter(ProtectedPaths(), quarantine_dir=tmp_path / "q")
    entry = _make_entry(target, size=14, risk=RiskLevel.NONE)

    ok, msg, freed = deleter.delete_entry(entry, DeletionMode.DRY_RUN)

    assert ok is True
    assert "[dry-run]" in msg
    assert freed == 0
    assert target.exists(), "file must still exist after dry-run"


def test_safe_deleter_protected_path_blocked(tmp_path):
    """Attempting to delete a protected system path must raise ProtectedPathError."""
    protected_file = Path(r"C:\Windows\System32\fake.dll")

    deleter = SafeDeleter(ProtectedPaths(), quarantine_dir=tmp_path / "q")
    entry = _make_entry(protected_file, size=100, risk=RiskLevel.LOW)

    with pytest.raises(ProtectedPathError):
        deleter.delete_entry(entry, DeletionMode.SOFT)


def test_safe_deleter_quarantine_sweep(tmp_path):
    """Quarantined items older than retention period should be swept away."""
    q_dir = tmp_path / "q"
    q_dir.mkdir()
    old_item = q_dir / "old_file.bin"
    old_item.write_bytes(b"expired data")

    # Back-date the file's mtime to 31 days ago (beyond default 30-day retention)
    old_time = time.time() - 31 * 86400
    os.utime(old_item, (old_time, old_time))

    deleter = SafeDeleter(ProtectedPaths(), quarantine_dir=q_dir)
    swept = deleter.sweep_quarantine(max_age_days=30)

    assert swept == 1
    assert not old_item.exists(), "old quarantined item should have been removed"


def test_protected_paths_symlink_resolution(tmp_path):
    """Symlinks that resolve to a protected path must still be flagged."""
    pp = ProtectedPaths()

    if sys.platform == "win32":
        # On Windows, symlinks may require elevated privileges
        link = tmp_path / "sneaky_link"
        try:
            link.symlink_to(r"C:\Windows\System32")
        except OSError:
            pytest.skip("symlink creation requires elevated privileges on Windows")
    else:
        link = tmp_path / "sneaky_link"
        try:
            link.symlink_to("/etc")
        except OSError:
            pytest.skip("symlink creation not supported in this environment")

    assert pp.is_protected(str(link)), "symlink to protected path must be detected"
    assert pp.is_protected(str(link / "any_file.dll")), "files under symlinked protected path must be blocked"


def test_orchestrator_with_user_decisions(tmp_path):
    """Orchestrator should honor a custom user_decision callback."""
    # Set up test files at different risk levels
    none_dir = tmp_path / "cache"
    none_dir.mkdir()
    (none_dir / "browser.tmp").write_bytes(b"\0" * 2048)

    high_dir = tmp_path / "important"
    high_dir.mkdir()
    (high_dir / "database.vmdk").write_bytes(b"\0" * 2048)

    cfg = ScanConfig(
        target_paths=[tmp_path],
        deletion_mode=DeletionMode.DRY_RUN,
        min_size_mb=1,
    )

    approved_ids: list[str] = []
    skipped_ids: list[str] = []

    def decision(entry: CleanEntry) -> str:
        if entry.risk_level is RiskLevel.NONE:
            approved_ids.append(entry.id)
            return "approve"
        skipped_ids.append(entry.id)
        return "skip"

    orch = Orchestrator()
    result = orch.run(cfg, user_decision=decision, use_cache=False, record_history=False)

    # At minimum, NONE-risk entries should have been approved
    none_entries = [e for e in result.entries if e.risk_level is RiskLevel.NONE]
    high_entries = [e for e in result.entries if e.risk_level is RiskLevel.HIGH]

    if none_entries:
        assert all(e in result.approved for e in none_entries), \
            "NONE-risk entries should be approved by the custom callback"
    if high_entries:
        assert all(e in result.skipped for e in high_entries), \
            "HIGH-risk entries should be skipped by the custom callback"


# ===========================================================================
# v8 — scanner_v3.py (DeepScanner + CleanupEngine)
# ===========================================================================

from v8.scanner_v3 import DeepScanner, CleanupEngine, ScanItem
from unittest.mock import patch, MagicMock


def test_deep_scanner_categorize_safe():
    """Paths containing 'cache' or 'temp' should be categorized as SAFE."""
    scanner = DeepScanner()
    path_cache = Path(r"C:\Users\me\AppData\Local\Google\Chrome\Cache\data")
    path_temp = Path(r"C:\Users\me\AppData\Local\Temp\junk_file")

    cat1, reason1 = scanner._categorize(path_cache, 1024, True)
    assert cat1 == 'SAFE', f"Expected SAFE for cache path, got {cat1}"

    cat2, reason2 = scanner._categorize(path_temp, 2048, False)
    assert cat2 == 'SAFE', f"Expected SAFE for temp path, got {cat2}"


def test_deep_scanner_categorize_keep():
    """Paths containing 'vmware' or '.vmdk' should be categorized as KEEP."""
    scanner = DeepScanner()
    path_vmware = Path(r"D:\VMware\Ubuntu\disk.vmdk")
    path_vmdk = Path(r"D:\VMs\Kali.vmdk")

    cat1, reason1 = scanner._categorize(path_vmware, 10 * 1024**3, False)
    assert cat1 == 'KEEP', f"Expected KEEP for vmware path, got {cat1}"

    cat2, reason2 = scanner._categorize(path_vmdk, 5 * 1024**3, False)
    assert cat2 == 'KEEP', f"Expected KEEP for .vmdk path, got {cat2}"


def test_deep_scanner_categorize_review():
    """Paths containing 'download' should be categorized as REVIEW."""
    scanner = DeepScanner()
    path_download = Path(r"C:\Users\me\Downloads\setup.exe")

    cat, reason = scanner._categorize(path_download, 50 * 1024**2, False)
    assert cat == 'REVIEW', f"Expected REVIEW for download path, got {cat}"
    assert 'download' in reason.lower() or 'downloads' in reason.lower()


def test_deep_scanner_categorize_unknown_defaults_to_review():
    """An unrecognized small file should default to REVIEW, not SAFE."""
    scanner = DeepScanner()
    path_unknown = Path(r"D:\qz\mystery_file.xyz")

    cat, reason = scanner._categorize(path_unknown, 500, False)
    assert cat == 'REVIEW', f"Expected REVIEW for unknown small file, got {cat}"
    assert reason == 'Unknown small item', f"Expected 'Unknown small item', got '{reason}'"


def test_deep_scanner_categorize_large_unknown():
    """A file > 500MB with no pattern match should be REVIEW with 'Large unknown'."""
    scanner = DeepScanner()
    path_large = Path(r"D:\data\bigfile.bin")
    large_size = 600 * 1024 * 1024  # 600MB

    cat, reason = scanner._categorize(path_large, large_size, False)
    assert cat == 'REVIEW', f"Expected REVIEW for large unknown, got {cat}"
    assert reason == 'Large unknown', f"Expected 'Large unknown', got '{reason}'"


def test_deep_scanner_scan_nonexistent_raises():
    """Scanning a nonexistent path should raise FileNotFoundError."""
    scanner = DeepScanner()
    nonexistent = Path(r"Z:\this\path\does\not\exist_12345")

    with pytest.raises(FileNotFoundError):
        scanner.scan(nonexistent)


def test_deep_scanner_scan_creates_tree(tmp_path):
    """Scan a temp directory structure and verify the tree structure."""
    # Create structure: tmp_path/subdir/file.txt, tmp_path/other_dir/
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file.txt").write_bytes(b"\0" * 1024)

    other_dir = tmp_path / "other_dir"
    other_dir.mkdir()
    (other_dir / "data.bin").write_bytes(b"\0" * 512)

    scanner = DeepScanner(min_size=0)
    root = scanner.scan(tmp_path)

    assert root.is_dir is True
    assert root.path == tmp_path
    assert root.size >= 1024 + 512
    assert root.file_count >= 2
    assert len(root.children) >= 2

    child_names = {c.name for c in root.children}
    assert "subdir" in child_names
    assert "other_dir" in child_names


def test_cleanup_engine_delete_item_respects_protection(tmp_path):
    """Trying to delete a protected path via CleanupEngine should be blocked."""
    scanner = DeepScanner()
    engine = CleanupEngine(scanner, deletion_mode=DeletionMode.SOFT)

    # Create a ScanItem pointing at a protected system path
    protected_item = ScanItem(
        path=Path(r"C:\Windows\System32\fake.dll"),
        name="fake.dll",
        size=100,
        file_count=1,
        is_dir=False,
        depth=0,
        category='SAFE',
        reason='test',
        children=[],
    )

    ok, msg = engine.delete_item(protected_item)
    assert ok is False
    assert 'protected' in msg.lower()


def test_cleanup_engine_dry_run_default():
    """CleanupEngine should default to DRY_RUN mode."""
    scanner = DeepScanner()
    engine = CleanupEngine(scanner)
    assert engine.deletion_mode == DeletionMode.DRY_RUN


def test_cleanup_engine_delete_safe_items_requires_confirm(tmp_path):
    """delete_safe_items should return 0 when confirm=False."""
    # Create a temp file that will be categorized as SAFE (cache)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "data.tmp").write_bytes(b"\0" * 1024)

    scanner = DeepScanner(min_size=0)
    root = scanner.scan(tmp_path)

    engine = CleanupEngine(scanner, deletion_mode=DeletionMode.DRY_RUN)
    deleted = engine.delete_safe_items(root, confirm=False)
    assert deleted == 0


# ===========================================================================
# v8 — memory_optimizer.py
# ===========================================================================

from v8.memory_optimizer import MemoryOptimizer, MemoryProcess


def _make_optimizer_for_testing():
    """Create a MemoryOptimizer with psutil mocked."""
    mock_mem = MagicMock()
    mock_mem.total = 16 * 1024**3
    mock_mem.used = 8 * 1024**3
    with patch('v8.memory_optimizer.psutil.virtual_memory', return_value=mock_mem):
        return MemoryOptimizer()


def test_memory_optimizer_categorize():
    """Test _categorize() with known process names."""
    opt = _make_optimizer_for_testing()

    assert opt._categorize('chrome.exe') == 'BROWSER'
    assert opt._categorize('code.exe') == 'IDE'
    assert opt._categorize('python.exe') == 'AI'
    assert opt._categorize('svchost.exe') == 'SYSTEM'
    assert opt._categorize('randomapp.exe') == 'OTHER'


def test_memory_optimizer_get_memory_hogs():
    """Test get_memory_hogs with manually set processes."""
    opt = _make_optimizer_for_testing()

    opt.processes = [
        MemoryProcess(pid=1, name="big.exe", memory_mb=200, cpu_percent=5.0,
                       handles=100, threads=10, category="APP"),
        MemoryProcess(pid=2, name="small.exe", memory_mb=10, cpu_percent=1.0,
                       handles=50, threads=2, category="OTHER"),
        MemoryProcess(pid=3, name="huge.exe", memory_mb=500, cpu_percent=20.0,
                       handles=200, threads=30, category="BROWSER"),
    ]

    hogs = opt.get_memory_hogs(threshold_mb=100)
    assert len(hogs) == 2
    names = {h.name for h in hogs}
    assert "big.exe" in names
    assert "huge.exe" in names
    assert "small.exe" not in names


def test_memory_optimizer_dry_run_optimize():
    """optimize_windows_settings(dry_run=True) should return [DRY RUN] strings."""
    opt = _make_optimizer_for_testing()
    results = opt.optimize_windows_settings(dry_run=True)

    assert len(results) > 0
    for r in results:
        assert '[DRY RUN]' in r


def test_memory_optimizer_dry_run_stop_services():
    """stop_unnecessary_services(dry_run=True) should return dry run output."""
    opt = _make_optimizer_for_testing()
    results = opt.stop_unnecessary_services(dry_run=True)

    assert len(results) > 0
    for r in results:
        assert '[DRY RUN]' in r


def test_memory_optimizer_dry_run_disable_startup():
    """disable_startup_programs(dry_run=True) should return dry run output."""
    opt = _make_optimizer_for_testing()
    results = opt.disable_startup_programs(dry_run=True)

    assert len(results) > 0
    for r in results:
        assert '[DRY RUN]' in r


# ===========================================================================
# v8 — performance_optimizer.py
# ===========================================================================

from v8.performance_optimizer import PerformanceOptimizer, OptimizationItem


def test_performance_optimizer_apply_dry_run():
    """apply_optimization with dry_run=True should return True without executing."""
    opt = PerformanceOptimizer()
    item = OptimizationItem(
        name="TestStartup",
        category="STARTUP",
        impact="MEDIUM",
        description="Test startup item",
        action='disable_startup("TestStartup")',
        enabled=True,
        safe_to_disable=True,
    )

    result = opt.apply_optimization(item, dry_run=True)
    assert result is True


def test_performance_optimizer_apply_unknown_category():
    """apply_optimization with UNKNOWN category should return False."""
    opt = PerformanceOptimizer()
    item = OptimizationItem(
        name="UnknownThing",
        category="UNKNOWN",
        impact="LOW",
        description="Unknown optimization",
        action="none",
        enabled=True,
        safe_to_disable=True,
    )

    result = opt.apply_optimization(item, dry_run=True)
    assert result is False


# ===========================================================================
# v8 — iterative_scanner.py
# ===========================================================================

from v8.iterative_scanner import IterativeScanner


def test_iterative_scanner_load_empty_history(tmp_path):
    """IterativeScanner with no history file should have empty history."""
    fake_history = tmp_path / "nonexistent_history.json"
    with patch.object(IterativeScanner, 'HISTORY_FILE', fake_history):
        scanner = IterativeScanner()
        assert scanner.history == []
        assert scanner.scan_count == 0


def test_iterative_scanner_record_and_load(tmp_path):
    """Record a cleanup action and verify it appears in history."""
    fake_history = tmp_path / "history.json"
    with patch.object(IterativeScanner, 'HISTORY_FILE', fake_history):
        scanner = IterativeScanner()
        scanner.record_cleanup('/tmp/test_file', 1024, 'SAFE')

        assert len(scanner.history) == 1
        assert scanner.history[0].path == '/tmp/test_file'
        assert scanner.history[0].size == 1024
        assert scanner.history[0].category == 'SAFE'

        # Reload from disk to verify persistence
        scanner2 = IterativeScanner()
        assert len(scanner2.history) == 1
        assert scanner2.history[0].path == '/tmp/test_file'


def test_iterative_scanner_scan_depth_increases(tmp_path):
    """First scan uses max_depth=2, second scan max_depth=3, third+ scan max_depth=4."""
    # Create a real directory for scanning
    scan_dir = tmp_path / "project"
    scan_dir.mkdir()
    (scan_dir / "file.bin").write_bytes(b"\0" * 1024)

    fake_history = tmp_path / "empty_history.json"
    captured_depths: list[int] = []

    original_init = DeepScanner.__init__

    def spy_init(self, max_depth=4, min_size=10 * 1024 * 1024):
        captured_depths.append(max_depth)
        original_init(self, max_depth=max_depth, min_size=min_size)

    with patch.object(IterativeScanner, 'HISTORY_FILE', fake_history), \
         patch.object(DeepScanner, '__init__', spy_init):
        scanner = IterativeScanner()

        scanner.scan_with_learning(scan_dir)
        scanner.scan_with_learning(scan_dir)
        scanner.scan_with_learning(scan_dir)

    assert captured_depths[0] == 2, f"First scan depth should be 2, got {captured_depths[0]}"
    assert captured_depths[1] == 3, f"Second scan depth should be 3, got {captured_depths[1]}"
    assert captured_depths[2] == 4, f"Third scan depth should be 4, got {captured_depths[2]}"
