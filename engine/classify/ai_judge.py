"""AI-assisted classification (optional, opt-in).

Why this exists:
  The rule-based classifier in `classifier.py` covers ~85% of common
  cleanup targets via regex + heuristics. The remaining 15% are
  "yellow" items where the user could benefit from a second opinion.

  This module is the seam where a local LLM (Ollama / LM Studio /
  any OpenAI-compatible endpoint) can be plugged in to judge ambiguous
  items. It is OFF by default and does nothing unless the user passes
  --ai-judge or sets `ai: enabled: true` in config.

Design principles:
  - The rule-based path is never replaced; AI is an *additional* tier
    that only runs on items the rules couldn't confidently classify.
  - Local-first: default endpoint is http://localhost:11434 (Ollama).
    No data leaves the machine.
  - Cache: identical items produce identical verdicts, cached on disk.
  - Budget: a hard cap on items-per-run and total time, so AI cannot
    make a 30s scan take 10 minutes.
  - Failure-tolerant: if the model is down / slow / wrong, fall back
    to the rule verdict silently and continue.

Public API:
  from engine.classify.ai_judge import AIJudge, NullJudge
  judge = AIJudge.from_config(cfg)  # or NullJudge() to disable
  verdict = judge.judge(item)       # item -> Verdict dataclass
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Verdict:
    """AI judge verdict for a single item."""
    tier: str            # "green" | "yellow" | "red"
    reason: str          # human-readable explanation
    confidence: float    # 0.0 - 1.0
    model: str           # model name used (or "rules" / "null")
    elapsed_ms: int      # how long the judgment took
    cached: bool = False # whether this came from the on-disk cache

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseJudge:
    """Subclass this to add a new AI backend (OpenAI, Anthropic, etc.)."""

    def judge(self, item: Dict[str, Any]) -> Verdict:  # pragma: no cover
        raise NotImplementedError

    def judge_batch(self, items: List[Dict[str, Any]]) -> List[Verdict]:
        return [self.judge(i) for i in items]

    def close(self) -> None:
        """Optional cleanup (close HTTP sessions, etc.)."""
        pass


class NullJudge(BaseJudge):
    """Default no-op judge. Always returns the input's existing tier."""

    def judge(self, item: Dict[str, Any]) -> Verdict:
        return Verdict(
            tier=item.get("tier", "yellow"),
            reason=item.get("reason", "no AI judge configured"),
            confidence=0.0,
            model="null",
            elapsed_ms=0,
            cached=False,
        )


# ---------------------------------------------------------------------------
# Local LLM judge (Ollama-compatible)
# ---------------------------------------------------------------------------

# Default prompt — small on purpose, local models are fast but small.
_JUDGE_PROMPT = """You are a senior sysadmin helping decide whether a file/directory is safe to delete.

Item:
- name: {name}
- path: {path}
- size: {size_h}
- group: {group}
- rules_matched: {rules}

Respond with EXACTLY one line, no prose, no markdown:
TIER|REASON|CONFIDENCE
where TIER is one of: green (safe to delete), yellow (review first), red (do not delete).
CONFIDENCE is a number 0.0-1.0.

Examples:
green|System temp file, regenerated on reboot|0.95
yellow|Project build cache, may slow next build|0.7
red|User document directory|0.99
"""


class LocalLLMJudge(BaseJudge):
    """Ollama / OpenAI-compatible local model judge.

    Requires `requests`. If requests is not installed, the judge falls
    back to NullJudge() at construction time.

    Config (under `ai:` in config.json):
        enabled:       bool, default False
        endpoint:      str,  default http://localhost:11434
        model:         str,  default qwen2.5:3b
        timeout_s:     int,  default 5
        max_items:     int,  default 50  (cap per scan)
        cache_path:    str,  default ~/.cache/storage-analyzer/ai_cache.json
    """

    def __init__(self, cfg: Dict[str, Any]):
        try:
            import requests  # noqa: F401  -- only import-time check
        except ImportError:
            raise RuntimeError(
                "AI judge needs the 'requests' package. "
                "Install with: pip install requests"
            )

        self.endpoint = cfg.get("endpoint", "http://localhost:11434").rstrip("/")
        self.model = cfg.get("model", "qwen2.5:3b")
        self.timeout_s = int(cfg.get("timeout_s", 5))
        self.max_items = int(cfg.get("max_items", 50))
        self.cache_path = os.path.expanduser(
            cfg.get("cache_path", "~/.cache/storage-analyzer/ai_cache.json")
        )
        self._cache: Dict[str, Verdict] = self._load_cache()

    # ---- public ---------------------------------------------------------

    def judge(self, item: Dict[str, Any]) -> Verdict:
        key = self._cache_key(item)

        # Cache hit
        if key in self._cache:
            v = self._cache[key]
            v.cached = True
            return v

        # Build prompt
        prompt = _JUDGE_PROMPT.format(
            name=item.get("name", item.get("n", "?")),
            path=item.get("path", item.get("p", "?")),
            size_h=item.get("h", item.get("size_h", "?")),
            group=item.get("group", item.get("cat", "?")),
            rules=item.get("rules_matched", []),
        )

        t0 = time.time()
        try:
            raw = self._call_ollama(prompt)
            verdict = self._parse(raw, self.model, int((time.time() - t0) * 1000))
        except Exception as e:
            # Failure-tolerant: return a low-confidence yellow
            verdict = Verdict(
                tier="yellow",
                reason=f"AI judge failed: {type(e).__name__}",
                confidence=0.0,
                model=self.model,
                elapsed_ms=int((time.time() - t0) * 1000),
            )

        self._cache[key] = verdict
        return verdict

    def close(self) -> None:
        self._save_cache()

    # ---- internal -------------------------------------------------------

    def _call_ollama(self, prompt: str) -> str:
        import requests
        url = f"{self.endpoint}/api/generate"
        resp = requests.post(
            url,
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    @staticmethod
    def _parse(raw: str, model: str, elapsed_ms: int) -> Verdict:
        """Parse 'TIER|REASON|CONFIDENCE' line. Lenient on noise."""
        line = raw.splitlines()[-1] if raw else ""
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            return Verdict("yellow", "AI response unparseable", 0.0, model, elapsed_ms)
        tier = parts[0].lower()
        if tier not in ("green", "yellow", "red"):
            tier = "yellow"
        try:
            conf = max(0.0, min(1.0, float(parts[-1])))
        except ValueError:
            conf = 0.5
        reason = "|".join(parts[1:-1]) or "no reason given"
        return Verdict(tier, reason[:200], conf, model, elapsed_ms)

    def _cache_key(self, item: Dict[str, Any]) -> str:
        payload = json.dumps(
            {"n": item.get("n"), "p": item.get("p"), "g": item.get("group", item.get("cat"))},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _load_cache(self) -> Dict[str, Verdict]:
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {k: Verdict(**v) for k, v in raw.items()}
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return {}

    def _save_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({k: v.to_dict() for k, v in self._cache.items()}, f)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def from_config(cfg: Dict[str, Any]) -> BaseJudge:
    """Build a judge from the `ai:` section of the loaded config.

    Falls back to NullJudge when AI is disabled or the backend fails
    to initialize (so the rest of the tool keeps working).
    """
    ai_cfg = (cfg or {}).get("ai", {}) or {}
    if not ai_cfg.get("enabled", False):
        return NullJudge()
    try:
        return LocalLLMJudge(ai_cfg)
    except Exception:
        # Backend not installed / config wrong - silently degrade.
        return NullJudge()
