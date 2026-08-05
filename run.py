#!/usr/bin/env python3
"""Storage Analyzer v9.0 - Direct entry point (no subprocess overhead).

Usage:
  python run.py                    # dry-run analysis + summary
  python run.py --json             # full JSON output
  python run.py --execute          # actually clean
  python run.py --full             # everything
  python run.py --report           # generate HTML report
  python run.py --confidence       # 4-tier confidence analysis
  python run.py --similar          # find similar/duplicate files
  python run.py --corrupted        # detect corrupted files
  python run.py --piracy           # detect piracy-related files
  python run.py --tui              # interactive TUI
  python run.py --plan             # manage cleanup plans
  python run.py --migrate          # migration analysis
  python run.py --friendly         # user-friendly output (通俗易懂版)

This version imports the v7 modular `engine/` package directly.
The legacy top-level `engine.py` is no longer used.
"""
import sys, os, webbrowser, json, time, io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def _summary(out: dict) -> str:
    """Compact human-readable summary."""
    lines = []
    lines.append(f"=== Storage Analyzer v7 | {time.strftime('%Y-%m-%d %H:%M')} ===")
    lines.append(f"Mode: {'DRY-RUN' if out.get('dry_run') else 'EXECUTE'} | {out.get('elapsed',0)}s")

    # Disks
    lines.append("")
    lines.append("--- Drives ---")
    for label, d in out.get("disks", {}).items():
        pct = d["p"]
        bar = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
        lines.append(f"  {label}: [{bar}] {pct}%  {d['uh']}/{d['th']}")

    # Actions
    acts = out.get("actions", [])
    if acts:
        lines.append("")
        lines.append(f"--- Cleanable: {out.get('safe_h','0')} safe to reclaim ---")
        for a in acts[:12]:
            icon = {"delete": "[X]", "review": "[?]", "keep": "[OK]"}.get(a.get("act",""), "[?]")
            lines.append(f"  {icon} [{a.get('risk','?')}] {a.get('sz','?'):>8s}  {a.get('what','?')}")
        if len(acts) > 12:
            lines.append(f"  ... +{len(acts)-12} more (use --json for full)")

    # Dupes
    dupes = out.get("dupes", [])
    if dupes:
        lines.append("")
        lines.append(f"--- Duplicates: {len(dupes)} groups ---")
        for d in dupes[:5]:
            lines.append(f"  {d.get('keep','?')[:60]} (+{d.get('cnt',2)-1} copies)")

    # Warnings
    warns = out.get("warnings", [])
    if warns:
        lines.append("")
        lines.append("--- WARNINGS ---")
        for w in warns:
            lines.append(f"  [{w['lvl']}] {w['msg']}")

    lines.append("")
    lines.append("Run with --execute to clean, --json for full output.")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    do_report = "--report" in args
    do_json = "--json" in args
    do_confidence = "--confidence" in args
    do_similar = "--similar" in args
    do_corrupted = "--corrupted" in args
    do_piracy = "--piracy" in args
    do_tui = "--tui" in args
    do_plan = "--plan" in args
    do_migrate = "--migrate" in args
    do_friendly = "--friendly" in args
    engine_args = [a for a in args if a not in ("--report", "--json", "--full", "--deep", "--dupes",
                                                 "--confidence", "--similar", "--corrupted", "--piracy",
                                                 "--tui", "--plan", "--migrate", "--friendly")]

    # Build opts dict for engine.main.run()
    opts = {
        "execute": "--execute" in args,
        "quiet": "--quiet" in args,
        "deep": any(x in args for x in ("--deep", "--full")),
        "dupes": any(x in args for x in ("--dupes", "--full")),
        "no_cache": "--no-cache" in args,
    }

    # Handle new features
    if do_confidence:
        _run_confidence_analysis()
        return

    if do_similar:
        _run_similar_analysis()
        return

    if do_corrupted:
        _run_corrupted_detection()
        return

    if do_piracy:
        _run_piracy_detection()
        return

    if do_tui:
        _run_tui()
        return

    if do_plan:
        _run_plan_management()
        return

    if do_migrate:
        _run_migration_analysis()
        return

    if do_friendly:
        _run_friendly_scan()
        return

    # Direct import - no stdout-capture trick needed anymore
    from engine.main import run
    data = run(opts)

    if do_report:
        import tempfile, datetime, subprocess
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(tempfile.gettempdir(), f"storage-report_{ts}.html")
        tmp_json = os.path.join(tempfile.gettempdir(), "sa_report_data.json")
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        subprocess.run([sys.executable, os.path.join(HERE, "scripts", "build_report.py"),
                        tmp_json, report_path])
        print(f"\nReport: {report_path}")
        webbrowser.open("file://" + report_path)
    elif do_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(_summary(data))


