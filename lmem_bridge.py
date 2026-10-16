"""LightMem CLI Bridge.

Executes `lmem answer` and `lmem recall` via subprocess, parsing structured
JSON results to supply autofill values directly to the UI.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger("lightmem_autofill.lmem_bridge")


def find_lmem_executable() -> str:
    """Find the path to the lmem binary."""
    path = shutil.which("lmem")
    if not path:
        # Common fallback paths
        import os
        from pathlib import Path

        home = Path.home()
        candidates = [
            home / ".lightmem" / "bin" / "lmem.exe",
            home / ".lightmem" / "bin" / "lmem",
            home / ".cargo" / "bin" / "lmem.exe",
            home / ".cargo" / "bin" / "lmem",
        ]
        for c in candidates:
            if c.exists() and os.access(str(c), os.X_OK):
                return str(c)
        return "lmem"
    return path


class LightMemBridge:
    def __init__(self, binary_path: Optional[str] = None, use_global: bool = True):
        self.binary_path = binary_path or find_lmem_executable()
        self.use_global = use_global

    def query(self, text: str) -> Dict[str, Any]:
        """Query LightMem using extractive QA first, falling back to hybrid recall."""
        text = text.strip()
        if not text:
            return {"status": "empty", "value": "", "candidates": []}

        # 1. Try lmem answer for exact span extraction
        answer_res = self.query_answer(text)
        if answer_res and answer_res.get("confidence", 0.0) > 0.3:
            ans_text = answer_res.get("answer", "").strip()
            if ans_text and not ans_text.lower().startswith("insufficient evidence"):
                return {
                    "status": "success",
                    "mode": "answer",
                    "value": ans_text,
                    "confidence": answer_res.get("confidence", 1.0),
                    "memory_id": (answer_res.get("selected_memory") or {}).get("id"),
                    "candidates": [ans_text],
                }

        # 2. Fall back to lmem recall
        recalled = self.query_recall(text, limit=5)
        if recalled:
            candidates: List[str] = []
            for item in recalled:
                mem = item.get("memory", {})
                content = mem.get("content", "").strip()
                if content and content not in candidates:
                    candidates.append(content)

            top_val = candidates[0] if candidates else ""
            return {
                "status": "success" if top_val else "not_found",
                "mode": "recall",
                "value": top_val,
                "confidence": recalled[0].get("score", 0.5) if recalled else 0.0,
                "candidates": candidates,
            }

        return {"status": "not_found", "value": "", "candidates": []}

    def query_answer(self, question: str) -> Optional[Dict[str, Any]]:
        """Run `lmem answer <question> --json`."""
        cmd = [self.binary_path, "answer", question, "--json"]
        if self.use_global:
            cmd.append("-g")

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=12,
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout)
        except Exception as e:
            logger.debug(f"lmem answer error: {e}")
        return None

    def query_recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Run `lmem recall <query> -l <limit> --json`."""
        cmd = [self.binary_path, "recall", query, "-l", str(limit), "--json"]
        if self.use_global:
            cmd.append("-g")

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=8,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.debug(f"lmem recall error: {e}")
        return []
