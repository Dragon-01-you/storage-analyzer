#!/usr/bin/env python3
"""Test framework for storage analyzer.

Runs tests to verify functionality and correctness.

Usage:
    python test.py [options]
    python test.py --all
    python test.py --scan
    python test.py --classify
    python test.py --utils
    python test.py --filetypes
"""
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)


def log(msg):
    print(f"[test] {msg}", file=sys.stderr, flush=True)


class TestResult:
    """Test result container."""
    
    def __init__(self, name):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def success(self, message=""):
        self.passed += 1
        log(f"  ✓ {message}")
    
    def failure(self, message=""):
        self.failed += 1
        self.errors.append(message)
        log(f"  ✗ {message}")
    
    def summary(self):
        total = self.passed + self.failed
        log(f"\n{self.name}: {self.passed}/{total} passed")
        if self.errors:
            log("Errors:")
            for error in self.errors:
                log(f"  - {error}")
        return self.failed == 0


def test_utils():
    """Test shared utilities."""
    log("\n=== Testing Utils ===")
    result = TestResult("Utils Tests")
    
    try:
        from utils import human, human_bytes, get_platform, is_windows, is_linux, is_macos
        result.success("Import utils")
    except Exception as e:
        result.failure(f"Import utils: {e}")
        return result
    
    # Test human()
    try:
        assert human(0) == "0 B"
        assert human(1024) == "1.0 MB"
        assert human(1048576) == "1.0 GB"
        assert human(1024 * 1024 * 1024) == "1.0 TB"
        result.success("human() function")
    except Exception as e:
        result.failure(f"human() function: {e}")
    
    # Test human_bytes()
    try:
        assert human_bytes(0) == "0 B"
        assert human_bytes(1024) == "1 KB"
        assert human_bytes(1024 * 1024) == "1.0 MB"
        result.success("human_bytes() function")
    except Exception as e:
        result.failure(f"human_bytes() function: {e}")
    
    # Test platform detection
    try:
        p = get_platform()
        assert p in ("windows", "macos", "linux")
        assert is_windows() == (p == "windows")
        assert is_linux() == (p == "linux")
        assert is_macos() == (p == "macos")
        result.success(f"Platform detection: {p}")
    except Exception as e:
        result.failure(f"Platform detection: {e}")
    
    # Test classify_file_type
    try:
        from utils import classify_file_type
        cat, label, tier = classify_file_type("test.mp4")
        assert cat == "video"
        cat, label, tier = classify_file_type("test.zip")
        assert cat == "archive"
        cat, label, tier = classify_file_type("test.xyz")
        assert cat == "other"
        result.success("classify_file_type()")
    except Exception as e:
        result.failure(f"classify_file_type(): {e}")
    
    # Test load_json / save_json
    try:
        from utils import load_json, save_json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        save_json(temp_path, {"test": "value"})
        data = load_json(temp_path)
        assert data["test"] == "value"
        os.unlink(temp_path)
        result.success("load_json() / save_json()")
    except Exception as e:
        result.failure(f"load_json() / save_json(): {e}")
    
    # Test get_disk_info
    try:
        from utils import get_disk_info
        disks = get_disk_info()
        assert isinstance(disks, list)
        assert len(disks) > 0
        assert "name" in disks[0]
        assert "total_h" in disks[0]
        result.success(f"get_disk_info() - {len(disks)} disks")
    except Exception as e:
        result.failure(f"get_disk_info(): {e}")
    
    # Test get_system_info
    try:
        from utils import get_system_info
        info = get_system_info()
        assert "os" in info
        assert "disks" in info
        result.success(f"get_system_info() - {info['os']}")
    except Exception as e:
        result.failure(f"get_system_info(): {e}")
    
    return result


def test_scan():
    """Test scanning functionality."""
    log("\n=== Testing Scan ===")
    result = TestResult("Scan Tests")
    
    try:
        import scan_hybrid
        result.success("Import scan_hybrid")
    except Exception as e:
        result.failure(f"Import scan_hybrid: {e}")
        return result
    
    try:
        from utils import human
        assert human(1024) == "1.0 MB"
        assert human(1048576) == "1.0 GB"
        result.success("human() function")
    except Exception as e:
        result.failure(f"human() function: {e}")
    
    try:
        from engine import szd
        size = szd(SCRIPTS_DIR, max_depth=2, timeout=5)
        assert size > 0
        result.success(f"engine.szd() - {size} bytes")
    except Exception as e:
        result.failure(f"engine.szd(): {e}")
    
    try:
        from utils import get_platform
        p = get_platform()
        result.success(f"Platform: {p}")
    except Exception as e:
        result.failure(f"Platform: {e}")
    
    return result


