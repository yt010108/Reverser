"""Durable task frontier and session activity for the web orchestrator."""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .security import validate_id
from .storage import utc_now


class TaskDB:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get(
            "REVERSER_STATE_DB", Path(__file__).resolve().parents[2] / ".private" / "web" / "state.sqlite"
        ))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    challenge_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'ready',
                    goal TEXT NOT NULL DEFAULT '', round INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS intents (
                    challenge_id TEXT NOT NULL, intent_id TEXT NOT NULL,
                    summary TEXT NOT NULL, parent_id TEXT, status TEXT NOT NULL,
                    owner TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (challenge_id, intent_id)
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL,
                    evidence_run INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                    verify_run INTEGER, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id TEXT NOT NULL,
                    session TEXT NOT NULL, role TEXT NOT NULL, intent_id TEXT,
                    kind TEXT NOT NULL, summary TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
                    tokens TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS activity_task_seq ON activity(challenge_id, seq);
                CREATE INDEX IF NOT EXISTS activity_session_seq ON activity(challenge_id, session, seq);
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def ensure_task(self, challenge_id: str, goal: str = "") -> dict[str, Any]:
        validate_id(challenge_id)
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO tasks(challenge_id,goal,updated_at) VALUES(?,?,?)",
                (challenge_id, goal, utc_now()),
            )
        return self.task(challenge_id)

    def task(self, challenge_id: str) -> dict[str, Any] | None:
        validate_id(challenge_id)
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE challenge_id=?", (challenge_id,)).fetchone()
        return dict(row) if row else None

    def active_tasks(self) -> list[str]:
        with self.connect() as db:
            rows = db.execute("SELECT challenge_id FROM tasks WHERE status IN ('running','verifying')").fetchall()
        return [str(row["challenge_id"]) for row in rows]

    def set_task(self, challenge_id: str, status: str, goal: str | None = None) -> None:
        if status not in {"ready", "running", "paused", "verifying", "solved", "local_verified", "unsolved", "failed"}:
            raise ValueError("Invalid task status")
        self.ensure_task(challenge_id)
        with self.connect() as db:
            if goal is None:
                db.execute("UPDATE tasks SET status=?,updated_at=? WHERE challenge_id=?",
                           (status, utc_now(), challenge_id))
            else:
                db.execute("UPDATE tasks SET status=?,goal=?,updated_at=? WHERE challenge_id=?",
                           (status, goal[:2000], utc_now(), challenge_id))

    def next_round(self, challenge_id: str) -> int:
        with self.connect() as db:
            db.execute("UPDATE tasks SET round=round+1,updated_at=? WHERE challenge_id=?",
                       (utc_now(), challenge_id))
            row = db.execute("SELECT round FROM tasks WHERE challenge_id=?", (challenge_id,)).fetchone()
        return int(row["round"])

    def sync_intents(self, challenge_id: str, intents: list[dict[str, Any]]) -> list[str]:
        """Import newly recorded planner intents without resetting assigned work."""
        added: list[str] = []
        with self.connect() as db:
            for item in intents:
                intent_id = str(item["id"])
                result = db.execute(
                    """INSERT OR IGNORE INTO intents
                       (challenge_id,intent_id,summary,parent_id,status,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (challenge_id, intent_id, str(item["summary"]), item.get("parent_id"),
                    item.get("status") if item.get("status") in {"done", "blocked", "open"} else "open",
                    item.get("created_at") or utc_now(), utc_now()),
                )
                if result.rowcount:
                    added.append(intent_id)
        return added

    def intents(self, challenge_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM intents WHERE challenge_id=? ORDER BY created_at,intent_id",
                              (challenge_id,)).fetchall()
        return [dict(row) for row in rows]

    def claim(self, challenge_id: str, owner: str) -> dict[str, Any] | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT i.* FROM intents i
                   LEFT JOIN intents p ON p.challenge_id=i.challenge_id AND p.intent_id=i.parent_id
                   WHERE i.challenge_id=? AND i.status='open'
                     AND (i.parent_id IS NULL OR p.status='done')
                   ORDER BY i.created_at,i.intent_id LIMIT 1""", (challenge_id,)
            ).fetchone()
            if not row:
                return None
            db.execute("UPDATE intents SET status='running',owner=?,updated_at=? WHERE challenge_id=? AND intent_id=?",
                       (owner, utc_now(), challenge_id, row["intent_id"]))
        return {**dict(row), "status": "running", "owner": owner}

    def has_claimable(self, challenge_id: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                """SELECT 1 FROM intents i
                   LEFT JOIN intents p ON p.challenge_id=i.challenge_id AND p.intent_id=i.parent_id
                   WHERE i.challenge_id=? AND i.status='open'
                     AND (i.parent_id IS NULL OR p.status='done') LIMIT 1""",
                (challenge_id,),
            ).fetchone()
        return row is not None

    def has_unplanned_hint(self, challenge_id: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                """SELECT 1 FROM activity
                   WHERE challenge_id=? AND kind='hint' AND seq >
                     coalesce((SELECT max(seq) FROM activity WHERE challenge_id=? AND kind='round'), 0)
                   LIMIT 1""", (challenge_id, challenge_id),
            ).fetchone()
        return row is not None

    def set_intent(self, challenge_id: str, intent_id: str, status: str) -> None:
        if status not in {"open", "running", "paused", "done", "blocked", "exhausted", "stopped"}:
            raise ValueError("Invalid intent status")
        with self.connect() as db:
            result = db.execute(
                "UPDATE intents SET status=?,owner=NULL,updated_at=? WHERE challenge_id=? AND intent_id=?",
                (status, utc_now(), challenge_id, intent_id),
            )
            if not result.rowcount:
                raise ValueError("Unknown intent")

    def reopen_running(self, challenge_id: str | None = None) -> None:
        with self.connect() as db:
            if challenge_id:
                db.execute("UPDATE intents SET status='open',owner=NULL,updated_at=? WHERE challenge_id=? AND status IN ('running','paused')",
                           (utc_now(), challenge_id))
            else:
                db.execute("UPDATE intents SET status='open',owner=NULL,updated_at=? WHERE status='running'",
                           (utc_now(),))

    def pause_running(self, challenge_id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE intents SET status='paused',owner=NULL,updated_at=? WHERE challenge_id=? AND status='running'",
                       (utc_now(), challenge_id))

    def add_candidate(self, challenge_id: str, intent_id: str, kind: str,
                      value: str, evidence_run: int) -> int:
        if kind not in {"flag", "local_solution"} or not value.strip() or len(value) > 1024:
            raise ValueError("Invalid candidate")
        with self.connect() as db:
            duplicate = db.execute(
                "SELECT id FROM candidates WHERE challenge_id=? AND kind=? AND value=? AND evidence_run=?",
                (challenge_id, kind, value, evidence_run),
            ).fetchone()
            if duplicate:
                return int(duplicate["id"])
            row = db.execute(
                """INSERT INTO candidates(challenge_id,intent_id,kind,value,evidence_run,created_at)
                   VALUES(?,?,?,?,?,?) RETURNING id""",
                (challenge_id, intent_id, kind, value, evidence_run, utc_now()),
            ).fetchone()
        return int(row["id"])

    def candidate(self, challenge_id: str, candidate_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM candidates WHERE challenge_id=? AND id=?",
                             (challenge_id, candidate_id)).fetchone()
        return dict(row) if row else None

    def candidates(self, challenge_id: str, *, include_value: bool = False) -> list[dict[str, Any]]:
        columns = "*" if include_value else "id,challenge_id,intent_id,kind,evidence_run,status,verify_run,created_at"
        with self.connect() as db:
            rows = db.execute(f"SELECT {columns} FROM candidates WHERE challenge_id=? ORDER BY id",
                              (challenge_id,)).fetchall()
        return [dict(row) for row in rows]

    def set_candidate(self, challenge_id: str, candidate_id: int, status: str,
                      verify_run: int | None = None) -> None:
        if status not in {"pending", "verified", "rejected"}:
            raise ValueError("Invalid candidate status")
        with self.connect() as db:
            result = db.execute("UPDATE candidates SET status=?,verify_run=? WHERE challenge_id=? AND id=?",
                                (status, verify_run, challenge_id, candidate_id))
            if not result.rowcount:
                raise ValueError("Unknown candidate")

    def append(self, challenge_id: str, session: str, role: str, kind: str,
               summary: str, detail: str = "", intent_id: str | None = None,
               tokens: dict[str, Any] | None = None) -> int:
        with self.connect() as db:
            row = db.execute(
                """INSERT INTO activity(challenge_id,session,role,intent_id,kind,summary,detail,tokens,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?) RETURNING seq""",
                (challenge_id, session, role, intent_id, kind, summary[:2000], detail[:20000],
                 json.dumps(tokens or {}, ensure_ascii=False), utc_now()),
            ).fetchone()
        return int(row["seq"])

    def activities(self, challenge_id: str, since: int = 0, session: str = "",
                   limit: int = 200) -> list[dict[str, Any]]:
        limit = min(500, max(1, limit))
        query = "SELECT * FROM activity WHERE challenge_id=? AND seq>?"
        args: list[Any] = [challenge_id, since]
        if session:
            query += " AND session=?"
            args.append(session)
        query += " ORDER BY seq LIMIT ?"
        args.append(limit)
        with self.connect() as db:
            rows = db.execute(query, args).fetchall()
        return [{**dict(row), "tokens": json.loads(row["tokens"])} for row in rows]

    def last_seq(self, challenge_id: str) -> int:
        with self.connect() as db:
            row = db.execute("SELECT coalesce(max(seq),0) AS seq FROM activity WHERE challenge_id=?",
                             (challenge_id,)).fetchone()
        return int(row["seq"])
