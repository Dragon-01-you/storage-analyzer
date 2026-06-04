"""VMware Workstation / Player VM cleaner.

Detects VMs in common locations and reports what could be:
  - removed (.lck dirs, log files)   -- safe, can auto-clean
  - merged (snapshot chains)         -- requires VMware UI / downtime
  - compacted (vmdk shrink)          -- requires VMware CLI or UI

By default, only [A] .lck + [B] .log are auto-cleaned (risk = 0).
Snapshot compaction is REPORTED, never auto-done.

Enable with config:
  {
    "vmware": {
      "auto_clean_locks": true,   // delete .lck if VM not running
      "auto_clean_logs":  true,   // delete vmware-*.log
      "scan_paths": ["E:\\kali", "D:\\VMs", ...]
    }
  }
"""
from __future__ import annotations
import os
import glob
from collections import defaultdict
from typing import List, Dict, Any

from ._base import Cleaner, Entry, ScanContext
from engine.utils import hk


def _vm_size(path: str) -> int:
    """Get the apparent (allocated) size of a VM directory."""
    total = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _analyze_vm(vm_dir: str) -> Dict[str, Any]:
    """Inspect a VMware VM dir, return a structured report."""
    out = {
        "path": vm_dir,
        "vmdk_bytes": 0,
        "vmem_bytes": 0,
        "vmsn_bytes": 0,
        "lck_count": 0,
        "log_bytes": 0,
        "vmdk_files": 0,
        "snapshots": [],     # [{base, files, total_bytes}]
        "total_bytes": 0,
    }
    if not os.path.isdir(vm_dir):
        return out

    lck_dirs = glob.glob(os.path.join(vm_dir, "*.lck"))
    out["lck_count"] = len(lck_dirs)

    vmdk_groups = defaultdict(list)
    for entry in os.listdir(vm_dir):
        full = os.path.join(vm_dir, entry)
        try:
            if os.path.isfile(full):
                sz = os.path.getsize(full)
                if entry.endswith(".vmdk"):
                    out["vmdk_bytes"] += sz
                    out["vmdk_files"] += 1
                    base = entry[:-5]
                    for sep in ("-s", "-0"):
                        if sep in base:
                            base = base.split(sep)[0]
                            break
                    vmdk_groups[base].append(sz)
                elif entry.endswith(".vmem"):
                    out["vmem_bytes"] += sz
                elif entry.endswith(".vmsn"):
                    out["vmsn_bytes"] += sz
                elif entry.startswith("vmware") and entry.endswith(".log"):
                    out["log_bytes"] += sz
        except OSError:
            pass

    for base, sizes in sorted(vmdk_groups.items()):
        out["snapshots"].append({
            "base": base, "files": len(sizes), "bytes": sum(sizes),
        })

    out["total_bytes"] = (
        out["vmdk_bytes"] + out["vmem_bytes"] + out["vmsn_bytes"] + out["log_bytes"]
    )
    return out


def _scan_default_paths() -> List[str]:
    """Default VMware VM locations to scan."""
    candidates = []
    if os.name == "nt":
        for drv in ("C:", "D:", "E:", "F:"):
            for sub in ("Virtual Machines", "VMs", "vm", "VMware",
                        "kali", "ubuntu", "debian", "centos", "fedora",
                        "arch", "manjaro", "opensuse", "alpine"):
                p = os.path.join(drv + "\\", sub)
                if os.path.isdir(p):
                    candidates.append(p)
            # Also scan the root of each drive for *.vmx files
            for entry in _safe_listdir(drv + "\\"):
                p = os.path.join(drv + "\\", entry)
                if os.path.isfile(os.path.join(p, entry + ".vmx")):
                    candidates.append(p)
    return candidates


def _safe_listdir(p: str) -> List[str]:
    try:
        return os.listdir(p)
    except OSError:
        return []


# ---------------------------------------------------------------------------
# VMware CLI detection
# ---------------------------------------------------------------------------