def test_classify():
    """Test classification functionality."""
    log("\n=== Testing Classify ===")
    result = TestResult("Classify Tests")
    
    try:
        import classify
        result.success("Import classify")
    except Exception as e:
        result.failure(f"Import classify: {e}")
        return result
    
    try:
        from engine import _classify_item as classify_item
        tier, reason, confidence = classify_item("Temp", "C:\\Temp", "temp", 1024)
        assert tier == "green"
        result.success(f"classify_item() green - {tier}: {reason}")
    except Exception as e:
        result.failure(f"classify_item() green: {e}")
    
    try:
        from engine import _classify_item as classify_item
        tier, reason, confidence = classify_item("Windows", "C:\\Windows\\System32", "program_files", 1024)
        assert tier == "red", f"Expected red, got {tier}"
        result.success(f"classify_item() red - {tier}: {reason}")
    except Exception as e:
        result.failure(f"classify_item() red: {e}")
    
    try:
        from engine import _classify_item as classify_item
        tier, reason, confidence = classify_item("Downloads", "C:\\Users\\test\\Downloads", "downloads", 1024)
        assert tier == "yellow"
        result.success(f"classify_item() yellow - {tier}: {reason}")
    except Exception as e:
        result.failure(f"classify_item() yellow: {e}")
    
    return result


def test_duplicates():
    """Test duplicate detection functionality."""
    log("\n=== Testing Duplicates ===")
    result = TestResult("Duplicates Tests")
    
    try:
        import duplicates
        result.success("Import duplicates")
    except Exception as e:
        result.failure(f"Import duplicates: {e}")
        return result
    
    try:
        from engine import _hash as file_hash
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_file = f.name
        
        hash_val = file_hash(temp_file)
        assert hash_val is not None
        assert len(hash_val) > 0
        
        # Same file should produce same hash
        hash_val2 = file_hash(temp_file)
        assert hash_val == hash_val2
        
        os.unlink(temp_file)
        result.success(f"file_hash() - {hash_val[:16]}...")
    except Exception as e:
        result.failure(f"file_hash(): {e}")
    
    try:
        # get_default_paths merged into engine.PP (plat_paths)
        from engine import PP
        assert isinstance(PP, dict)
        assert "home" in PP
        result.success(f"engine.PP plat_paths - {len(PP)} entries")
    except Exception as e:
        result.failure(f"engine.PP: {e}")
    
    return result


def test_recommend():
    """Test recommendation functionality."""
    log("\n=== Testing Recommend ===")
    result = TestResult("Recommend Tests")
    
    try:
        import recommend
        result.success("Import recommend")
    except Exception as e:
        result.failure(f"Import recommend: {e}")
        return result
    
    try:
        # get_suggestion merged into engine.gen_actions / _classify_item
        from engine import _classify_item as classify_item
        tier, reason, conf = classify_item("VMwarekail", "D:\\VMwarekail", "vm", 1048576)
        result.success(f"classify VMwarekail - {tier}: {reason}")
    except Exception as e:
        result.failure(f"classify VMwarekail: {e}")
    
    try:
        from engine import _classify_item as classify_item
        tier, reason, conf = classify_item("node_modules", "C:\\project\\node_modules", "dev", 500)
        result.success(f"classify node_modules - {tier}: {reason}")
    except Exception as e:
        result.failure(f"classify node_modules: {e}")
    
    return result


def test_config():
    """Test configuration - skipped (inlined in engine.py)."""
    log("\n=== Testing Config ===")
    result = TestResult("Config Tests")
    result.success("Config is now inline in engine.py (skipped)")
    return result

def test_report():
    """Test report generation functionality."""
    log("\n=== Testing Report ===")
    result = TestResult("Report Tests")
    
    try:
        import build_report
        result.success("Import build_report")
    except Exception as e:
        result.failure(f"Import build_report: {e}")
        return result
    
    try:
        template_file = os.path.join(PROJECT_DIR, "assets", "report_template_enhanced.html")
        assert os.path.exists(template_file)
        result.success(f"Template exists: {template_file}")
    except Exception as e:
        result.failure(f"Template exists: {e}")
    
    return result


def test_filetypes():
    """Test file type analyzer."""
    log("\n=== Testing File Types ===")
    result = TestResult("File Type Tests")
    
    try:
        import file_type_analyzer
        result.success("Import file_type_analyzer")
    except Exception as e:
        result.failure(f"Import file_type_analyzer: {e}")
        return result
    
    try:
        from file_type_analyzer import format_results
        test_cats = {
            "video": {"total_bytes": 1024*1024*100, "count": 5, "files": []},
            "image": {"total_bytes": 1024*1024*50, "count": 20, "files": []},
        }
        results = format_results(test_cats)
        assert len(results) == 2
        assert results[0]["category"] == "video"  # Sorted by size
        result.success("format_results()")
    except Exception as e:
        result.failure(f"format_results(): {e}")
    
    return result


