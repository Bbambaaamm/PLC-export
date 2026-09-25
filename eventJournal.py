"""Bounded asynchronous SQLite archive of observations, not guaranteed PLC events."""
import json
from contextlib import closing
import logging
import os
from pathlib import Path
import queue
import sqlite3
import threading
import time
import uuid

log = logging.getLogger(__name__)


class EventJournal:
    def __init__(self, path, capacity=5000, retention_days=7, max_rows=100000):
        self.path = Path(path)
        self.pending = queue.Queue(maxsize=capacity)
        self.retention_seconds = retention_days * 86400
        self.max_rows = max_rows
        self.session = uuid.uuid4().hex
        self.lock = threading.Lock()
        self.dropped = self.errors = self.written = 0
        self.healthy = False
        self.retry_batch = []
        self.stopping = threading.Event()
        self.thread = None

    def publish(self, event):
        # Freeze at publication: readers cannot mutate data waiting for disk.
        frozen = (event["observed_at"], event["kind"], event.get("station", ""),
                  event.get("box_id", ""), json.dumps(event.get("details", {}), ensure_ascii=False), self.session)
        try:
            self.pending.put_nowait(frozen)
        except queue.Full:
            with self.lock:
                self.dropped += 1

    def flush_once(self):
        if not self.retry_batch:
            for _ in range(200):
                try:
                    self.retry_batch.append(self.pending.get_nowait())
                except queue.Empty:
                    break
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=1)) as db, db:
                db.execute("PRAGMA journal_mode=WAL")
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1):
                    raise ValueError("Unsupported journal schema")
                db.execute("CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY, observed_at REAL NOT NULL, kind TEXT NOT NULL, station TEXT NOT NULL, box_id TEXT NOT NULL, details TEXT NOT NULL, session TEXT NOT NULL)")
                db.execute("CREATE INDEX IF NOT EXISTS obs_box_time ON observations(box_id, observed_at)")
                db.execute("CREATE INDEX IF NOT EXISTS obs_time ON observations(observed_at)")
                db.execute("PRAGMA user_version=1")
                db.executemany("INSERT INTO observations(observed_at,kind,station,box_id,details,session) VALUES (?,?,?,?,?,?)", self.retry_batch)
                db.execute("DELETE FROM observations WHERE observed_at < ?", (time.time() - self.retention_seconds,))
                db.execute("DELETE FROM observations WHERE id <= COALESCE((SELECT id FROM observations ORDER BY id DESC LIMIT 1 OFFSET ?), -1)", (self.max_rows,))
            with self.lock:
                self.healthy = True
                self.written += len(self.retry_batch)
            self.retry_batch = []
            return True
        except Exception:
            log.warning("Observation archive unavailable; bounded retry retained", exc_info=True)
            with self.lock:
                self.healthy = False
                self.errors += 1
            return False

    def start(self):
        if self.thread is not None:
            return
        def run():
            while not self.stopping.is_set():
                self.flush_once()
                self.stopping.wait(1)
            deadline = time.monotonic() + 2
            while (self.retry_batch or not self.pending.empty()) and time.monotonic() < deadline:
                if not self.flush_once():
                    break
        self.thread = threading.Thread(target=run, name="EventJournal", daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=3)

    def health(self):
        with self.lock:
            return {"healthy": int(self.healthy), "dropped_total": self.dropped,
                    "errors_total": self.errors, "written_total": self.written,
                    "pending": self.pending.qsize() + len(self.retry_batch)}

    def search(self, box_id="", since=None, until=None, limit=200):
        if not 1 <= limit <= 200 or len(box_id) > 64:
            raise ValueError("Invalid query limits")
        since = time.time() - 86400 if since is None else since
        until = time.time() if until is None else until
        if since > until:
            raise ValueError("since must precede until")
        # mode=ro forbids a UI query from creating a missing archive.
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM observations WHERE observed_at >= ? AND observed_at <= ? AND (? = '' OR box_id = ?) ORDER BY observed_at DESC, id DESC LIMIT ?",
                (since, until, box_id, box_id, limit),
            ).fetchall()
        return [dict(row, details=json.loads(row["details"])) for row in rows]


journal = EventJournal(os.getenv("EVENT_DB_PATH", "var/observations.sqlite3"))
