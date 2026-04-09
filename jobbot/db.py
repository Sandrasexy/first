"""SQLite база данных для хранения вакансий, откликов и сообщений."""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobbot.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vacancies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    hh_id        TEXT UNIQUE NOT NULL,
    role_alias   TEXT NOT NULL,
    title        TEXT,
    employer     TEXT,
    url          TEXT,
    salary_from  INTEGER,
    salary_to    INTEGER,
    salary_cur   TEXT,
    area         TEXT,
    published_at TEXT,
    raw_json     TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS covers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id  INTEGER NOT NULL REFERENCES vacancies(id),
    role_alias  TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id   INTEGER NOT NULL REFERENCES vacancies(id),
    role_alias   TEXT NOT NULL,
    resume_id    TEXT,
    cover_id     INTEGER REFERENCES covers(id),
    status       TEXT DEFAULT 'pending',
    applied_at   TEXT,
    error_msg    TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS inbox (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    hh_thread_id  TEXT UNIQUE,
    employer      TEXT,
    vacancy_title TEXT,
    last_message  TEXT,
    received_at   TEXT,
    status        TEXT DEFAULT 'new',
    created_at    TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


def vacancy_exists(hh_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM vacancies WHERE hh_id = ?", (hh_id,)
        ).fetchone()
        return row is not None


def save_vacancy(data: dict) -> int:
    """Сохраняет вакансию, возвращает её id."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO vacancies
               (hh_id, role_alias, title, employer, url,
                salary_from, salary_to, salary_cur, area, published_at, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["hh_id"], data["role_alias"], data["title"], data["employer"],
                data["url"], data.get("salary_from"), data.get("salary_to"),
                data.get("salary_cur"), data.get("area"), data.get("published_at"),
                data.get("raw_json"),
            ),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM vacancies WHERE hh_id = ?", (data["hh_id"],)
        ).fetchone()
        return row["id"]


def save_cover(vacancy_id: int, role_alias: str, text: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO covers (vacancy_id, role_alias, text) VALUES (?, ?, ?)",
            (vacancy_id, role_alias, text),
        )
        return cur.lastrowid


def get_vacancies_without_cover() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT v.* FROM vacancies v
               LEFT JOIN covers c ON c.vacancy_id = v.id
               WHERE c.id IS NULL
               ORDER BY v.created_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


def get_pending_applications() -> list:
    """Вакансии с одобренными письмами, на которые ещё не откликались (или были ошибки)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT v.*, c.text AS cover_text, c.id AS cover_id
               FROM vacancies v
               JOIN covers c ON c.vacancy_id = v.id
               WHERE c.status = 'approved'
               AND NOT EXISTS (
                   SELECT 1 FROM applications aa
                   WHERE aa.vacancy_id = v.id
                   AND aa.status IN ('applied', 'already_applied')
               )
               ORDER BY v.created_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


def save_application(vacancy_id: int, role_alias: str, resume_id: str,
                     cover_id: int, status: str, applied_at: str = None,
                     error_msg: str = None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO applications
               (vacancy_id, role_alias, resume_id, cover_id, status, applied_at, error_msg)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (vacancy_id, role_alias, resume_id, cover_id, status, applied_at, error_msg),
        )


def get_all_applications() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.*, v.title, v.employer, v.url, v.salary_from, v.salary_to,
                      v.salary_cur, v.area
               FROM applications a
               JOIN vacancies v ON v.id = a.vacancy_id
               ORDER BY a.created_at DESC""",
        ).fetchall()
        return [dict(r) for r in rows]