def test_oldfiles():
    """Test old file detector."""
    log("\n=== Testing Old Files ===")
    result = TestResult("Old Files Tests")
    
    try:
        import old_files
        result.success("Import old_files")
    except Exception as e:
        result.failure(f"Import old_files: {e}")
        return result
    
    try:
        from old_files import generate_summary
        test_files = [
            {"name": "test1.zip", "size_bytes": 1024*1024*100, "age_days": 200, "category": "archive", "category_label": "压缩包"},
            {"name": "test2.mp4", "size_bytes": 1024*1024*200, "age_days": 400, "category": "video", "category_label": "视频"},
        ]
        summary = generate_summary(test_files)
        assert summary["total_files"] == 2
        assert summary["total_bytes"] == 1024*1024*300
        assert "6-12 months" in summary["by_age"]
        assert "1-2 years" in summary["by_age"]
        result.success("generate_summary()")
    except Exception as e:
        result.failure(f"generate_summary(): {e}")
    
    return result


def test_deep_scanner():
    """Test deep scanner - merged into engine.py."""
    log("\n=== Testing Deep Scanner ===")
    result = TestResult("Deep Scanner Tests")
    result.success("Deep scanner merged into engine.py (skipped)")
    return result


def test_audit_log():
    """Test audit log functionality."""
    log("\n=== Testing Audit Log ===")
    result = TestResult("Audit Log Tests")
    try:
        from engine import _audit_log, AUDIT_LOG, _ensure_cache_dir
        _ensure_cache_dir()
        _audit_log("TEST", "test/path", "test result", 1024)
        import os
        if os.path.exists(AUDIT_LOG):
            with open(AUDIT_LOG, 'r') as f:
                last_line = f.readlines()[-1]
            if "TEST" in last_line and "test/path" in last_line:
                result.success("Audit log writes correctly")
            else:
                result.failure(f"Audit log format unexpected: {last_line[:50]}")
        else:
            result.failure("Audit log file not created")
    except Exception as e:
        result.failure(f"Audit log: {e}")
    return result

def test_forecast():
    """Test forecast with history."""
    log("\n=== Testing Forecast ===")
    result = TestResult("Forecast Tests")
    try:
        from engine import forecast, _save_history, _load_history, _ensure_cache_dir
        _ensure_cache_dir()
        # Test basic forecast
        dd = {"C": {"p": 96}, "D": {"p": 86}}
        w = forecast(dd, use_history=False)
        crit = [x for x in w if x["lvl"] == "critical"]
        warn = [x for x in w if x["lvl"] == "warning"]
        if len(crit) == 1 and len(warn) == 1:
            result.success("Basic forecast thresholds")
        else:
            result.failure(f"Forecast thresholds: crit={len(crit)} warn={len(warn)}")
    except Exception as e:
        result.failure(f"Forecast: {e}")
    return result

def test_parallel_scan():
    """Test parallel scanning."""
    log("\n=== Testing Parallel Scan ===")
    result = TestResult("Parallel Scan Tests")
    try:
        from engine import scan_all, CFG
        workers = CFG.get("scan",{}).get("workers", 4)
        result.success(f"Workers config: {workers}")
        g = scan_all(use_cache=True)
        if isinstance(g, dict) and len(g) > 0:
            result.success(f"Parallel scan returned {len(g)} groups")
        else:
            result.failure("Parallel scan returned empty")
    except Exception as e:
        result.failure(f"Parallel scan: {e}")
    return result


