"""Interactive TUI (Terminal User Interface) for storage analyzer.

Inspired by gdu's interactive interface.
Uses curses for terminal-based interaction.

Features:
- Navigate directories
- View file details
- Select items for cleanup
- Sort by size/name/date
- Filter by category
"""
from __future__ import annotations
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable


@dataclass
class TUIItem:
    """An item to display in TUI."""
    path: str
    name: str
    size_bytes: int
    is_dir: bool
    category: str = ''
    risk: str = ''
    selected: bool = False

    @property
    def size_human(self) -> str:
        if self.size_bytes == 0:
            return "0B"
        n = float(self.size_bytes)
        for u in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or u == "TB":
                return f"{n:.0f}{u}" if n < 100 else f"{n:.1f}{u}"
            n /= 1024
        return f"{n:.1f}PB"


class SimpleTUI:
    """Simple terminal UI without curses dependency.

    Works on all platforms including Windows.
    Uses basic print/input for interaction.
    """

    def __init__(self) -> None:
        self.items: List[TUIItem] = []
        self.current_dir: str = ''
        self.sort_by: str = 'size'  # 'size', 'name', 'date'
        self.filter_category: str = ''
        self.selected_indices: set = set()

    def scan_directory(self, path: str) -> None:
        """Scan a directory and populate items."""
        self.current_dir = path
        self.items = []

        try:
            for entry in os.scandir(path):
                try:
                    st = entry.stat()
                    self.items.append(TUIItem(
                        path=entry.path,
                        name=entry.name,
                        size_bytes=st.st_size if entry.is_file() else self._get_dir_size(entry.path),
                        is_dir=entry.is_dir(),
                    ))
                except OSError:
                    continue
        except OSError as e:
            print(f"Error scanning {path}: {e}")

        self._sort_items()

    def _get_dir_size(self, path: str) -> int:
        """Get directory size."""
        total = 0
        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        continue
        except OSError:
            pass
        return total

    def _sort_items(self) -> None:
        """Sort items by current sort key."""
        if self.sort_by == 'size':
            self.items.sort(key=lambda x: x.size_bytes, reverse=True)
        elif self.sort_by == 'name':
            self.items.sort(key=lambda x: x.name.lower())
        elif self.sort_by == 'date':
            self.items.sort(key=lambda x: x.size_bytes, reverse=True)  # Fallback

    def display(self) -> None:
        """Display current view."""
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')

        # Header
        print("=" * 70)
        print(f"  Storage Analyzer - {self.current_dir}")
        print("=" * 70)
        print()

        # Stats
        total_size = sum(item.size_bytes for item in self.items)
        selected_size = sum(item.size_bytes for i, item in enumerate(self.items) if i in self.selected_indices)
        print(f"  Items: {len(self.items)}  |  Total: {self._human_bytes(total_size)}  |  Selected: {self._human_bytes(selected_size)}")
        print()

        # Items
        print(f"  {'#':>4}  {'Size':>10}  {'Type':>5}  {'Name'}")
        print(f"  {'─'*4}  {'─'*10}  {'─'*5}  {'─'*40}")

        for i, item in enumerate(self.items[:20]):  # Show top 20
            marker = "*" if i in self.selected_indices else " "
            type_str = "DIR" if item.is_dir else "FILE"
            size_str = item.size_human if item.size_bytes > 0 else "─"
            print(f"  {marker}{i:>3}  {size_str:>10}  {type_str:>5}  {item.name}")

        if len(self.items) > 20:
            print(f"  ... +{len(self.items) - 20} more items")

        print()

    def show_menu(self) -> str:
        """Show menu and get user choice."""
        print("  Commands:")
        print("    [s] Sort by size    [n] Sort by name    [d] Sort by date")
        print("    [1-9] Select item   [a] Select all      [c] Clear selection")
        print("    [e] Execute         [p] Save plan       [q] Quit")
        print()

        choice = input("  Enter command: ").strip().lower()
        return choice

    def handle_input(self, choice: str) -> bool:
        """Handle user input. Returns False to quit."""
        if choice == 'q':
            return False
        elif choice == 's':
            self.sort_by = 'size'
            self._sort_items()
        elif choice == 'n':
            self.sort_by = 'name'
            self._sort_items()
        elif choice == 'd':
            self.sort_by = 'date'
            self._sort_items()
        elif choice == 'a':
            self.selected_indices = set(range(len(self.items)))
        elif choice == 'c':
            self.selected_indices.clear()
        elif choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(self.items):
                if idx in self.selected_indices:
                    self.selected_indices.remove(idx)
                else:
                    self.selected_indices.add(idx)
        elif choice == 'e':
            self._execute_cleanup()
        elif choice == 'p':
            self._save_plan()
        return True

    def _execute_cleanup(self) -> None:
        """Execute cleanup for selected items."""
        if not self.selected_indices:
            print("  No items selected!")
            input("  Press Enter to continue...")
            return

        total_size = sum(self.items[i].size_bytes for i in self.selected_indices)
        print(f"\n  Will delete {len(self.selected_indices)} items ({self._human_bytes(total_size)})")
        confirm = input("  Are you sure? (y/n): ").strip().lower()

        if confirm == 'y':
            deleted = 0
            for idx in self.selected_indices:
                item = self.items[idx]
                try:
                    if item.is_dir:
                        import shutil
                        shutil.rmtree(item.path)
                    else:
                        os.remove(item.path)
                    deleted += 1
                except OSError as e:
                    print(f"  Failed to delete {item.name}: {e}")

            print(f"\n  Deleted {deleted} items")
            self.selected_indices.clear()
            self.scan_directory(self.current_dir)  # Rescan

        input("  Press Enter to continue...")

    def _save_plan(self) -> None:
        """Save current selection as a plan."""
        if not self.selected_indices:
            print("  No items selected!")
            input("  Press Enter to continue...")
            return

        from .cleanup_plan import PlanManager

        manager = PlanManager()
        items = []
        for idx in self.selected_indices:
            item = self.items[idx]
            items.append({
                'path': item.path,
                'name': item.name,
                'size_bytes': item.size_bytes,
                'category': 'manual',
                'risk': 'review',
            })

        plan = manager.create_plan([self.current_dir], items)
        filepath = manager.save_plan(plan)
        print(f"\n  Plan saved: {filepath}")
        input("  Press Enter to continue...")

    def run(self, path: str = None) -> None:
        """Run the TUI."""
        if path is None:
            path = os.path.expanduser('~')

        self.scan_directory(path)

        while True:
            self.display()
            choice = self.show_menu()
            if not self.handle_input(choice):
                break

    @staticmethod
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


