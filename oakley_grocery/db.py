"""SQLite database — products, preferences, lists, orders, price history."""

from __future__ import annotations

import sqlite3
from typing import Optional

from oakley_grocery.common.config import Config

_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """Get or create a SQLite connection with WAL mode."""
    global _conn
    if _conn is not None:
        return _conn

    Config.ensure_dirs()
    _conn = sqlite3.connect(str(Config.db_path), timeout=10)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS preferences (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            generic_name    TEXT UNIQUE NOT NULL,
            stockcode       INTEGER NOT NULL,
            product_name    TEXT NOT NULL,
            brand           TEXT,
            package_size    TEXT,
            purchase_count  INTEGER NOT NULL DEFAULT 1,
            last_price      REAL,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lists (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'active',
            total_estimate  REAL,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS list_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id         INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
            generic_name    TEXT NOT NULL,
            quantity        INTEGER NOT NULL DEFAULT 1,
            unit            TEXT,
            stockcode       INTEGER,
            product_name    TEXT,
            price           REAL,
            resolved        INTEGER NOT NULL DEFAULT 0,
            checked         INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id         INTEGER REFERENCES lists(id),
            total_estimate  REAL,
            total_paid      REAL,
            item_count      INTEGER NOT NULL DEFAULT 0,
            store           TEXT DEFAULT 'woolworths',
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id        INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            generic_name    TEXT NOT NULL,
            stockcode       INTEGER,
            product_name    TEXT,
            brand           TEXT,
            quantity        INTEGER NOT NULL DEFAULT 1,
            price           REAL,
            on_special      INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stockcode       INTEGER NOT NULL,
            product_name    TEXT NOT NULL,
            price           REAL NOT NULL,
            on_special      INTEGER NOT NULL DEFAULT 0,
            recorded_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_list_items_list_id ON list_items(list_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_price_history_stockcode ON price_history(stockcode);
        CREATE INDEX IF NOT EXISTS idx_preferences_generic ON preferences(generic_name);
        CREATE INDEX IF NOT EXISTS idx_lists_status ON lists(status);
    """)


# ─── Preferences CRUD ────────────────────────────────────────────────────────

def get_preference(generic_name: str) -> Optional[dict]:
    """Get a preference by generic name."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM preferences WHERE generic_name = ? LIMIT 1",
        (generic_name.lower().strip(),),
    ).fetchone()
    return dict(row) if row else None


def get_all_preferences() -> list[dict]:
    """Get all preferences."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM preferences ORDER BY purchase_count DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def save_preference(generic_name: str, stockcode: int, product_name: str,
                    brand: Optional[str] = None, package_size: Optional[str] = None,
                    price: Optional[float] = None) -> int:
    """Save or update a product preference. Returns row id."""
    conn = _get_conn()
    generic = generic_name.lower().strip()
    existing = get_preference(generic)

    if existing:
        conn.execute(
            """UPDATE preferences SET stockcode = ?, product_name = ?, brand = ?,
               package_size = ?, purchase_count = purchase_count + 1,
               last_price = COALESCE(?, last_price),
               updated_at = datetime('now')
               WHERE generic_name = ?""",
            (stockcode, product_name, brand, package_size, price, generic),
        )
        conn.commit()
        return existing["id"]
    else:
        cursor = conn.execute(
            """INSERT INTO preferences (generic_name, stockcode, product_name,
               brand, package_size, last_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (generic, stockcode, product_name, brand, package_size, price),
        )
        conn.commit()
        return cursor.lastrowid


def delete_preference(generic_name: str) -> bool:
    """Delete a preference. Returns True if deleted."""
    conn = _get_conn()
    cursor = conn.execute(
        "DELETE FROM preferences WHERE generic_name = ?",
        (generic_name.lower().strip(),),
    )
    conn.commit()
    return cursor.rowcount > 0


def search_preferences(query: str) -> list[dict]:
    """Search preferences by generic name (substring match)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM preferences WHERE generic_name LIKE ? ORDER BY purchase_count DESC",
        (f"%{query.lower().strip()}%",),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Lists CRUD ──────────────────────────────────────────────────────────────

def create_list(name: str) -> int:
    """Create a new shopping list. Returns list id."""
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO lists (name) VALUES (?)",
        (name,),
    )
    conn.commit()
    return cursor.lastrowid


def get_list(list_id: int) -> Optional[dict]:
    """Get a list by id."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM lists WHERE id = ? LIMIT 1",
        (list_id,),
    ).fetchone()
    return dict(row) if row else None


def get_lists(status: Optional[str] = None) -> list[dict]:
    """Get all lists, optionally filtered by status."""
    conn = _get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM lists WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM lists ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_list_status(list_id: int, status: str, total_estimate: Optional[float] = None) -> bool:
    """Update a list's status."""
    conn = _get_conn()
    if total_estimate is not None:
        cursor = conn.execute(
            "UPDATE lists SET status = ?, total_estimate = ?, updated_at = datetime('now') WHERE id = ?",
            (status, total_estimate, list_id),
        )
    else:
        cursor = conn.execute(
            "UPDATE lists SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, list_id),
        )
    conn.commit()
    return cursor.rowcount > 0


def delete_list(list_id: int) -> bool:
    """Delete a list and its items. Returns True if deleted."""
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
    conn.commit()
    return cursor.rowcount > 0


# ─── List Items CRUD ─────────────────────────────────────────────────────────

def add_list_item(list_id: int, generic_name: str, quantity: int = 1,
                  unit: Optional[str] = None) -> int:
    """Add an item to a list. Returns item id."""
    conn = _get_conn()
    generic = generic_name.lower().strip()

    # Check for existing item — merge quantities
    existing = conn.execute(
        "SELECT * FROM list_items WHERE list_id = ? AND generic_name = ?",
        (list_id, generic),
    ).fetchone()

    if existing:
        new_qty = existing["quantity"] + quantity
        conn.execute(
            "UPDATE list_items SET quantity = ? WHERE id = ?",
            (new_qty, existing["id"]),
        )
        conn.commit()
        return existing["id"]

    cursor = conn.execute(
        """INSERT INTO list_items (list_id, generic_name, quantity, unit)
           VALUES (?, ?, ?, ?)""",
        (list_id, generic, quantity, unit),
    )
    conn.commit()
    return cursor.lastrowid


def get_list_items(list_id: int) -> list[dict]:
    """Get all items in a list."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM list_items WHERE list_id = ? ORDER BY id ASC",
        (list_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_list_item(item_id: int, **kwargs) -> bool:
    """Update a list item's fields."""
    conn = _get_conn()
    allowed = {"stockcode", "product_name", "price", "resolved", "checked", "quantity"}
    sets = []
    values = []
    for key, val in kwargs.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(val)

    if not sets:
        return False

    values.append(item_id)
    sql = f"UPDATE list_items SET {', '.join(sets)} WHERE id = ?"
    cursor = conn.execute(sql, values)
    conn.commit()
    return cursor.rowcount > 0


def remove_list_item(list_id: int, generic_name: str) -> bool:
    """Remove an item from a list by generic name."""
    conn = _get_conn()
    cursor = conn.execute(
        "DELETE FROM list_items WHERE list_id = ? AND generic_name = ?",
        (list_id, generic_name.lower().strip()),
    )
    conn.commit()
    return cursor.rowcount > 0


# ─── Orders CRUD ─────────────────────────────────────────────────────────────

def create_order(list_id: Optional[int], total_estimate: Optional[float],
                 total_paid: Optional[float], item_count: int,
                 store: str = "woolworths", notes: Optional[str] = None) -> int:
    """Create an order record. Returns order id."""
    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO orders (list_id, total_estimate, total_paid, item_count, store, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (list_id, total_estimate, total_paid, item_count, store, notes),
    )
    conn.commit()
    return cursor.lastrowid


def add_order_item(order_id: int, generic_name: str, stockcode: Optional[int],
                   product_name: Optional[str], brand: Optional[str],
                   quantity: int, price: Optional[float],
                   on_special: bool = False) -> int:
    """Add an item to an order. Returns item id."""
    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO order_items (order_id, generic_name, stockcode, product_name,
           brand, quantity, price, on_special)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (order_id, generic_name, stockcode, product_name, brand,
         quantity, price, 1 if on_special else 0),
    )
    conn.commit()
    return cursor.lastrowid


