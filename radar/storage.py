from __future__ import annotations

import json
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, expires TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS reports(day TEXT PRIMARY KEY, status TEXT, payload TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS deliveries(day TEXT, part TEXT, state TEXT, message_id INTEGER,
              PRIMARY KEY(day,part));
            CREATE TABLE IF NOT EXISTS costs(day TEXT, request_id TEXT PRIMARY KEY,
              amount REAL, reserved REAL, detail TEXT);
            CREATE TABLE IF NOT EXISTS subscription_calls(id TEXT PRIMARY KEY, day TEXT, purpose TEXT, state TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, day TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS report_versions(id TEXT PRIMARY KEY, day TEXT, payload TEXT);
            """)

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def cached(self, key):
        with self.db() as db:
            row = db.execute("SELECT payload,expires FROM cache WHERE key=?", (key,)).fetchone()
        if row and datetime.fromisoformat(row[1]) > datetime.now(timezone.utc):
            return json.loads(row[0])
        return None

    def cache(self, key, value, seconds=3600):
        expires = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (key, expires, json.dumps(value, allow_nan=False)))

    def report(self, day):
        with self.db() as db:
            row = db.execute("SELECT payload FROM reports WHERE day=?", (day,)).fetchone()
        return json.loads(row[0]) if row else None

    def previous(self, day):
        with self.db() as db:
            row = db.execute("SELECT payload FROM reports WHERE day<? ORDER BY day DESC LIMIT 1", (day,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_report(self, day, report):
        with self.db() as db:
            if report.get('snapshot_id'):
                db.execute('INSERT OR IGNORE INTO report_versions VALUES(?,?,?)',
                           (hashlib.sha256(json.dumps(report,sort_keys=True,allow_nan=False).encode()).hexdigest(),day,json.dumps(report,allow_nan=False)))
            db.execute("INSERT OR REPLACE INTO reports VALUES(?,?,?,?)",
                       (day, report["status"], json.dumps(report, allow_nan=False), datetime.now(timezone.utc).isoformat()))

    def save_snapshot(self, identifier, day, payload):
        with self.db() as db:
            db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?,?)',(identifier,day,json.dumps(payload,allow_nan=False)))

    def versions(self, day):
        with self.db() as db:
            rows=db.execute('SELECT id FROM report_versions WHERE day=? ORDER BY rowid DESC',(day,)).fetchall()
        return [r[0] for r in rows]

    def report_version(self, identifier):
        with self.db() as db:
            row=db.execute('SELECT payload FROM report_versions WHERE id=?',(identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def claim_subscription_call(self, day, identifier, purpose, limit):
        from .local_ai import LocalAIError
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM subscription_calls WHERE id=?',(identifier,)).fetchone():
                raise LocalAIError('Tentativa Codex já registrada sem cache utilizável; conferir histórico antes de repetir.')
            count=db.execute('SELECT COUNT(*) FROM subscription_calls WHERE day=?',(day,)).fetchone()[0]
            if count>=limit:raise LocalAIError('Limite diário local de chamadas Codex atingido; nenhuma API paga será usada.')
            db.execute('INSERT INTO subscription_calls VALUES(?,?,?, ?,?)',(identifier,day,purpose,'started','{}'))

    def finish_subscription_call(self, identifier, state, detail):
        with self.db() as db:
            db.execute('UPDATE subscription_calls SET state=?,detail=? WHERE id=?',(state,json.dumps(detail),identifier))

    def subscription_usage(self, day):
        with self.db() as db:
            return [{'state':state,'calls':count} for state,count in db.execute('SELECT state,COUNT(*) FROM subscription_calls WHERE day=? GROUP BY state',(day,))]

    def claim_delivery(self, day, part):
        # Claim before network I/O. An ambiguous timeout remains 'sending' for manual reconciliation.
        with self.db() as db:
            result = db.execute("INSERT OR IGNORE INTO deliveries VALUES(?,?,'sending',NULL)", (day, part))
            return result.rowcount == 1

    def sent(self, day, part, message_id):
        with self.db() as db:
            db.execute("UPDATE deliveries SET state='sent',message_id=? WHERE day=? AND part=?",
                       (message_id, day, part))

    def release_delivery(self, day, part):
        with self.db() as db:
            db.execute("DELETE FROM deliveries WHERE day=? AND part=? AND state='sending'", (day, part))

    def delivery_states(self, day):
        with self.db() as db:
            return dict(db.execute("SELECT part,state FROM deliveries WHERE day=?", (day,)))

    def reserve(self, day, request_id, upper_bound, budget):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            spent = db.execute("SELECT COALESCE(SUM(MAX(amount,reserved)),0) FROM costs WHERE day=?", (day,)).fetchone()[0]
            if spent + upper_bound > budget:
                raise BudgetExceeded("Orçamento diário insuficiente para reservar a próxima pesquisa")
            db.execute("INSERT INTO costs VALUES(?,?,0,?,?)", (day, request_id, upper_bound, "reservado"))

    def settle(self, request_id, amount, detail):
        with self.db() as db:
            db.execute("UPDATE costs SET amount=?,reserved=0,detail=? WHERE request_id=?",
                       (amount, json.dumps(detail), request_id))

    def cost(self, day):
        with self.db() as db:
            return db.execute("SELECT COALESCE(SUM(amount),0),COALESCE(SUM(reserved),0) FROM costs WHERE day=?", (day,)).fetchone()
