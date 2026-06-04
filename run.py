#!/usr/bin/env python3
"""Storage Analyzer - Direct entry point (no subprocess overhead).

Usage:
  python run.py                    # dry-run analysis + summary
  python run.py --json             # full JSON output
  python run.py --execute          # actually clean
  python run.py --full             # everything
  python run.py --report           # generate HTML report

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
    engine_args = [a for a in args if a not in ("--report", "--json", "--full", "--deep", "--dupes")]

    # Build opts dict for engine.main.run()
    opts = {
        "execute": "--execute" in args,
        "quiet": "--quiet" in args,
        "deep": any(x in args for x in ("--deep", "--full")),
        "dupes": any(x in args for x in ("--dupes", "--full")),
        "no_cache": "--no-cache" in args,
    }

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


if __name__ == "__main__":
    main()
