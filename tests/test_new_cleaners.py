"""Tests for new cleaners added in v9.0."""
import os
import sys
import tempfile
import shutil
from pathlib import Path
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cleaners._base import ScanContext, Entry
from cleaners._communication import (
    DiscordCleaner, SlackCleaner, ZoomCleaner, SkypeCleaner, TelegramCleaner
)
from cleaners._browsers_extra import (
    OperaCacheCleaner, VivaldiCacheCleaner, ChromiumCacheCleaner,
    LibreWolfCacheCleaner, WaterfoxCacheCleaner, ArcCacheCleaner
)
from cleaners._dev_extra import (
    JavaCacheCleaner, PythonCacheCleaner, VimSwapCleaner,
    TortoiseSVNCacheCleaner, GitCacheCleaner, RubyCacheCleaner, GoCacheCleaner
)
from cleaners._office import (
    OfficeCacheCleaner, LibreOfficeCacheCleaner, ThunderbirdCacheCleaner, OutlookCacheCleaner
)
from cleaners._gaming import (
    EpicGamesCleaner, GOGGalaxyCleaner, EACleaner, UbisoftConnectCleaner
)
from cleaners._deep_scan import (
    BackupFilesCleaner, DSStoreCleaner, ThumbsDbCleaner,
    NodeModulesCleaner, VenvCleaner, PycacheCleaner, OldInstallersCleaner,
    LogFilesCleaner, OldDownloadsCleaner, WindowsUpdateCleanup,
    InstallerResidualsCleaner, CrashDumpCleaner
)
from cleaners._windows_integration import (
    RecentDocsCleaner, WindowsOldCleaner, DeliveryOptimizationCleaner,
    DefenderHistoryCleaner, ErrorReportingCleaner, FontCacheCleaner, IconCacheCleaner
)
from cleaners._downloads_analyzer import DownloadsAnalyzer, TempFilesCleaner, RecycleBinCleaner
from cleaners._media import (
    VLCCacheCleaner, SpotifyCacheCleaner, AdobeReaderCacheCleaner,
    WinRARCacheCleaner, SevenZipCacheCleaner, EverythingCacheCleaner
)
from cleaners._communication import COMMUNICATION_CLEANERS
from cleaners._browsers_extra import BROWSER_CLEANERS_EXTRA_NEW
from cleaners._dev_extra import DEV_CLEANERS_EXTRA_NEW
from cleaners._office import OFFICE_CLEANERS
from cleaners._gaming import GAMING_CLEANERS
from cleaners._deep_scan import DEEP_SCAN_CLEANERS
from cleaners._windows_integration import WINDOWS_INTEGRATION_CLEANERS
from cleaners._downloads_analyzer import DOWNLOADS_CLEANERS
from cleaners._media import MEDIA_CLEANERS


class TestCleanerImports:
    """Test that all new cleaners can be imported."""

    def test_communication_cleaners(self):
        assert len(COMMUNICATION_CLEANERS) == 5
        for cls in COMMUNICATION_CLEANERS:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_browsers_extra_cleaners(self):
        assert len(BROWSER_CLEANERS_EXTRA_NEW) == 6
        for cls in BROWSER_CLEANERS_EXTRA_NEW:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_dev_extra_cleaners(self):
        assert len(DEV_CLEANERS_EXTRA_NEW) == 7
        for cls in DEV_CLEANERS_EXTRA_NEW:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_office_cleaners(self):
        assert len(OFFICE_CLEANERS) == 4
        for cls in OFFICE_CLEANERS:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_gaming_cleaners(self):
        assert len(GAMING_CLEANERS) == 4
        for cls in GAMING_CLEANERS:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_deep_scan_cleaners(self):
        assert len(DEEP_SCAN_CLEANERS) == 12
        for cls in DEEP_SCAN_CLEANERS:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_windows_integration_cleaners(self):
        assert len(WINDOWS_INTEGRATION_CLEANERS) == 7
        for cls in WINDOWS_INTEGRATION_CLEANERS:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_downloads_cleaners(self):
        assert len(DOWNLOADS_CLEANERS) == 3
        for cls in DOWNLOADS_CLEANERS:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')

    def test_media_cleaners(self):
        assert len(MEDIA_CLEANERS) == 6
        for cls in MEDIA_CLEANERS:
            assert hasattr(cls, 'name')
            assert hasattr(cls, 'analyze')