_VMTOOL_CANDIDATES_WIN = [
    r"C:\Program Files (x86)\VMware\VMware Workstation\vmware-vdiskmanager.exe",
    r"C:\Program Files\VMware\VMware Workstation\vmware-vdiskmanager.exe",
    r"C:\Program Files (x86)\VMware\VMware Player\vmware-vdiskmanager.exe",
    r"C:\Program Files\VMware\VMware Player\vmware-vdiskmanager.exe",
]
_VMTOOL_CANDIDATES_NIX = [
    "/usr/bin/vmware-vdiskmanager",
    "/usr/local/bin/vmware-vdiskmanager",
    "/opt/vmware/workstation/bin/vmware-vdiskmanager",
]


def find_vmware_cli() -> str:
    """Return path to vmware-vdiskmanager or '' if not found."""
    import shutil
    in_path = shutil.which("vmware-vdiskmanager")
    if in_path:
        return in_path
    candidates = _VMTOOL_CANDIDATES_WIN if os.name == "nt" else _VMTOOL_CANDIDATES_NIX
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ""


def vmware_shrink_command(vmdk_path: str, vmware_cli: str = None) -> list:
    """Build the command line to shrink a vmdk in place.

    Caller must ensure:
      - VM is shut down
      - Guest OS has zeroed free space (dd if=/dev/zero of=/zerofile; rm /zerofile)
    """
    cli = vmware_cli or find_vmware_cli()
    if not cli:
        return []
    return [cli, "-k", vmdk_path]


