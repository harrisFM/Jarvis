"""Append-only audit log of every tool call: who asked, what ran, what the policy said, the result."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: Path | str) -> None:
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                user_id TEXT, user_role TEXT, room TEXT,
                tool TEXT NOT NULL, tool_input TEXT,
                decision TEXT NOT NULL, approved_by TEXT,
                result TEXT, is_error INTEGER DEFAULT 0, duration_ms REAL
            )"""
        )
        self.conn.commit()

    def record(self, *, user_id: str, user_role: str, room: str, tool: str, tool_input: dict[str, Any],
               decision: str, approved_by: str | None, result: str, is_error: bool, duration_ms: float) -> int:
        cur = self.conn.execute(
            "INSERT INTO audit (ts,user_id,user_role,room,tool,tool_input,decision,approved_by,result,is_error,duration_ms)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (time.time(), user_id, user_role, room, tool, json.dumps(tool_input, default=str), decision,
             approved_by, result[:4000], int(is_error), duration_ms),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id,ts,user_id,user_role,room,tool,tool_input,decision,approved_by,result,is_error,duration_ms"
            " FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        keys = ["id", "ts", "user_id", "user_role", "room", "tool", "tool_input", "decision", "approved_by",
                "result", "is_error", "duration_ms"]
        out = []
        for r in rows:
            d = dict(zip(keys, r))
            try:
                d["tool_input"] = json.loads(d["tool_input"]) if d["tool_input"] else {}
            except json.JSONDecodeError:
                pass
            out.append(d)
        return out
