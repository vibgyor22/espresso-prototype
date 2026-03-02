from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "outputs" / "inference_history.jsonl"


def record_run(entry: Dict[str, Any]) -> None:
  """
  Append a single inference run to the audit log.

  The entry should be JSON-serializable. A UTC timestamp and simple run_id
  will be added automatically.
  """
  LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
  ts = datetime.now(timezone.utc).isoformat()
  # Use timestamp plus a cheap hash of question as run_id
  question = (entry.get("question") or "")[:80]
  run_id = f"{ts}|{abs(hash(question)) % 10_000_000:07d}"

  payload: Dict[str, Any] = {
      "run_id": run_id,
      "timestamp": ts,
      **entry,
  }

  with LOG_PATH.open("a", encoding="utf-8") as f:
      f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_all_lines() -> List[Dict[str, Any]]:
  if not LOG_PATH.exists():
      return []
  lines: List[Dict[str, Any]] = []
  with LOG_PATH.open("r", encoding="utf-8") as f:
      for line in f:
          line = line.strip()
          if not line:
              continue
          try:
              lines.append(json.loads(line))
          except json.JSONDecodeError:
              continue
  return lines


def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
  """
  Return the most recent `limit` runs from the audit log.
  """
  all_runs = _read_all_lines()
  return all_runs[-limit:]


