"""SQLite 存储层：草稿（带 revision 乐观锁）与不可变版本。

- 每次写草稿都要求携带当前 revision，UPDATE ... WHERE revision = ?
  原子地完成“检查并递增”，并发下只有一个请求成功，其余得到 409。
- 版本表只插不改，(proof_id, version_no) 主键保证不可变与唯一。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS proofs (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    revision    INTEGER NOT NULL,
    tracks_json TEXT NOT NULL,
    cards_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    proof_id    TEXT NOT NULL REFERENCES proofs(id) ON DELETE CASCADE,
    version_no  INTEGER NOT NULL,
    title       TEXT NOT NULL,
    revision    INTEGER NOT NULL,
    tracks_json TEXT NOT NULL,
    cards_json  TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (proof_id, version_no)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Storage:
    def __init__(self, path: str):
        self.path = path
        self._write_lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    # ------------------------------------------------------------------ 草稿

    @staticmethod
    def _row_to_proof(row: sqlite3.Row, version_count: int = 0) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "revision": row["revision"],
            "tracks": json.loads(row["tracks_json"]),
            "cards": json.loads(row["cards_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version_count": version_count,
        }

    def create_proof(self, title: str, tracks: list, cards: list) -> dict:
        proof_id = uuid.uuid4().hex[:12]
        now = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO proofs (id, title, revision, tracks_json, cards_json, created_at, updated_at)"
                " VALUES (?, ?, 1, ?, ?, ?, ?)",
                (proof_id, title, json.dumps(tracks), json.dumps(cards), now, now),
            )
        return self.get_proof(proof_id)

    def list_proofs(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT p.*, COUNT(v.version_no) AS version_count"
                " FROM proofs p LEFT JOIN versions v ON v.proof_id = p.id"
                " GROUP BY p.id ORDER BY p.updated_at DESC"
            ).fetchall()
        return [self._row_to_proof(r, r["version_count"]) for r in rows]

    def get_proof(self, proof_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM proofs WHERE id = ?", (proof_id,)).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM versions WHERE proof_id = ?", (proof_id,)
            ).fetchone()["c"]
        return self._row_to_proof(row, count) if row else None

    def update_proof(
        self, proof_id: str, revision: int, title: str, tracks: list, cards: list
    ) -> tuple[str, Optional[dict]]:
        """乐观锁更新。返回 ("ok", proof) / ("conflict", current) / ("missing", None)。"""
        now = _now()
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE proofs SET title = ?, tracks_json = ?, cards_json = ?,"
                " revision = revision + 1, updated_at = ?"
                " WHERE id = ? AND revision = ?",
                (title, json.dumps(tracks), json.dumps(cards), now, proof_id, revision),
            )
            if cur.rowcount == 1:
                outcome = "ok"
            else:
                exists = conn.execute(
                    "SELECT 1 FROM proofs WHERE id = ?", (proof_id,)
                ).fetchone()
                outcome = "missing" if exists is None else "conflict"
        # 事务已提交，再读最新状态
        if outcome == "ok":
            return "ok", self.get_proof(proof_id)
        if outcome == "missing":
            return "missing", None
        return "conflict", self.get_proof(proof_id)

    def delete_proof(self, proof_id: str) -> bool:
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM proofs WHERE id = ?", (proof_id,))
            return cur.rowcount == 1

    # ------------------------------------------------------------------ 版本

    @staticmethod
    def _row_to_version(row: sqlite3.Row) -> dict:
        return {
            "proof_id": row["proof_id"],
            "version_no": row["version_no"],
            "title": row["title"],
            "revision": row["revision"],
            "tracks": json.loads(row["tracks_json"]),
            "cards": json.loads(row["cards_json"]),
            "note": row["note"],
            "created_at": row["created_at"],
        }

    def create_version(
        self, proof_id: str, revision: int, note: Optional[str]
    ) -> tuple[str, Optional[dict]]:
        """从指定 revision 发布不可变版本。返回 ("ok", version) / ("conflict", proof) / ("missing", None)。"""
        with self._write_lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            proof = conn.execute("SELECT * FROM proofs WHERE id = ?", (proof_id,)).fetchone()
            if proof is None:
                conn.rollback()
                return "missing", None
            if proof["revision"] != revision:
                conn.rollback()
                return "conflict", self.get_proof(proof_id)
            next_no = conn.execute(
                "SELECT COALESCE(MAX(version_no), 0) + 1 AS n FROM versions WHERE proof_id = ?",
                (proof_id,),
            ).fetchone()["n"]
            conn.execute(
                "INSERT INTO versions (proof_id, version_no, title, revision, tracks_json, cards_json, note, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proof_id,
                    next_no,
                    proof["title"],
                    proof["revision"],
                    proof["tracks_json"],
                    proof["cards_json"],
                    note,
                    _now(),
                ),
            )
            conn.commit()
        return "ok", self.get_version(proof_id, next_no)

    def list_versions(self, proof_id: str) -> Optional[list]:
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM proofs WHERE id = ?", (proof_id,)).fetchone() is None:
                return None
            rows = conn.execute(
                "SELECT * FROM versions WHERE proof_id = ? ORDER BY version_no", (proof_id,)
            ).fetchall()
        return [self._row_to_version(r) for r in rows]

    def get_version(self, proof_id: str, version_no: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM versions WHERE proof_id = ? AND version_no = ?",
                (proof_id, version_no),
            ).fetchone()
        return self._row_to_version(row) if row else None