class MenuDrivenUI:
    """Menu-driven UI for non-interactive environments."""

    @staticmethod
    def show_scan_options() -> Dict[str, Any]:
        """Show scan options and get user choices."""
        print("\n=== Storage Analyzer v9.0 ===\n")
        print("Scan Options:")
        print("  1. Quick scan (Downloads, Desktop, Temp)")
        print("  2. Full scan (All user directories)")
        print("  3. Custom path")
        print("  4. Load saved plan")
        print()

        choice = input("Select option (1-4): ").strip()

        if choice == '1':
            return {
                'mode': 'quick',
                'paths': [
                    os.path.join(os.path.expanduser('~'), 'Downloads'),
                    os.path.join(os.path.expanduser('~'), 'Desktop'),
                    os.environ.get('TEMP', ''),
                ]
            }
        elif choice == '2':
            home = os.path.expanduser('~')
            return {
                'mode': 'full',
                'paths': [
                    os.path.join(home, 'Downloads'),
                    os.path.join(home, 'Documents'),
                    os.path.join(home, 'Desktop'),
                    os.path.join(home, 'Pictures'),
                    os.path.join(home, 'Videos'),
                ]
            }
        elif choice == '3':
            path = input("Enter path to scan: ").strip()
            return {'mode': 'custom', 'paths': [path]}
        elif choice == '4':
            return {'mode': 'plan'}
        else:
            return {'mode': 'quick', 'paths': []}

    @staticmethod
    def show_cleanup_options(items: List[Dict[str, Any]]) -> List[str]:
        """Show cleanup options and get user choices."""
        print(f"\nFound {len(items)} items to clean\n")

        # Group by risk
        safe = [i for i in items if i.get('risk') == 'safe']
        review = [i for i in items if i.get('risk') == 'review']
        high = [i for i in items if i.get('risk') == 'high']

        print(f"  [SAFE]     {len(safe)} items")
        print(f"  [REVIEW]   {len(review)} items")
        print(f"  [HIGH]     {len(high)} items")
        print()

        print("Cleanup Options:")
        print("  1. Clean SAFE items only (recommended)")
        print("  2. Clean SAFE + REVIEW items")
        print("  3. Clean all items (not recommended)")
        print("  4. Select manually")
        print("  5. Save plan for later")
        print()

        choice = input("Select option (1-5): ").strip()

        if choice == '1':
            return [i['path'] for i in safe]
        elif choice == '2':
            return [i['path'] for i in safe + review]
        elif choice == '3':
            return [i['path'] for i in items]
        elif choice == '4':
            # Manual selection
            selected = []
            for i, item in enumerate(items[:50]):  # Show top 50
                print(f"  [{i}] {item['name']} ({item.get('size_human', '?')})")
            indices = input("Enter indices to clean (comma-separated): ").strip()
            for idx in indices.split(','):
                try:
                    idx = int(idx.strip())
                    if 0 <= idx < len(items):
                        selected.append(items[idx]['path'])
                except ValueError:
                    continue
            return selected
        elif choice == '5':
            return []  # Save plan instead
        else:
            return []


def run_tui(path: str = None) -> None:
    """Run the interactive TUI."""
    tui = SimpleTUI()
    tui.run(path)


def run_menu() -> Dict[str, Any]:
    """Run the menu-driven UI."""
    return MenuDrivenUI.show_scan_options()
