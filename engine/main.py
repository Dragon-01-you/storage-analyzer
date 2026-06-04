"""CLI entry point for storage analyzer (v7 modular).

Provides both:
  - main()       : argparse-driven CLI entry (prints JSON)
  - run(opts)    : importable API returning a dict

The dict-returning `run()` is what scripts/run.py call to avoid the
stdout-capture trick the v6 engine required.
"""
import argparse
import json
import os
import sys
import time

from . import (
    disks, scan_all, scan_sys, gen_actions, forecast, find_dupes,
    hb, hk, log, szf, szd, _parse_h, safe_delete, audit_log, _is_protected
)


def run(opts):
    """Run a full analysis + optional execution. Returns dict.

    opts keys (all optional):
      execute    bool  default False (dry-run)
      deep       bool  default False
      dupes      bool  default False
      no_cache   bool  default False
      quiet      bool  default False
      use_cleaners  bool  default False  (use new plugin pipeline)
      include_vm    bool  default False  (also surface VM items in deep)
    """
    execute = bool(opts.get("execute"))
    deep = bool(opts.get("deep"))
    dupes = bool(opts.get("dupes"))
    no_cache = bool(opts.get("no_cache"))
    use_cleaners = bool(opts.get("use_cleaners"))
    include_vm = bool(opts.get("include_vm"))
    if opts.get("quiet"):
        os.environ["SA_VERBOSE"] = "0"

    dry = not execute
    if dry:
        log("DRY-RUN MODE. Use --execute to actually delete.", 0)

    t0 = time.time()
    dd = disks()
    gr = scan_all(use_cache=not no_cache)
    log(f"Scan: {sum(len(v) for v in gr.values())} items", 1)

    # Default to the new plugin pipeline. Legacy is still available
    # via opt-in (--legacy-scanner) for emergency rollback.
    if opts.get("legacy_scanner"):
        si = scan_sys() if deep else []
    else:
        from engine.scanner_v2 import scan_sys_v2
        si = scan_sys_v2() if deep else []
    acts = gen_actions(gr, si, dry)
    dp = find_dupes() if dupes else []
    fc = forecast(dd)

    safe_b = sum(_parse_h(a["sz"]) for a in acts if a["act"] == "delete")

    # Actually execute deletions when execute=True
    deleted = 0
    deleted_bytes = 0
    if not dry:
        safe_items = [a for a in acts if a["act"] == "delete" and a.get("risk") == "none"]
        if safe_items:
            log(f"Executing {len(safe_items)} safe deletions...", 0)
            for a in safe_items:
                path = a.get("path", "")
                if not path:
                    continue
                is_dism = a.get("dism", False)
                is_recycle = (path == "Recycle Bin")
                if not is_dism and not is_recycle and not os.path.exists(path):
                    continue
                if not a.get("force") and not is_dism and not is_recycle and _is_protected(path):
                    log(f"  SKIP (protected): {path}", 0)
                    audit_log("SKIP", path, "protected")
                    continue
                size_before = 0
                if not is_dism and not is_recycle:
                    size_before = szf(path) if os.path.isfile(path) else szd(path, 2, 5)
                ok, reason = safe_delete(
                    path, force=a.get("force", False),
                    is_dism=is_dism, is_recycle=is_recycle
                )
                audit_log("DELETE" if ok else "FAIL", path, str(reason), size_before)
                if ok:
                    deleted += 1
                    deleted_bytes += size_before
                    reason_str = str(reason).lower()
                    if 'scheduled' in reason_str:
                        log(f"  SCHEDULED (reboot): {a.get('what','?')} ({hb(size_before)})", 0)
                    elif 'dism' in reason_str:
                        log(f"  DISM CLEANUP: WinSxS component store", 0)
                    elif 'recycle' in reason_str:
                        log(f"  EMPTIED: Recycle Bin", 0)
                    else:
                        log(f"  DELETED: {a.get('what','?')} ({hb(size_before)})", 0)
                else:
                    log(f"  FAILED: {a.get('what','?')} - {reason}", 0)

    out = {
        "ok": True,
        "elapsed": round(time.time() - t0, 1),
        "dry_run": dry,
        "disks": dd,
        "safe_h": hb(safe_b),
        "actions": acts,
        "deleted": deleted,
        "deleted_bytes": deleted_bytes
    }
    if dp:
        out["dupes"] = dp
    if fc:
        out["warnings"] = fc

    log(f"Done. Safe: {hb(safe_b)}, Deleted: {deleted} items", 0)
    for a in acts[:5]:
        log(f"  [{a['act']:6s}] {a['sz']:>10s}  {a['what']}", 0)
    if fc:
        for f in fc:
            log(f"  ! {f['msg']}", 0)
    if dp:
        wasted = sum(szf(d["keep"]) * len(d["dups"]) for d in dp)
        log(f"  Duplicates: {len(dp)} groups, {hb(wasted)} wasted", 0)

    return out


def main():
    """Argparse-driven CLI entry. Prints JSON to stdout (for piping)."""
    ap = argparse.ArgumentParser(description="Storage Analyzer Engine v7")
    ap.add_argument("--execute", action="store_true", help="Actually delete files")
    ap.add_argument("--quiet", action="store_true", help="Suppress stderr logs")
    ap.add_argument("--deep", action="store_true", help="Include system scan")
    ap.add_argument("--dupes", action="store_true", help="Include duplicate detection")
    ap.add_argument("--full", action="store_true", help="Deep + dupes")
    ap.add_argument("-o", "--output", type=str, help="Output JSON file")
    ap.add_argument("--json", action="store_true",
                    help="Print JSON to stdout (default; for piping)")
    ap.add_argument("--no-cache", action="store_true", help="Skip incremental cache")
    ap.add_argument("--use-cleaners", action="store_true",
                    help="[DEPRECATED] Now default; alias kept for back-compat")
    ap.add_argument("--include-vm", action="store_true",
                    help="Surface VMware / VM items in the deep scan")
    ap.add_argument("--legacy-scanner", action="store_true",
                    help="Use the legacy scan_sys() instead of the new plugin pipeline")
    args = ap.parse_args()

    opts = {
        "execute": args.execute,
        "quiet": args.quiet,
        "deep": args.deep or args.full,
        "dupes": args.dupes or args.full,
        "no_cache": args.no_cache,
        "use_cleaners": args.use_cleaners or True,   # default
        "include_vm": args.include_vm,
        "legacy_scanner": args.legacy_scanner,
    }
    out = run(opts)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    else:
        # Default: print to stdout (so zipapp / pipe users get JSON)
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