def get_orders(limit: int = 20, days: Optional[int] = None) -> list[dict]:
    """Get orders, optionally filtered by recency."""
    conn = _get_conn()
    if days:
        rows = conn.execute(
            """SELECT * FROM orders
               WHERE created_at >= datetime('now', ? || ' days')
               ORDER BY created_at DESC LIMIT ?""",
            (f"-{days}", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_order(order_id: int) -> Optional[dict]:
    """Get an order by id."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM orders WHERE id = ? LIMIT 1",
        (order_id,),
    ).fetchone()
    return dict(row) if row else None


def get_order_items(order_id: int) -> list[dict]:
    """Get items for an order."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC",
        (order_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Price History ───────────────────────────────────────────────────────────

def record_price(stockcode: int, product_name: str, price: float,
                 on_special: bool = False) -> int:
    """Record a price observation. Returns row id."""
    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO price_history (stockcode, product_name, price, on_special)
           VALUES (?, ?, ?, ?)""",
        (stockcode, product_name, price, 1 if on_special else 0),
    )
    conn.commit()
    return cursor.lastrowid


def get_price_history(stockcode: Optional[int] = None, days: int = 90,
                      limit: int = 50) -> list[dict]:
    """Get price history, optionally for a specific product."""
    conn = _get_conn()
    if stockcode:
        rows = conn.execute(
            """SELECT * FROM price_history
               WHERE stockcode = ? AND recorded_at >= datetime('now', ? || ' days')
               ORDER BY recorded_at DESC LIMIT ?""",
            (stockcode, f"-{days}", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM price_history
               WHERE recorded_at >= datetime('now', ? || ' days')
               ORDER BY recorded_at DESC LIMIT ?""",
            (f"-{days}", limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ─── Stats helpers ───────────────────────────────────────────────────────────

def count_preferences() -> int:
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) FROM preferences").fetchone()
    return row[0]


def count_lists(status: Optional[str] = None) -> int:
    conn = _get_conn()
    if status:
        row = conn.execute("SELECT COUNT(*) FROM lists WHERE status = ?", (status,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM lists").fetchone()
    return row[0]


def count_orders() -> int:
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) FROM orders").fetchone()
    return row[0]


def get_frequent_items(min_orders: int = 3, lookback: int = 10) -> list[dict]:
    """Get items that appear frequently in recent orders.
    Returns items appearing in min_orders+ of the last 'lookback' orders."""
    conn = _get_conn()

    # Get the last N order IDs
    order_ids = conn.execute(
        "SELECT id FROM orders ORDER BY created_at DESC LIMIT ?",
        (lookback,),
    ).fetchall()

    if not order_ids:
        return []

    ids = [r["id"] for r in order_ids]
    placeholders = ",".join("?" * len(ids))

    rows = conn.execute(
        f"""SELECT generic_name, COUNT(DISTINCT order_id) as frequency,
                   MAX(product_name) as product_name, MAX(brand) as brand,
                   MAX(stockcode) as stockcode, AVG(price) as avg_price,
                   SUM(quantity) as total_qty
            FROM order_items
            WHERE order_id IN ({placeholders})
            GROUP BY generic_name
            HAVING frequency >= ?
            ORDER BY frequency DESC, total_qty DESC""",
        (*ids, min_orders),
    ).fetchall()
    return [dict(r) for r in rows]


def get_spending_stats(days: int = 30) -> dict:
    """Get spending statistics for a period."""
    conn = _get_conn()
    row = conn.execute(
        """SELECT COUNT(*) as order_count,
                  COALESCE(SUM(total_paid), 0) as total_spent,
                  COALESCE(AVG(total_paid), 0) as avg_order,
                  COALESCE(MAX(total_paid), 0) as max_order,
                  COALESCE(MIN(total_paid), 0) as min_order
           FROM orders
           WHERE total_paid IS NOT NULL
             AND created_at >= datetime('now', ? || ' days')""",
        (f"-{days}",),
    ).fetchone()
    return dict(row) if row else {
        "order_count": 0, "total_spent": 0, "avg_order": 0,
        "max_order": 0, "min_order": 0,
    }