def find_vmware_vdiskmanager() -> str:
    """Locate vmware-vdiskmanager.exe on this host. Returns "" if missing."""
    candidates = []
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files (x86)")
        candidates += [
            os.path.join(pf, "VMware", "VMware Workstation", "vmware-vdiskmanager.exe"),
            os.path.join(pf, "VMware", "VMware Player", "vmware-vdiskmanager.exe"),
        ]
    else:
        candidates += [
            "/usr/bin/vmware-vdiskmanager",
            "/usr/local/bin/vmware-vdiskmanager",
            "/Applications/VMware Fusion.app/Contents/Library/vmware-vdiskmanager",
        ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return ""


def get_vmware_version(vdiskmanager_path: str) -> str:
    """Try to get the version string. Returns "" on failure."""
    if not vdiskmanager_path:
        return ""
    try:
        import subprocess
        r = subprocess.run(
            [vdiskmanager_path, "-v"],
            capture_output=True, text=True, timeout=5,
        )
        # Output like "vmware-vdiskmanager version 12.0.0 build-12345"
        return (r.stdout or r.stderr).strip().splitlines()[-1] if r.stdout or r.stderr else ""
    except Exception:
        return ""


class VMwareCleaner(Cleaner):
    name = "vmware-vm"
    platforms = ("windows", "macos", "linux")
    risk_level = "med"  # only because snapshot merging is dangerous
    description = "VMware Workstation / Player VMs (snapshots, locks, logs)"

    def analyze(self, ctx: ScanContext) -> List[Entry]:
        # Decide which paths to scan
        cfg = ctx.config.get("vmware", {}) if ctx.config else {}
        scan_paths = cfg.get("scan_paths") or _scan_default_paths()
        # Auto-add the path from PP["vm"] if present
        if ctx.pp.get("vm"):
            scan_paths.append(ctx.pp["vm"])

        # Detect VMware CLI for the "next step" advisory
        vmware_cli = find_vmware_cli()

        out: List[Entry] = []
        for vm_dir in scan_paths:
            if not os.path.isdir(vm_dir):
                continue
            report = _analyze_vm(vm_dir)
            if report["total_bytes"] == 0:
                continue

            snapshots = report["snapshots"]
            non_base = [s for s in snapshots if "-0" in s["base"]]
            non_base_bytes = sum(s["bytes"] for s in non_base)
            base_bytes = sum(s["bytes"] for s in snapshots) - non_base_bytes

            # Compose a single "review" entry per VM with full breakdown
            extra = {
                "vmware_report": report,
                "snapshot_merge_bytes": non_base_bytes,
                "log_bytes": report["log_bytes"],
                "lck_count": report["lck_count"],
                "vmware_cli": vmware_cli,
            }
            reason = (
                f"VM {os.path.basename(vm_dir)}: "
                f"base {hk(base_bytes // 1024)}, "
                f"{len(non_base)} snapshots ({hk(non_base_bytes // 1024)}), "
                f"vmem {hk(report['vmem_bytes'] // 1024)}"
                + (f"  [cli: {vmware_cli}]" if vmware_cli else "  [vmware-vdiskmanager NOT FOUND]")
            )
            out.append(Entry(
                name=os.path.basename(vm_dir) or vm_dir,
                path=vm_dir,
                size_kb=report["total_bytes"] // 1024,
                size_h=hk(report["total_bytes"] // 1024),
                reason=reason,
                risk="med",
                prio=3,
                cat="vm",
                safe=False,           # never auto-delete a whole VM
                extra=extra,
            ))
        return out

    def clean(self, entries: List[Entry], mode: str = "dry-run") -> "Result":
        """VM 'cleaning' is advisory only: report what could be merged,
        do NOT auto-delete snapshots. We only auto-clean .lck and .log
        if the user opted in via config (vmware.auto_clean_locks/logs).
        """
        from ._base import Result
        result = Result(ok=True)

        # Read opt-in flags from default config (best-effort)
        try:
            from engine.utils import CFG
            cfg = (CFG or {}).get("vmware", {}) or {}
        except Exception:
            cfg = {}
        clean_locks = bool(cfg.get("auto_clean_locks", False))
        clean_logs = bool(cfg.get("auto_clean_logs", False))

        for e in entries:
            report = e.extra.get("vmware_report", {})

            # .lck cleanup (only if VM is not running - we can't know from here)
            if clean_locks and report.get("lck_count", 0) > 0:
                import glob
                for d in glob.glob(os.path.join(e.path, "*.lck")):
                    if mode == "dry-run":
                        result.notes.append(f"[dry-run] would remove lock dir: {d}")
                    else:
                        try:
                            import shutil
                            shutil.rmtree(d, ignore_errors=True)
                            result.deleted += 1
                        except Exception as ex:
                            result.failed += 1
                            result.notes.append(f"failed {d}: {ex}")

            # .log cleanup
            if clean_logs and report.get("log_bytes", 0) > 0:
                for f in glob.glob(os.path.join(e.path, "vmware*.log")):
                    if mode == "dry-run":
                        result.notes.append(f"[dry-run] would remove log: {f}")
                    else:
                        try:
                            os.remove(f)
                            result.deleted += 1
                        except Exception as ex:
                            result.failed += 1
                            result.notes.append(f"failed {f}: {ex}")

            # Snapshot merge: NEVER auto-do, only advise
            merge_bytes = e.extra.get("snapshot_merge_bytes", 0)
            if merge_bytes > 0:
                result.notes.append(
                    f"[advisory] {e.name}: merge {len([s for s in report.get('snapshots', []) if '-0' in s['base']])} "
                    f"snapshots in VMware UI to free {hk(merge_bytes // 1024)} (requires VM shutdown)"
                )
                result.skipped += 1

            # Compact: only if we found vmware-vdiskmanager and user opted in
            vd = e.extra.get("vdiskmanager", "")
            if vd and mode == "execute":
                # Find the active vmdk (base, not a snapshot delta)
                active = None
                for f in os.listdir(e.path):
                    if f.endswith(".vmdk") and "-0" not in f and "-s" not in f:
                        active = os.path.join(e.path, f)
                        break
                if active:
                    result.notes.append(
                        f"[advisory] run to compact: \"{vd}\" -k \"{active}\"  "
                        f"(VM must be shut down; 0-byte VM first via dd)"
                    )
        return result
