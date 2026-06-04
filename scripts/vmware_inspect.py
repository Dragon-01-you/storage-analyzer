"""Inspect a VMware VM directory and surface consolidation opportunities."""
import os
import sys
from collections import defaultdict
from pathlib import Path


def fmt_size(n: int) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f}{u}" if n >= 100 else f"{n:.0f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


def main(vm_dir: str):
    vm_dir = Path(vm_dir)
    if not vm_dir.is_dir():
        print(f"NOT A DIRECTORY: {vm_dir}")
        sys.exit(1)

    print(f"=== VMware VM inspection: {vm_dir} ===\n")

    # Bucket files by category
    vmdk_total = 0
    vmdk_files = []
    snap_vmem = []
    snap_vmsn = []
    lck_dirs = []
    log_files = []
    other = []

    for p in vm_dir.iterdir():
        name = p.name
        if p.is_dir():
            if name.endswith(".lck"):
                lck_dirs.append(p)
            else:
                other.append((p, "dir"))
            continue
        sz = p.stat().st_size
        if name.endswith(".vmdk"):
            vmdk_files.append((p, sz))
            vmdk_total += sz
        elif name.endswith(".vmem"):
            snap_vmem.append((p, sz))
        elif name.endswith(".vmsn"):
            snap_vmsn.append((p, sz))
        elif name.startswith("vmware") and name.endswith(".log"):
            log_files.append((p, sz))
        else:
            other.append((p, f"{fmt_size(sz)}"))

    print(f"  vmdk (disk) total:        {fmt_size(vmdk_total)}  ({len(vmdk_files)} files)")
    print(f"  .vmem (memory dumps):     {fmt_size(sum(s for _, s in snap_vmem))}  ({len(snap_vmem)} files)")
    print(f"  .vmsn (snapshots):        {fmt_size(sum(s for _, s in snap_vmsn))}  ({len(snap_vmsn)} files)")
    print(f"  .lck lock dirs:           {len(lck_dirs)} (empty if VM not running)")
    print(f"  vmware-*.log:             {fmt_size(sum(s for _, s in log_files))}  ({len(log_files)} files)")

    # Group vmdks by parent disk
    print("\n  === VMDK breakdown (by base name) ===")
    groups = defaultdict(list)
    for p, sz in vmdk_files:
        # Strip -sNNN / -NNNNNN-sNNN suffix
        stem = p.name.replace(".vmdk", "")
        # Find base
        for sep in ("-s", "-0"):
            if sep in stem:
                stem = stem.split(sep)[0]
                break
        groups[stem].append((p.name, sz))

    for base, files in sorted(groups.items()):
        total = sum(s for _, s in files)
        print(f"    {base:35s} {len(files):2d} files  {fmt_size(total)}")

    # Recommendations
    print("\n  === Recommendations ===")
    if lck_dirs:
        print(f"  [A] Delete {len(lck_dirs)} .lck lock dirs (only if VMware is NOT running):")
        print(f"        del /s /q \"{vm_dir}\\*.lck\"  -- if VM is shut down")
    if log_files:
        log_total = sum(s for _, s in log_files)
        print(f"  [B] Delete vmware log files ({fmt_size(log_total)} - safe, VMware recreates):")
        print(f"        del \"{vm_dir}\\vmware*.log\"")
    snap_vmem_total = sum(s for _, s in snap_vmem)
    if snap_vmem_total > 0:
        print(f"  [C] Snapshot .vmem files ({fmt_size(snap_vmem_total)}):")
        print(f"        These are RAM dumps from old snapshots. Merged when you 'Delete Snapshot' in VMware UI.")

    # Count snapshots
    snapshot_bases = [b for b in groups if "Snapshot" in b]
    if snapshot_bases:
        print(f"  [D] Found {len(snapshot_bases)} snapshot chains to consider merging in VMware UI:")
        for s in snapshot_bases:
            total = sum(sz for _, sz in groups[s])
            print(f"        - {s}.vmdk  ({fmt_size(total)} of diff disks)")
        print(f"        Action: Open VM in VMware -> VM -> Snapshot Manager -> 'Delete' the oldest snapshot.")
        print(f"        This merges the diff disk back into the parent, freeing space.")
        print(f"        DO NOT do this while the VM is running.")

    # VMware CLI hint
    print("\n  === VMware CLI (if installed) ===")
    vmware_cli = "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmware-vdiskmanager.exe"
    if os.path.exists(vmware_cli):
        print(f"  Found: {vmware_cli}")
        print(f"  Shrink the active vmdk (must be done in 2 steps):")
        print(f"    1. Inside VM:  sudo dd if=/dev/zero of=/zerofile; sudo rm /zerofile; shutdown")
        print(f"    2. On host:    \"{vmware_cli}\" -k \"{vm_dir}\\Debian 12.x 64 \\?.vmdk\"")
    else:
        print(f"  vmware-vdiskmanager not found at {vmware_cli}")
        print(f"  Use the VMware UI: Edit VM Settings -> Hard Disk -> Utilities -> Compact")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else r"E:\kali"
    main(target)
