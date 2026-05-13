import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DB_PATH = os.path.join(DATA_DIR, 'screener.db')

_JSON_FIELDS = {
    'skills', 'keywordMatches', 'missingKeywords', 'keywords',
    'scoringCriteria', 'strengths', 'weaknesses'
}

_RESUME_FIELDS = [
    'id', 'filename', 'originalFilename', 'name', 'email', 'phone',
    'skills', 'experience', 'education', 'summary', 'rawText',
    'keywordMatches', 'missingKeywords', 'parseStatus', 'matchStatus',
    'jdId', 'createdAt', 'parseError', 'textQuality'
]

_JD_FIELDS = ['id', 'title', 'description', 'keywords', 'scoringCriteria', 'createdAt']

_MATCH_FIELDS = [
    'id', 'resumeId', 'jdId', 'overallScore', 'skillMatch',
    'experienceMatch', 'educationMatch', 'keywordMatch', 'projectMatch',
    'keywordMatches', 'missingKeywords', 'strengths', 'weaknesses',
    'analysis', 'createdAt', 'confidence', 'scoringVersion',
    'thresholdPassed', 'thresholdChecks', 'textQuality'
]

_FAILED_UPLOAD_FIELDS = ['id', 'filename', 'error', 'createdAt']


def _get_conn() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL DEFAULT '',
                originalFilename TEXT DEFAULT '',
                name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                skills TEXT DEFAULT '[]',
                experience INTEGER DEFAULT 0,
                education TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                rawText TEXT DEFAULT '',
                keywordMatches TEXT DEFAULT '[]',
                missingKeywords TEXT DEFAULT '[]',
                parseStatus TEXT DEFAULT 'parsing',
                matchStatus TEXT,
                jdId TEXT,
                createdAt TEXT NOT NULL,
                parseError TEXT,
                textQuality REAL DEFAULT 1.0
            );

            CREATE TABLE IF NOT EXISTS jds (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                description TEXT DEFAULT '',
                keywords TEXT DEFAULT '[]',
                scoringCriteria TEXT DEFAULT '[]',
                createdAt TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS match_results (
                id TEXT PRIMARY KEY,
                resumeId TEXT NOT NULL,
                jdId TEXT NOT NULL,
                overallScore REAL DEFAULT 0,
                skillMatch REAL DEFAULT 0,
                experienceMatch REAL DEFAULT 0,
                educationMatch REAL DEFAULT 0,
                keywordMatch REAL DEFAULT 0,
                projectMatch REAL DEFAULT 0,
                keywordMatches TEXT DEFAULT '[]',
                missingKeywords TEXT DEFAULT '[]',
                strengths TEXT DEFAULT '[]',
                weaknesses TEXT DEFAULT '[]',
                analysis TEXT DEFAULT '',
                createdAt TEXT NOT NULL,
                confidence REAL DEFAULT NULL,
                scoringVersion TEXT DEFAULT NULL,
                thresholdPassed INTEGER DEFAULT NULL,
                thresholdChecks TEXT DEFAULT NULL,
                textQuality REAL DEFAULT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_match_resume_jd ON match_results(resumeId, jdId);
            CREATE INDEX IF NOT EXISTS idx_match_jd ON match_results(jdId);
            CREATE INDEX IF NOT EXISTS idx_match_resume ON match_results(resumeId);
            CREATE INDEX IF NOT EXISTS idx_resume_jd ON resumes(jdId);

            CREATE TABLE IF NOT EXISTS failed_uploads (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL DEFAULT '',
                error TEXT DEFAULT '',
                createdAt TEXT NOT NULL
            );
        """)
    finally:
        conn.close()


def _migrate_schema():
    """Idempotent schema migration: add columns if missing (run on every start)."""
    conn = _get_conn()
    try:
        _safe_add_column(conn, 'resumes', 'textQuality', 'REAL DEFAULT 1.0')
        _safe_add_column(conn, 'match_results', 'confidence', 'REAL DEFAULT NULL')
        _safe_add_column(conn, 'match_results', 'scoringVersion', 'TEXT DEFAULT NULL')
        _safe_add_column(conn, 'match_results', 'thresholdPassed', 'INTEGER DEFAULT NULL')
        _safe_add_column(conn, 'match_results', 'thresholdChecks', 'TEXT DEFAULT NULL')
        _safe_add_column(conn, 'match_results', 'textQuality', 'REAL DEFAULT NULL')
    finally:
        conn.close()


def _safe_add_column(conn, table: str, column: str, col_type: str):
    """Add a column if it doesn't already exist (idempotent)."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # column already exists


def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    d = dict(row)
    for key in _JSON_FIELDS:
        if key in d and isinstance(d[key], str) and d[key]:
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
    return d


def _rows_to_list(rows: List[sqlite3.Row]) -> List[dict]:
    return [_row_to_dict(r) for r in rows]


def _serialize(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _insert(table: str, fields: list, data: dict) -> dict:
    conn = _get_conn()
    try:
        cols = [f for f in fields if f in data]
        vals = [_serialize(data[f]) for f in cols]
        placeholders = ','.join(['?' for _ in cols])
        col_names = ','.join(cols)
        conn.execute(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
            vals
        )
        conn.commit()
        return data
    finally:
        conn.close()


def _update(table: str, fields: list, item_id: str, updates: dict) -> Optional[dict]:
    conn = _get_conn()
    try:
        set_cols = [f for f in fields if f in updates and f != 'id']
        if not set_cols:
            return _get_by_id(table, item_id)
        set_clause = ','.join(f"{c}=?" for c in set_cols)
        vals = [_serialize(updates[c]) for c in set_cols]
        vals.append(item_id)
        conn.execute(
            f"UPDATE {table} SET {set_clause} WHERE id=?",
            vals
        )
        conn.commit()
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def _get_by_id(table: str, item_id: str) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def _delete_by_id(table: str, item_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Resume ──────────────────────────────────────────────────────────

def save_resume(resume_data: Dict[str, Any]) -> Dict[str, Any]:
    resume_id = str(uuid.uuid4())
    resume = {
        'id': resume_id,
        **resume_data,
        'createdAt': datetime.now().isoformat()
    }
    return _insert('resumes', _RESUME_FIELDS, resume)


def get_all_resumes() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM resumes ORDER BY createdAt DESC").fetchall()
        return _rows_to_list(rows)
    finally:
        conn.close()


def get_all_resumes_paginated(page: int = 1, page_size: int = 20, jd_id: Optional[str] = None):
    """Returns (items, total_count) with LIMIT/OFFSET pagination."""
    conn = _get_conn()
    try:
        offset = (page - 1) * page_size
        conditions = []
        params: list = []
        if jd_id:
            conditions.append("jdId=?")
            params.append(jd_id)
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        count_row = conn.execute(
            f"SELECT COUNT(*) FROM resumes {where_clause}", params
        ).fetchone()
        total = count_row[0]

        rows = conn.execute(
            f"SELECT * FROM resumes {where_clause} ORDER BY createdAt DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        ).fetchall()
        return _rows_to_list(rows), total
    finally:
        conn.close()


def get_resume_by_id(resume_id: str) -> Optional[Dict[str, Any]]:
    return _get_by_id('resumes', resume_id)


def update_resume(resume_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _update('resumes', _RESUME_FIELDS, resume_id, updates)


def delete_resume(resume_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM resumes WHERE id=?", (resume_id,))
        conn.execute("DELETE FROM match_results WHERE resumeId=?", (resume_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── JD ──────────────────────────────────────────────────────────────

def save_jd(jd_data: Dict[str, Any]) -> Dict[str, Any]:
    jd_id = str(uuid.uuid4())
    jd = {
        'id': jd_id,
        **jd_data,
        'createdAt': datetime.now().isoformat()
    }
    return _insert('jds', _JD_FIELDS, jd)


def get_all_jds() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM jds ORDER BY createdAt DESC").fetchall()
        return _rows_to_list(rows)
    finally:
        conn.close()


def get_all_jds_paginated(page: int = 1, page_size: int = 50):
    """Returns (items, total_count) with LIMIT/OFFSET pagination."""
    conn = _get_conn()
    try:
        offset = (page - 1) * page_size
        count_row = conn.execute("SELECT COUNT(*) FROM jds").fetchone()
        total = count_row[0]
        rows = conn.execute(
            "SELECT * FROM jds ORDER BY createdAt DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        ).fetchall()
        return _rows_to_list(rows), total
    finally:
        conn.close()


def get_jd_by_id(jd_id: str) -> Optional[Dict[str, Any]]:
    return _get_by_id('jds', jd_id)


def get_jd() -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM jds LIMIT 1").fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_jd(jd_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _update('jds', _JD_FIELDS, jd_id, updates)


def delete_jd(jd_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM jds WHERE id=?", (jd_id,))
        conn.execute("UPDATE resumes SET jdId=NULL WHERE jdId=?", (jd_id,))
        conn.execute("DELETE FROM match_results WHERE jdId=?", (jd_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Match Results ───────────────────────────────────────────────────

def save_match_result(match_result_data: Dict[str, Any]) -> Dict[str, Any]:
    conn = _get_conn()
    try:
        resume_id = match_result_data.get('resumeId')
        jd_id = match_result_data.get('jdId')
        existing = None
        if resume_id and jd_id:
            row = conn.execute(
                "SELECT * FROM match_results WHERE resumeId=? AND jdId=?",
                (resume_id, jd_id)
            ).fetchone()
            if row is not None:
                existing = dict(row)

        match_result = {
            **match_result_data,
            'createdAt': datetime.now().isoformat()
        }

        if existing is not None:
            match_result['id'] = existing.get('id', str(uuid.uuid4()))
            set_cols = [f for f in _MATCH_FIELDS if f != 'id']
            set_clause = ','.join(f"{c}=?" for c in set_cols)
            vals = [_serialize(match_result.get(c)) for c in set_cols]
            vals.append(match_result['id'])
            conn.execute(
                f"UPDATE match_results SET {set_clause} WHERE id=?",
                vals
            )
        else:
            match_result['id'] = str(uuid.uuid4())
            cols = [f for f in _MATCH_FIELDS if f in match_result]
            vals = [_serialize(match_result[f]) for f in cols]
            placeholders = ','.join(['?' for _ in cols])
            col_names = ','.join(cols)
            conn.execute(
                f"INSERT INTO match_results ({col_names}) VALUES ({placeholders})",
                vals
            )

        conn.commit()
        return match_result
    finally:
        conn.close()


def get_all_match_results() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM match_results ORDER BY createdAt DESC").fetchall()
        return _rows_to_list(rows)
    finally:
        conn.close()


def get_match_results_by_jd_id(jd_id: str) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM match_results WHERE jdId=? ORDER BY overallScore DESC",
            (jd_id,)
        ).fetchall()
        return _rows_to_list(rows)
    finally:
        conn.close()


def get_match_result_by_resume_and_jd(resume_id: str, jd_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM match_results WHERE resumeId=? AND jdId=?",
            (resume_id, jd_id)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_match_result_by_resume_id(resume_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM match_results WHERE resumeId=? LIMIT 1",
            (resume_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_match_results_by_jd_id(jd_id: str):
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM match_results WHERE jdId=?", (jd_id,))
        conn.commit()
    finally:
        conn.close()


def delete_match_result(resume_id: str, jd_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM match_results WHERE resumeId=? AND jdId=?",
            (resume_id, jd_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ── Failed Uploads ──────────────────────────────────────────────────

def save_failed_upload(filename: str, error: str) -> Dict[str, Any]:
    record = {
        'id': str(uuid.uuid4()),
        'filename': filename,
        'error': error,
        'createdAt': datetime.now().isoformat()
    }
    return _insert('failed_uploads', _FAILED_UPLOAD_FIELDS, record)


def get_all_failed_uploads() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM failed_uploads ORDER BY createdAt DESC").fetchall()
        return _rows_to_list(rows)
    finally:
        conn.close()


def delete_failed_upload(failed_id: str) -> bool:
    return _delete_by_id('failed_uploads', failed_id)


def delete_failed_uploads_by_filename(filename: str) -> int:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM failed_uploads WHERE filename=?", (filename,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ── Migration ───────────────────────────────────────────────────────

def _migrate_from_json():
    data_file = os.path.join(DATA_DIR, 'data.json')
    match_file = os.path.join(DATA_DIR, 'match_results.json')

    data = None
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = None

    match_results_data = None
    if os.path.exists(match_file):
        try:
            with open(match_file, 'r', encoding='utf-8') as f:
                match_results_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            match_results_data = None

    if not data and not match_results_data:
        return

    conn = _get_conn()
    try:
        if data:
            if 'jd' in data and 'jds' not in data:
                old_match = data.pop('matchResults', [])
                if data['jd']:
                    data['jds'] = [data['jd']]
                else:
                    data['jds'] = []
                del data['jd']
                if not match_results_data and old_match:
                    match_results_data = old_match

            for resume in data.get('resumes', []):
                cols = [f for f in _RESUME_FIELDS if f in resume]
                vals = [_serialize(resume[f]) for f in cols]
                placeholders = ','.join(['?' for _ in cols])
                col_names = ','.join(cols)
                conn.execute(
                    f"INSERT OR IGNORE INTO resumes ({col_names}) VALUES ({placeholders})",
                    vals
                )

            for jd in data.get('jds', []):
                cols = [f for f in _JD_FIELDS if f in jd]
                vals = [_serialize(jd[f]) for f in cols]
                placeholders = ','.join(['?' for _ in cols])
                col_names = ','.join(cols)
                conn.execute(
                    f"INSERT OR IGNORE INTO jds ({col_names}) VALUES ({placeholders})",
                    vals
                )

            for failed in data.get('failedUploads', []):
                cols = [f for f in _FAILED_UPLOAD_FIELDS if f in failed]
                vals = [_serialize(failed[f]) for f in cols]
                placeholders = ','.join(['?' for _ in cols])
                col_names = ','.join(cols)
                conn.execute(
                    f"INSERT OR IGNORE INTO failed_uploads ({col_names}) VALUES ({placeholders})",
                    vals
                )

        if match_results_data:
            for mr in match_results_data:
                cols = [f for f in _MATCH_FIELDS if f in mr]
                vals = [_serialize(mr[f]) for f in cols]
                placeholders = ','.join(['?' for _ in cols])
                col_names = ','.join(cols)
                conn.execute(
                    f"INSERT OR IGNORE INTO match_results ({col_names}) VALUES ({placeholders})",
                    vals
                )

        conn.commit()
    finally:
        conn.close()


def _is_db_initialized() -> bool:
    if not os.path.exists(DB_PATH):
        return False
    conn = _get_conn()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('resumes', 'jds', 'match_results', 'failed_uploads')"
        ).fetchall()
        return len(tables) == 4
    except Exception:
        return False
    finally:
        conn.close()


# ── Legacy compatibility ────────────────────────────────────────────

# Keep backward-compatible aliases for code that may reference these
def load_data() -> Dict[str, Any]:
    """Legacy: return all data as dict (mimics old JSON format)."""
    return {
        'resumes': get_all_resumes(),
        'jds': get_all_jds(),
        'failedUploads': get_all_failed_uploads()
    }


# Initialize DB and migrate on first import
if not _is_db_initialized():
    _init_db()
    _migrate_from_json()

# Always run schema migration (idempotent) on startup
_migrate_schema()
