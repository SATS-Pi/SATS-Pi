import sqlite3
import threading
import time

PENDING = "PENDING_PAYMENT"  # facture créée, en attente du paiement Lightning
PAYING_OUT = "PAYING_OUT"  # sats reçus, payout en cours
COMPLETED = "COMPLETED"  # MoMo envoyé
FAILED = "PAYOUT_FAILED"  # sats reçus mais envoi en échec -> reprise manuelle
EXPIRED = "EXPIRED"  # jamais payée

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
  id TEXT PRIMARY KEY,
  phone TEXT NOT NULL,
  country TEXT NOT NULL DEFAULT 'BJ',
  operator TEXT,
  firstname TEXT NOT NULL DEFAULT '',
  lastname TEXT NOT NULL DEFAULT '',
  local_number TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  amount_xof INTEGER NOT NULL,
  total_xof INTEGER NOT NULL,
  sats INTEGER NOT NULL,
  rate REAL NOT NULL,
  rate_source TEXT NOT NULL,
  invoice TEXT NOT NULL,
  payment_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  payout_ref TEXT,
  payout_id TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL,
  paid_at REAL,
  completed_at REAL
)
"""


class Store:
    """Petit stockage SQLite. Les changements d'état sont atomiques :
    c'est ce qui garantit qu'un paiement Lightning ne déclenche qu'UN seul payout."""

    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._exec(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Ajoute les colonnes manquantes d'une ancienne base (démo)."""
        have = {r["name"] for r in self._rows("PRAGMA table_info(links)")}
        wanted = {
            "country": "TEXT NOT NULL DEFAULT 'BJ'", "operator": "TEXT",
            "firstname": "TEXT NOT NULL DEFAULT ''", "lastname": "TEXT NOT NULL DEFAULT ''",
            "local_number": "TEXT NOT NULL DEFAULT ''", "payout_id": "TEXT",
            "attempts": "INTEGER NOT NULL DEFAULT 0",
        }
        for col, ddl in wanted.items():
            if col not in have:
                self._exec(f"ALTER TABLE links ADD COLUMN {col} {ddl}")

    def _exec(self, sql: str, args: tuple = ()) -> int:
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.rowcount

    def _rows(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def insert(self, link: dict) -> None:
        cols = ", ".join(link)  # noms de colonnes fixés par le code, jamais par l'utilisateur
        marks = ", ".join("?" * len(link))
        self._exec(f"INSERT INTO links ({cols}) VALUES ({marks})", tuple(link.values()))

    def get(self, link_id: str) -> dict | None:
        rows = self._rows("SELECT * FROM links WHERE id=?", (link_id,))
        return rows[0] if rows else None

    def pending(self) -> list[dict]:
        return self._rows("SELECT * FROM links WHERE status=?", (PENDING,))

    def claim_for_payout(self, link_id: str) -> bool:
        return (
            self._exec(
                "UPDATE links SET status=?, paid_at=? WHERE id=? AND status=?",
                (PAYING_OUT, time.time(), link_id, PENDING),
            )
            == 1
        )

    def claim_retry(self, link_id: str) -> bool:
        return (
            self._exec(
                "UPDATE links SET status=?, error=NULL, payout_id=NULL, attempts=attempts+1 "
                "WHERE id=? AND status=?",
                (PAYING_OUT, link_id, FAILED),
            )
            == 1
        )

    def paying_out_pending(self) -> list[dict]:
        """Envois lancés chez le prestataire mais pas encore au statut final."""
        return self._rows(
            "SELECT * FROM links WHERE status=? AND payout_id IS NOT NULL", (PAYING_OUT,)
        )

    def set_payout_id(self, link_id: str, payout_id: str) -> None:
        self._exec("UPDATE links SET payout_id=? WHERE id=? AND status=?", (payout_id, link_id, PAYING_OUT))

    def mark_completed(self, link_id: str, ref: str | None) -> None:
        self._exec(
            "UPDATE links SET status=?, payout_ref=?, completed_at=? WHERE id=? AND status=?",
            (COMPLETED, ref, time.time(), link_id, PAYING_OUT),
        )

    def mark_failed(self, link_id: str, error: str) -> None:
        self._exec(
            "UPDATE links SET status=?, error=? WHERE id=? AND status=?",
            (FAILED, error[:500], link_id, PAYING_OUT),
        )

    def mark_expired(self, link_id: str) -> None:
        self._exec("UPDATE links SET status=? WHERE id=? AND status=?", (EXPIRED, link_id, PENDING))