def _run_confidence_analysis():
    """Run 4-tier confidence analysis."""
    from v8.confidence_tiers import ConfidenceAnalyzer
    import json

    analyzer = ConfidenceAnalyzer()
    home = os.path.expanduser("~")

    print("=== 4-Tier Confidence Analysis ===")
    print(f"Scanning: {home}")
    print()

    # Analyze Downloads directory
    downloads = os.path.join(home, "Downloads")
    if os.path.exists(downloads):
        entries = analyzer.analyze_directory(downloads)
        summary = analyzer.get_summary(entries)

        print(f"Downloads: {len(entries)} files")
        print(f"  [SAFE]       {summary['tiers']['safe']['count']:>5} files  {_human_bytes(summary['tiers']['safe']['bytes'])}")
        print(f"  [REC]        {summary['tiers']['recommended']['count']:>5} files  {_human_bytes(summary['tiers']['recommended']['bytes'])}")
        print(f"  [SUG]        {summary['tiers']['suggested']['count']:>5} files  {_human_bytes(summary['tiers']['suggested']['bytes'])}")
        print(f"  [ASK]        {summary['tiers']['ask']['count']:>5} files  {_human_bytes(summary['tiers']['ask']['bytes'])}")
        print()

        # Show top items
        print("Top 10 largest:")
        entries.sort(key=lambda e: e.size_bytes, reverse=True)
        for e in entries[:10]:
            print(f"  {e.tier_emoji} {e.size_human:>10}  {e.name}")
    else:
        print("Downloads directory not found")


def _run_similar_analysis():
    """Run similar file analysis."""
    from v8.similar_files import SimilarFileAnalyzer
    import json

    analyzer = SimilarFileAnalyzer(min_size_mb=1)
    home = os.path.expanduser("~")
    paths = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Documents"),
    ]

    print("=== Similar File Analysis ===")
    print(f"Scanning: {', '.join(paths)}")
    print()

    results = analyzer.analyze(paths)
    summary = results['summary']

    print(f"Duplicates: {summary['duplicate_groups']} groups, {summary['duplicate_files']} files")
    print(f"  Wasted space: {_human_bytes(summary['duplicate_wasted'])}")
    print(f"Corrupted: {summary['corrupted_files']} files")
    print(f"Wrong extensions: {summary['wrong_extensions']} files")
    print()

    # Show top duplicates
    if results['duplicates']:
        print("Top 5 duplicate groups:")
        for group in results['duplicates'][:5]:
            print(f"  {group.count} copies, {_human_bytes(group.wasted_bytes)} wasted")
            for f in group.files[:3]:
                print(f"    {f}")
            if group.count > 3:
                print(f"    ... +{group.count - 3} more")


def _run_corrupted_detection():
    """Run corrupted file detection."""
    from v8.similar_files import CorruptedFileDetector

    detector = CorruptedFileDetector()
    home = os.path.expanduser("~")
    paths = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Documents"),
    ]

    print("=== Corrupted File Detection ===")
    print(f"Scanning: {', '.join(paths)}")
    print()

    corrupted = detector.detect(paths)
    print(f"Found {len(corrupted)} corrupted files")
    print()

    for c in corrupted[:20]:
        print(f"  {c.path}")
        print(f"    Reason: {c.reason}")


def _run_piracy_detection():
    """Run piracy detection."""
    from v8.confidence_tiers import PiracyDetector

    detector = PiracyDetector()
    home = os.path.expanduser("~")
    paths = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
    ]

    print("=== Piracy Detection ===")
    print(f"Scanning: {', '.join(paths)}")
    print()

    piracy_files = []
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    result = detector.detect(fp)
                    if result:
                        piracy_files.append(result)
        except OSError:
            continue

    print(f"Found {len(piracy_files)} potential piracy files")
    print()

    for p in piracy_files:
        print(f"  {p.path}")
        print(f"    {p.reason}")


def _run_tui():
    """Run interactive TUI."""
    from v8.interactive_tui import run_tui
    run_tui()


