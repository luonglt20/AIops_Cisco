"""
MerakiMind — Trend & Anomaly Detection DB
SQLite local — không cần cloud DB.
Ghi lại mọi sự cố và phát hiện thiết bị lỗi lặp lại.
"""
import sqlite3
import os
import threading
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trends.db")
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if not exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS incident_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                serial      TEXT NOT NULL,
                device_name TEXT,
                alert_type  TEXT,
                severity    TEXT,
                org_id      TEXT,
                net_id      TEXT,
                model       TEXT,
                firmware    TEXT,
                timestamp   TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_serial ON incident_log(serial);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON incident_log(timestamp);
        """)


def record_incident(
    serial: str,
    device_name: str = "",
    alert_type: str = "",
    severity: str = "MEDIUM",
    org_id: str = "",
    net_id: str = "",
    model: str = "",
    firmware: str = "",
):
    """Log a new incident occurrence."""
    init_db()
    ts = datetime.now(timezone.utc).isoformat()
    with _lock:
        with _get_conn() as conn:
            conn.execute(
                """INSERT INTO incident_log
                   (serial, device_name, alert_type, severity, org_id, net_id, model, firmware, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (serial, device_name, alert_type, severity, org_id, net_id, model, firmware, ts),
            )
    print(f"[TrendDB] Recorded incident: serial={serial}, type={alert_type}")


def get_incident_frequency(serial: str, window_hours: int = 24) -> int:
    """Return how many times this device has had an incident in the last N hours."""
    init_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM incident_log WHERE serial=? AND timestamp >= ?",
            (serial, cutoff),
        ).fetchone()
    return row["cnt"] if row else 0


def get_persistent_devices(threshold: int = 3, window_hours: int = 24) -> list:
    """
    Return list of devices that have had >= threshold incidents in the last N hours.
    Each entry: {serial, device_name, count, alert_types}
    """
    init_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT serial, device_name, model, COUNT(*) as cnt,
                      GROUP_CONCAT(DISTINCT alert_type) as alert_types
               FROM incident_log
               WHERE timestamp >= ?
               GROUP BY serial
               HAVING cnt >= ?
               ORDER BY cnt DESC
               LIMIT 20""",
            (cutoff, threshold),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_history(serial: str, limit: int = 10) -> list:
    """Return recent incidents for a specific device."""
    init_db()
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT alert_type, severity, timestamp
               FROM incident_log
               WHERE serial=?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (serial, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_org_stats(org_id: str, window_hours: int = 24) -> dict:
    """Return aggregate stats for an org in the last N hours."""
    init_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    with _get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM incident_log WHERE org_id=? AND timestamp >= ?",
            (org_id, cutoff),
        ).fetchone()["cnt"]
        most_troubled = conn.execute(
            """SELECT serial, device_name, COUNT(*) as cnt
               FROM incident_log WHERE org_id=? AND timestamp >= ?
               GROUP BY serial ORDER BY cnt DESC LIMIT 5""",
            (org_id, cutoff),
        ).fetchall()
    return {
        "total_incidents_24h": total,
        "most_troubled_devices": [dict(r) for r in most_troubled],
    }


def build_trend_context(serial: str, window_hours: int = 24) -> str:
    """
    Build a short Vietnamese text context about this device's incident history.
    Injected into agent blackboard before LLM analysis.
    """
    freq = get_incident_frequency(serial, window_hours)
    if freq == 0:
        return ""
    history = get_recent_history(serial, limit=5)
    history_str = ", ".join([f"{h['alert_type']} ({h['timestamp'][:10]})" for h in history])

    if freq >= 5:
        flag = "🔴 NGUY HIỂM — Lỗi lặp lại nghiêm trọng"
    elif freq >= 3:
        flag = "🟠 CẢNH BÁO — Lỗi tái lặp đáng lo ngại"
    else:
        flag = "🟡 CHÚ Ý — Đã có sự cố trước đó"

    return (
        f"{flag}: Thiết bị (serial={serial}) đã ghi nhận {freq} sự cố "
        f"trong {window_hours}h qua. "
        f"Lịch sử gần nhất: {history_str}."
    )