class TestCleanerMetadata:
    """Test that all cleaners have proper metadata."""

    def test_all_cleaners_have_category(self):
        all_cleaners = (
            COMMUNICATION_CLEANERS +
            BROWSER_CLEANERS_EXTRA_NEW +
            DEV_CLEANERS_EXTRA_NEW +
            OFFICE_CLEANERS +
            GAMING_CLEANERS +
            DEEP_SCAN_CLEANERS +
            WINDOWS_INTEGRATION_CLEANERS +
            DOWNLOADS_CLEANERS +
            MEDIA_CLEANERS
        )
        for cls in all_cleaners:
            assert hasattr(cls, 'category'), f"{cls.name} missing category"
            assert cls.category in (
                'system', 'dev', 'browser', 'cloud', 'chat', 'ide',
                'gaming', 'mail', 'office', 'media'
            ), f"{cls.name} has invalid category: {cls.category}"

    def test_all_cleaners_have_risk_level(self):
        all_cleaners = (
            COMMUNICATION_CLEANERS +
            BROWSER_CLEANERS_EXTRA_NEW +
            DEV_CLEANERS_EXTRA_NEW +
            OFFICE_CLEANERS +
            GAMING_CLEANERS +
            DEEP_SCAN_CLEANERS +
            WINDOWS_INTEGRATION_CLEANERS +
            DOWNLOADS_CLEANERS +
            MEDIA_CLEANERS
        )
        for cls in all_cleaners:
            assert hasattr(cls, 'risk_level'), f"{cls.name} missing risk_level"
            assert cls.risk_level in ('none', 'med', 'high'), \
                f"{cls.name} has invalid risk_level: {cls.risk_level}"


class TestCleanerInstantiation:
    """Test that all cleaners can be instantiated."""

    def test_instantiate_all_new_cleaners(self):
        all_cleaners = (
            COMMUNICATION_CLEANERS +
            BROWSER_CLEANERS_EXTRA_NEW +
            DEV_CLEANERS_EXTRA_NEW +
            OFFICE_CLEANERS +
            GAMING_CLEANERS +
            DEEP_SCAN_CLEANERS +
            WINDOWS_INTEGRATION_CLEANERS +
            DOWNLOADS_CLEANERS +
            MEDIA_CLEANERS
        )
        for cls in all_cleaners:
            try:
                instance = cls()
                assert instance is not None
            except Exception as e:
                pytest.fail(f"Failed to instantiate {cls.name}: {e}")


class TestCleanerRegistry:
    """Test that all cleaners are properly registered."""

    def test_registry_contains_all_new_cleaners(self):
        from cleaners import REGISTRY
        registry_names = {c.name for c in REGISTRY}

        expected_names = [
            'discord-cache', 'slack-cache', 'zoom-cache', 'skype-cache', 'telegram-cache',
            'opera-cache', 'vivaldi-cache', 'chromium-cache', 'librewolf-cache',
            'waterfox-cache', 'arc-cache',
            'java-cache', 'python-cache', 'vim-swap', 'tortoisesvn-cache',
            'git-cache', 'ruby-cache', 'go-cache',
            'office-cache', 'libreoffice-cache', 'thunderbird-cache', 'outlook-cache',
            'epic-games', 'gog-galaxy', 'ea-app', 'ubisoft-connect',
            'backup-files', 'ds-store', 'thumbs-db', 'node-modules',
            'python-venv', 'pycache', 'old-installers',
            'log-files', 'old-downloads', 'windows-update-cleanup',
            'installer-residuals', 'crash-dumps-deep',
            'recent-docs', 'windows-old', 'delivery-optimization',
            'defender-history', 'error-reporting', 'font-cache', 'icon-cache',
            'downloads-analyzer', 'temp-files', 'recycle-bin',
            'vlc-cache', 'spotify-cache', 'adobe-reader-cache',
            'winrar-cache', '7zip-cache', 'everything-cache',
        ]

        for name in expected_names:
            assert name in registry_names, f"{name} not in REGISTRY"

    def test_registry_count(self):
        from cleaners import REGISTRY
        assert len(REGISTRY) >= 80, f"Expected at least 80 cleaners, got {len(REGISTRY)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