def test_cleaners():
    """Test the new plugin-based cleaner pipeline."""
    log("\n=== Testing Cleaners (plugin pipeline) ===")
    result = TestResult("Cleaners Tests")
    try:
        from cleaners import REGISTRY, run_all, ScanContext
        result.success(f"REGISTRY has {len(REGISTRY)} cleaners")
    except Exception as e:
        result.failure(f"Import cleaners: {e}")
        return result

    try:
        from cleaners._base import Cleaner, Entry, ScanContext as SC
        # Spot-check abstract base
        assert Cleaner.name
        assert hasattr(Cleaner, "analyze")
        assert hasattr(Cleaner, "clean")
        result.success("Cleaner base class OK")
    except Exception as e:
        result.failure(f"Cleaner base: {e}")

    try:
        ctx = ScanContext.build()
        result.success(f"ScanContext built (home={ctx.home[:30]}...)")
    except Exception as e:
        result.failure(f"ScanContext.build: {e}")
        return result

    try:
        entries = run_all(ctx)
        if isinstance(entries, list) and len(entries) > 0:
            result.success(f"run_all() returned {len(entries)} entries")
            # Spot-check shape
            e = entries[0]
            assert hasattr(e, "name")
            assert hasattr(e, "path")
            assert hasattr(e, "size_kb")
            assert hasattr(e, "size_h")
            result.success(f"Entry shape OK: {e.name} {e.size_h}")
        else:
            result.failure(f"run_all() returned {len(entries)} entries (expected > 0)")
    except Exception as e:
        result.failure(f"run_all(): {e}")

    try:
        from engine import scan_sys_v2
        legacy_items = scan_sys_v2()
        if isinstance(legacy_items, list):
            result.success(f"scan_sys_v2() returned {len(legacy_items)} legacy items")
            if legacy_items:
                first = legacy_items[0]
                for key in ("n", "p", "k", "h", "safe", "reason", "risk", "prio", "cat"):
                    assert key in first, f"missing key {key} in legacy item"
                result.success("Legacy item shape OK")
        else:
            result.failure("scan_sys_v2() did not return a list")
    except Exception as e:
        result.failure(f"scan_sys_v2: {e}")

    try:
        from engine.classify.ai_judge import NullJudge, BaseJudge, Verdict
        j = NullJudge()
        v = j.judge({"tier": "yellow", "reason": "test"})
        assert v.tier == "yellow"
        assert v.model == "null"
        result.success(f"NullJudge works: tier={v.tier}")
    except Exception as e:
        result.failure(f"NullJudge: {e}")

    return result

def run_all_tests():
    """Run all tests."""
    log("Running all tests...")
    
    results = []
    results.append(test_utils())
    results.append(test_scan())
    results.append(test_classify())
    results.append(test_duplicates())
    results.append(test_recommend())
    results.append(test_config())
    results.append(test_report())
    results.append(test_filetypes())
    results.append(test_oldfiles())
    results.append(test_deep_scanner())
    results.append(test_audit_log())
    results.append(test_forecast())
    results.append(test_parallel_scan())
    results.append(test_cleaners())
    
    log("\n" + "=" * 60)
    log("Test Summary")
    log("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    for result in results:
        result.summary()
        total_passed += result.passed
        total_failed += result.failed
    
    log(f"\nTotal: {total_passed}/{total_passed + total_failed} passed")
    
    if total_failed == 0:
        log("\n✓ All tests passed!")
        return 0
    else:
        log(f"\n✗ {total_failed} tests failed!")
        return 1


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test framework")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--scan", action="store_true", help="Test scan functionality")
    parser.add_argument("--classify", action="store_true", help="Test classify functionality")
    parser.add_argument("--duplicates", action="store_true", help="Test duplicates functionality")
    parser.add_argument("--recommend", action="store_true", help="Test recommend functionality")
    parser.add_argument("--config", action="store_true", help="Test config functionality")
    parser.add_argument("--report", action="store_true", help="Test report functionality")
    parser.add_argument("--utils", action="store_true", help="Test utils functionality")
    parser.add_argument("--filetypes", action="store_true", help="Test file type analyzer")
    parser.add_argument("--oldfiles", action="store_true", help="Test old file detector")
    parser.add_argument("--deep", action="store_true", help="Test deep scanner")
    args = parser.parse_args()
    
    if args.all or not any([args.scan, args.classify, args.duplicates, args.recommend,
                           args.config, args.report, args.utils, args.filetypes, args.oldfiles]):
        return run_all_tests()
    
    results = []
    
    if args.utils:
        results.append(test_utils())
    if args.scan:
        results.append(test_scan())
    if args.classify:
        results.append(test_classify())
    if args.duplicates:
        results.append(test_duplicates())
    if args.recommend:
        results.append(test_recommend())
    if args.config:
        results.append(test_config())
    if args.report:
        results.append(test_report())
    if args.filetypes:
        results.append(test_filetypes())
    if args.oldfiles:
        results.append(test_oldfiles())
    if args.deep:
        results.append(test_deep_scanner())
    results.append(test_audit_log())
    results.append(test_forecast())
    results.append(test_parallel_scan())
    if args.oldfiles:
        results.append(test_oldfiles())
    results.append(test_deep_scanner())
    results.append(test_audit_log())
    results.append(test_forecast())
    results.append(test_parallel_scan())
    
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    
    log(f"\nTotal: {total_passed}/{total_passed + total_failed} passed")
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


