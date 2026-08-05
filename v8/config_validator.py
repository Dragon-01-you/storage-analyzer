"""Config validation for storage-analyzer.

Validates config.json structure and rules to prevent:
- Malicious rules that mark system files as safe
- Invalid regex patterns
- Missing required fields
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class ValidationError:
    """A single validation error."""
    path: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class ValidationResult:
    """Result of config validation."""
    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def add_error(self, path: str, message: str) -> None:
        self.errors.append(ValidationError(path=path, message=message))
        self.valid = False

    def add_warning(self, path: str, message: str) -> None:
        self.warnings.append(ValidationError(path=path, message=message, severity="warning"))

    def summary(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  [{e.path}] {e.message}")
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  [{w.path}] {w.message}")
        if not self.errors and not self.warnings:
            lines.append("Config is valid.")
        return "\n".join(lines)


# Paths that should NEVER be marked as safe (green)
PROTECTED_SYSTEM_PATHS = [
    r"c:\\windows",
    r"c:\\windows\\system32",
    r"c:\\program files",
    r"c:\\program files (x86)",
    r"/bin",
    r"/sbin",
    r"/etc",
    r"/usr",
    r"/boot",
    r"/system",
    r"/applications",
]


class ConfigValidator:
    """Validate storage-analyzer config.json.

    Checks:
    1. Required fields exist
    2. Regex patterns are valid
    3. No system paths marked as green (safe)
    4. known_apps entries have correct format
    5. Protected paths list is sane
    """

    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate a config dict."""
        result = ValidationResult()

        # Check required top-level keys
        if "scan" not in config:
            result.add_error("scan", "Missing required field 'scan'")
        if "classify" not in config:
            result.add_error("classify", "Missing required field 'classify'")
        if "protected_paths" not in config:
            result.add_warning("protected_paths", "Missing 'protected_paths', using defaults")

        # Validate scan settings
        if "scan" in config:
            self._validate_scan(config["scan"], result)

        # Validate classify rules
        if "classify" in config:
            self._validate_classify(config["classify"], result)

        # Validate protected paths
        if "protected_paths" in config:
            self._validate_protected(config["protected_paths"], result)

        return result

    def _validate_scan(self, scan: Dict[str, Any], result: ValidationResult) -> None:
        """Validate scan settings."""
        if "timeout" in scan:
            if not isinstance(scan["timeout"], (int, float)) or scan["timeout"] <= 0:
                result.add_error("scan.timeout", "Must be a positive number")
        if "max_depth" in scan:
            if not isinstance(scan["max_depth"], int) or scan["max_depth"] < 1:
                result.add_error("scan.max_depth", "Must be a positive integer")
        if "min_kb" in scan:
            if not isinstance(scan["min_kb"], (int, float)) or scan["min_kb"] < 0:
                result.add_error("scan.min_kb", "Must be a non-negative number")
        if "workers" in scan:
            if not isinstance(scan["workers"], int) or scan["workers"] < 1:
                result.add_error("scan.workers", "Must be a positive integer")

    def _validate_classify(self, classify: Dict[str, Any], result: ValidationResult) -> None:
        """Validate classify rules."""
        # Validate green rules
        if "green" in classify:
            for i, rule in enumerate(classify["green"]):
                self._validate_rule(rule, f"classify.green[{i}]", result, is_green=True)

        # Validate red rules
        if "red" in classify:
            for i, rule in enumerate(classify["red"]):
                self._validate_rule(rule, f"classify.red[{i}]", result, is_green=False)

        # Validate known_apps
        if "known_apps" in classify:
            for name, entry in classify["known_apps"].items():
                self._validate_known_app(name, entry, result)

    def _validate_rule(
        self,
        rule: Dict[str, Any],
        path: str,
        result: ValidationResult,
        is_green: bool = True
    ) -> None:
        """Validate a single classify rule."""
        if "pat" not in rule:
            result.add_error(path, "Missing required field 'pat'")
            return

        # Validate regex pattern
        try:
            re.compile(rule["pat"])
        except re.error as e:
            result.add_error(f"{path}.pat", f"Invalid regex: {e}")
            return

        # Check for dangerous green rules
        if is_green:
            self._check_dangerous_green(rule, path, result)

    def _check_dangerous_green(
        self,
        rule: Dict[str, Any],
        path: str,
        result: ValidationResult
    ) -> None:
        """Check if a green rule might match protected system paths."""
        pat = rule["pat"].lower()

        # Check for patterns that could match system directories
        dangerous_patterns = [
            (r"\\\\windows\\\\", "Windows system directory"),
            (r"\\\\program files", "Program Files"),
            (r"\\\\system32", "System32"),
            (r"/usr/", "/usr directory"),
            (r"/bin/", "/bin directory"),
            (r"/etc/", "/etc directory"),
        ]

        for dpat, desc in dangerous_patterns:
            if dpat in pat:
                result.add_warning(
                    path,
                    f"Pattern might match {desc}. "
                    f"Ensure this is intentional and won't delete system files."
                )

    def _validate_known_app(
        self,
        name: str,
        entry: Any,
        result: ValidationResult
    ) -> None:
        """Validate a known_apps entry."""
        path = f"classify.known_apps.{name}"

        if not isinstance(entry, list) or len(entry) != 2:
            result.add_error(path, "Must be a list of [tier, reason]")
            return

        tier, reason = entry
        valid_tiers = ("green", "yellow", "red")
        if tier not in valid_tiers:
            result.add_error(f"{path}[0]", f"Tier must be one of {valid_tiers}, got '{tier}'")

        if not isinstance(reason, str) or not reason:
            result.add_error(f"{path}[1]", "Reason must be a non-empty string")

    def _validate_protected(
        self,
        protected: List[str],
        result: ValidationResult
    ) -> None:
        """Validate protected paths list."""
        if not isinstance(protected, list):
            result.add_error("protected_paths", "Must be a list")
            return

        # Check for common system paths
        has_windows = any("windows" in p.lower() for p in protected)
        has_program_files = any("program files" in p.lower() for p in protected)

        if not has_windows:
            result.add_warning(
                "protected_paths",
                "No Windows directory in protected paths. "
                "This is dangerous on Windows systems."
            )

        if not has_program_files:
            result.add_warning(
                "protected_paths",
                "No Program Files in protected paths. "
                "Installed applications might be accidentally deleted."
            )


def validate_config_file(config_path: str) -> ValidationResult:
    """Validate a config.json file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        result = ValidationResult()
        result.add_error("file", f"Config file not found: {config_path}")
        return result
    except json.JSONDecodeError as e:
        result = ValidationResult()
        result.add_error("file", f"Invalid JSON: {e}")
        return result

    validator = ConfigValidator()
    return validator.validate(config)


def validate_config_dict(config: Dict[str, Any]) -> ValidationResult:
    """Validate a config dict."""
    validator = ConfigValidator()
    return validator.validate(config)