def _run_plan_management():
    """Run plan management."""
    from v8.cleanup_plan import PlanManager

    manager = PlanManager()
    plans = manager.list_plans()

    if not plans:
        print("No saved plans found.")
        print("Run a scan first to create a plan.")
        return

    print("=== Saved Plans ===\n")
    for i, plan in enumerate(plans):
        print(f"  [{i}] {plan['plan_id']} - {plan['item_count']} items ({_human_bytes(plan['total_bytes'])})")
        print(f"      Created: {plan['created_at']}")

    print("\nOptions:")
    print("  [0-9] View plan details")
    print("  [d] Delete plan")
    print("  [q] Quit")

    choice = input("\nSelect: ").strip().lower()

    if choice.isdigit():
        idx = int(choice)
        if 0 <= idx < len(plans):
            plan = manager.load_plan(plans[idx]['plan_id'])
            if plan:
                print("\n" + manager.get_plan_summary(plan))
                input("\nPress Enter to continue...")


def _run_migration_analysis():
    """Run migration analysis."""
    from v8.cleanup_plan import MigrationPlanner

    planner = MigrationPlanner()

    print("=== Migration Analysis ===\n")
    print("Analyzing what can be migrated from C: to D:...\n")

    results = planner.analyze_migration('C:', 'D:')

    print(f"Found {len(results['migratable'])} directories to migrate")
    print(f"Total size: {_human_bytes(results['total_bytes'])}")
    print()

    for item in results['migratable']:
        print(f"  {item['name']}: {_human_bytes(item['size_bytes'])}")
        print(f"    {item['description']}")
        print(f"    From: {item['path']}")
        print(f"    To:   {item['target']}")
        print()

    if results['migratable']:
        save = input("Save migration script? (y/n): ").strip().lower()
        if save == 'y':
            script = planner.create_migration_plan(results['migratable'])
            filepath = os.path.join(os.path.expanduser('~'), 'migration_plan.bat')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(script)
            print(f"Migration script saved: {filepath}")
            print("WARNING: Review the script before running!")


def _run_friendly_scan():
    """Run user-friendly scan with drive and mode selection."""
    from v8.user_friendly_output import format_drive_selector, format_cleanup_mode, format_user_friendly

    # Step 1: 选择磁盘
    print(format_drive_selector())
    drive_choice = input().strip()

    drives = {
        '1': ['C:\\'],
        '2': ['D:\\'],
        '3': ['E:\\'],
        '4': ['C:\\', 'D:\\', 'E:\\'],
    }

    selected_drives = drives.get(drive_choice, ['C:\\'])
    print(f"\nSelected: {', '.join(selected_drives)}")
    print()

    # Step 2: 选择清理方式
    print(format_cleanup_mode())
    mode_choice = input().strip()

    modes = {
        '1': 'safe',      # 只清理安全项
        '2': 'standard',  # 安全项 + 需要确认的项
        '3': 'deep',      # 所有项
        '4': 'custom',    # 自定义
    }

    selected_mode = modes.get(mode_choice, 'safe')
    print(f"\nSelected: {selected_mode}")
    print()

    # Step 3: 扫描
    print("Scanning... Please wait.")
    print()

    # 运行扫描
    from engine.main import run
    opts = {
        'execute': False,
        'quiet': True,
        'deep': True,
        'dupes': False,
        'no_cache': False,
    }
    data = run(opts)
    actions = data.get('actions', [])

    # Step 4: 展示结果（通俗易懂版）
    print(format_user_friendly(actions))

    # Step 5: 询问是否清理
    print("=" * 60)
    print("要执行清理吗？")
    print("=" * 60)
    print()
    print("  [1] 清理所有安全项")
    print("  [2] 清理选中的项")
    print("  [3] 不清理，退出")
    print()
    print("请选择 (1-3): ")

    clean_choice = input().strip()

    if clean_choice == '1':
        print("\nCleaning safe items...")
        opts['execute'] = True
        data = run(opts)
        print(f"\nDone! Freed: {data.get('freed_h', '0')}")
    elif clean_choice == '2':
        print("\nCustom cleanup not implemented yet.")
        print("Please use --execute with specific items.")
    else:
        print("\nNo cleanup performed.")


def _human_bytes(b: int) -> str:
    """Convert bytes to human-readable string."""
    if b == 0:
        return "0B"
    n = float(b)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f}{u}" if n < 100 else f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"


if __name__ == "__main__":
    main()
