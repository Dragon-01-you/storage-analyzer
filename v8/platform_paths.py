"""Platform-aware path resolution.

Centralises ALL platform-specific paths so that engine_core.py
and cleaners never hardcode OS-specific paths themselves.

Usage:
    paths = PlatformPaths.resolve()
    for key, path in paths.scannable_dirs.items():
        if path.is_dir():
            scan(path)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PlatformPaths:
    """All platform-resolved paths the scanner needs."""

    # Core OS dirs
    temp_dirs: list[Path] = field(default_factory=list)
    cache_dirs: list[Path] = field(default_factory=list)
    recycle_dirs: list[Path] = field(default_factory=list)

    # App-specific caches
    browser_caches: list[Path] = field(default_factory=list)
    browser_profiles: list[Path] = field(default_factory=list)
    dev_caches: list[Path] = field(default_factory=list)
    ide_caches: list[Path] = field(default_factory=list)
    cloud_sync: list[Path] = field(default_factory=list)
    game_caches: list[Path] = field(default_factory=list)
    chat_caches: list[Path] = field(default_factory=list)

    @classmethod
    def resolve(cls, user_home: Path | None = None) -> "PlatformPaths":
        """Auto-detect platform and return all known paths."""
        home = user_home or Path.home()
        if sys.platform == "win32":
            return cls._resolve_windows(home)
        elif sys.platform == "darwin":
            return cls._resolve_macos(home)
        else:
            return cls._resolve_linux(home)

    @classmethod
    def _resolve_windows(cls, home: Path) -> "PlatformPaths":
        local = _env("LOCALAPPDATA", home / "AppData" / "Local")
        roaming = _env("APPDATA", home / "AppData" / "Roaming")
        temp = Path(_env("TEMP", local / "Temp"))

        return cls(
            temp_dirs=[temp, local / "Temp"],
            cache_dirs=[local / "Microsoft" / "Windows" / "Explorer"],
            recycle_dirs=[Path("C:\\$Recycle.Bin")],
            browser_caches=[
                local / "Google" / "Chrome" / "User Data" / "Default" / "Cache",
                local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache",
                local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache",
            ],
            browser_profiles=[
                local / "Google" / "Chrome" / "User Data",
                local / "Microsoft" / "Edge" / "User Data",
                local / "Mozilla" / "Firefox" / "Profiles",
                local / "BraveSoftware" / "Brave-Browser" / "User Data",
            ],
            dev_caches=[
                local / "npm-cache",
                local / "pip" / "cache",
                local / "Yarn" / "Cache",
                local / "pnpm" / "store",
                home / ".cargo" / "registry",
                home / ".gradle" / "caches",
                home / ".m2" / "repository",
                home / ".nuget" / "packages",
                home / ".bun" / "install" / "cache",
                home / ".uv" / "cache",
                local / "ms-playwright",
            ],
            ide_caches=[
                local / "JetBrains",
                local / "Microsoft" / "VisualStudio",
                local / "Google" / "AndroidStudio",
            ],
            cloud_sync=[
                local / "Microsoft" / "OneDrive",
                home / "OneDrive",
            ],
            game_caches=[
                local / "Steam" / "htmlcache",
                local / "Steam" / "shadercache",
            ],
            chat_caches=[
                local / "Discord" / "Cache",
                local / "Slack" / "Cache",
                roaming / "Slack" / "Cache",
                local / "Tencent" / "QQ",
            ],
        )

    @classmethod
    def _resolve_macos(cls, home: Path) -> "PlatformPaths":
        lib = home / "Library"
        return cls(
            temp_dirs=[Path("/tmp"), Path("/var/tmp"), home / ".Trash"],
            cache_dirs=[lib / "Caches"],
            recycle_dirs=[home / ".Trash"],
            browser_caches=[
                lib / "Caches" / "Google" / "Chrome",
                lib / "Caches" / "com.microsoft.edgemac",
                lib / "Caches" / "Firefox",
            ],
            browser_profiles=[
                lib / "Application Support" / "Google" / "Chrome",
                lib / "Application Support" / "Firefox",
            ],
            dev_caches=[
                lib / "Caches" / "npm",
                home / ".cache" / "pip",
                home / ".cargo" / "registry",
                home / ".gradle" / "caches",
                home / ".m2" / "repository",
            ],
            ide_caches=[
                lib / "Caches" / "JetBrains",
                lib / "Caches" / "com.jetbrains.intellij",
            ],
            cloud_sync=[
                home / "Library" / "CloudStorage",
            ],
            game_caches=[
                lib / "Application Support" / "Steam" / "htmlcache",
            ],
            chat_caches=[
                lib / "Caches" / "discord",
                lib / "Caches" / "Slack",
            ],
        )

    @classmethod
    def _resolve_linux(cls, home: Path) -> "PlatformPaths":
        xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", str(home / ".cache")))
        return cls(
            temp_dirs=[Path("/tmp"), Path("/var/tmp")],
            cache_dirs=[xdg_cache, Path("/var/cache")],
            recycle_dirs=[xdg_cache / "Trash" / "files"],
            browser_caches=[
                xdg_cache / "google-chrome",
                xdg_cache / "mozilla" / "firefox",
                xdg_cache / "microsoft-edge",
            ],
            browser_profiles=[
                home / ".config" / "google-chrome",
                home / ".mozilla" / "firefox",
                home / ".config" / "microsoft-edge",
            ],
            dev_caches=[
                xdg_cache / "npm",
                xdg_cache / "pip",
                home / ".cargo" / "registry",
                home / ".gradle" / "caches",
                home / ".m2" / "repository",
            ],
            ide_caches=[
                xdg_cache / "JetBrains",
                home / ".cache" / "JetBrains",
            ],
            cloud_sync=[],
            game_caches=[
                xdg_cache / "Steam" / "htmlcache",
            ],
            chat_caches=[
                xdg_cache / "discord",
                xdg_cache / "Slack",
            ],
        )

    def all_scannable(self) -> list[Path]:
        """Return every known path that might contain cleanable data."""
        all_paths = []
        for fld in (
            self.temp_dirs,
            self.cache_dirs,
            self.browser_caches,
            self.browser_profiles,
            self.dev_caches,
            self.ide_caches,
            self.cloud_sync,
            self.game_caches,
            self.chat_caches,
        ):
            all_paths.extend(fld)
        return [p for p in all_paths if p.is_dir()]


def _env(name: str, fallback: Path) -> Path:
    """Get env var as Path, with fallback."""
    v = os.environ.get(name)
    return Path(v) if v else fallback
