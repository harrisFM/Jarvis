"""Local memory: an episodic log of every turn plus a searchable store of facts (SQLite + FTS5).

This is the single-box baseline described in docs/JARVIS-PLAN.md §4.8. mem0/Graphiti can be
layered on later behind the same interface."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, path: Path | str) -> None:
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        c = self.conn
        c.execute(
            """CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, session TEXT,
                user_id TEXT, room TEXT, role TEXT NOT NULL, text TEXT NOT NULL)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, user_id TEXT,
                category TEXT, text TEXT NOT NULL, source TEXT DEFAULT 'user', confirmed INTEGER DEFAULT 1)"""
        )
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(text, category, content='facts', content_rowid='id')")
        c.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
              INSERT INTO facts_fts(rowid, text, category) VALUES (new.id, new.text, new.category); END;
            CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
              INSERT INTO facts_fts(facts_fts, rowid, text, category) VALUES('delete', old.id, old.text, old.category); END;
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, user_id TEXT,
                text TEXT NOT NULL, done INTEGER DEFAULT 0)"""
        )
        c.commit()

    # --- episodes -------------------------------------------------------
    def log_turn(self, session: str, user_id: str, room: str, role: str, text: str) -> None:
        self.conn.execute(
            "INSERT INTO episodes (ts,session,user_id,room,role,text) VALUES (?,?,?,?,?,?)",
            (time.time(), session, user_id, room, role, text),
        )
        self.conn.commit()

    def recent_turns(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM episodes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def forget_session(self, session: str) -> int:
        cur = self.conn.execute("DELETE FROM episodes WHERE session=?", (session,))
        self.conn.commit()
        return cur.rowcount

    # --- facts ------------------------------------------------------------
    def remember(self, text: str, user_id: str = "owner", category: str = "general",
                 source: str = "user", confirmed: bool = True) -> int:
        cur = self.conn.execute(
            "INSERT INTO facts (ts,user_id,category,text,source,confirmed) VALUES (?,?,?,?,?,?)",
            (time.time(), user_id, category, text.strip(), source, int(confirmed)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def recall(self, query: str, limit: int = 8, confirmed_only: bool = True) -> list[dict[str, Any]]:
        q = " OR ".join(_fts_terms(query))
        if not q:
            return self.list_facts(limit=limit, include_pending=not confirmed_only)
        where = "AND f.confirmed=1" if confirmed_only else ""
        rows = self.conn.execute(
            f"""SELECT f.id, f.ts, f.user_id, f.category, f.text, f.source, f.confirmed, bm25(facts_fts) AS score
                FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid
                WHERE facts_fts MATCH ? {where} ORDER BY score LIMIT ?""",
            (q, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_facts(self, limit: int = 200, include_pending: bool = True) -> list[dict[str, Any]]:
        where = "" if include_pending else "WHERE confirmed=1"
        rows = self.conn.execute(f"SELECT * FROM facts {where} ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def confirm_fact(self, fact_id: int) -> bool:
        cur = self.conn.execute("UPDATE facts SET confirmed=1 WHERE id=?", (fact_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def forget(self, fact_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM facts WHERE id=?", (fact_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # --- todos ------------------------------------------------------------
    def add_todo(self, text: str, user_id: str = "owner") -> int:
        cur = self.conn.execute("INSERT INTO todos (ts,user_id,text) VALUES (?,?,?)", (time.time(), user_id, text))
        self.conn.commit()
        return int(cur.lastrowid)

    def list_todos(self, include_done: bool = False) -> list[dict[str, Any]]:
        where = "" if include_done else "WHERE done=0"
        return [dict(r) for r in self.conn.execute(f"SELECT * FROM todos {where} ORDER BY id").fetchall()]

    def complete_todo(self, todo_id: int) -> bool:
        cur = self.conn.execute("UPDATE todos SET done=1 WHERE id=?", (todo_id,))
        self.conn.commit()
        return cur.rowcount > 0


def _fts_terms(query: str) -> list[str]:
    words = [w for w in "".join(ch if ch.isalnum() else " " for ch in query.lower()).split() if len(w) > 2]
    return [f'"{w}"' for w in words[:12]]
