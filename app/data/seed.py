"""Generate the demo database for Grindstone Coffee Co. (a fictional UK online coffee roaster).

The data is deterministic (fixed random seed) so eval expectations stay stable.
It also contains some business rules that are *not* obvious from the schema.
The agent gets these wrong until someone gives it feedback (see README "Demo scenarios"):

  * Revenue must be net of refunds (refunds live in a separate table) and exclude cancelled orders.
  * The financial year starts on 1 April, so "Q1" means April-June.
  * Staff/QA test accounts (emails ending @grindstonecoffee.co.uk) are not real customers.

Run:  uv run python -m app.data.seed
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "shop.db"
SEED = 20260401

FIRST_ORDER_DATE = date(2025, 4, 1)
LAST_ORDER_DATE = date(2026, 8, 31)

# (sku, name, category, price_pence, popularity weight)
PRODUCTS = [
    ("COF-HOUSE-1KG", "House Espresso Blend 1kg", "coffee", 2600, 30),
    ("COF-HOUSE-250", "House Espresso Blend 250g", "coffee", 850, 14),
    ("COF-ETH-250", "Ethiopia Yirgacheffe 250g", "coffee", 1100, 10),
    ("COF-COL-250", "Colombia Huila 250g", "coffee", 950, 10),
    ("COF-BRA-250", "Brazil Cerrado 250g", "coffee", 800, 9),
    ("COF-DECAF-250", "Swiss Water Decaf 250g", "coffee", 900, 6),
    ("COF-KEN-250", "Kenya Nyeri AA 250g", "coffee", 1250, 6),
    ("COF-GUA-250", "Guatemala Antigua 250g", "coffee", 1000, 5),
    ("EQP-V60", "Ceramic V60 Dripper", "equipment", 2400, 4),
    ("EQP-GRINDER", "Hand Burr Grinder", "equipment", 8900, 2),
    ("EQP-KETTLE", "Gooseneck Pour-Over Kettle", "equipment", 5500, 2),
    ("EQP-SCALE", "Brew Scale with Timer", "equipment", 3200, 2),
    ("EQP-FILTERS", "V60 Paper Filters (100)", "equipment", 650, 5),
    ("MER-MUG", "Grindstone Enamel Mug", "merch", 1400, 3),
    ("MER-TOTE", "Grindstone Tote Bag", "merch", 1200, 2),
    ("MER-GIFT", "Gift Card £25", "merch", 2500, 2),
]

COUNTRIES = [
    ("United Kingdom", 60),
    ("Ireland", 12),
    ("France", 10),
    ("Germany", 10),
    ("Netherlands", 8),
]

FIRST_NAMES = [
    "Olivia", "Amelia", "Isla", "Ava", "Mia", "Freya", "Lily", "Grace", "Sophie", "Evie",
    "Oliver", "George", "Noah", "Arthur", "Leo", "Harry", "Oscar", "Jack", "Charlie", "Theo",
    "Aoife", "Sean", "Claire", "Luc", "Emma", "Hugo", "Lena", "Jonas", "Sanne", "Daan",
]
LAST_NAMES = [
    "Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Patel", "Wright",
    "Murphy", "Kelly", "Martin", "Bernard", "Muller", "Schmidt", "de Vries", "Jansen", "Evans", "Walker",
]

N_CUSTOMERS = 600
N_TEST_ACCOUNTS = 25
CANCEL_RATE = 0.07
REFUND_RATE = 0.06

SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL          -- ISO-8601 UTC timestamp
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,           -- coffee | equipment | merch
    price_pence INTEGER NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    created_at TEXT NOT NULL,         -- ISO-8601 UTC timestamp
    status TEXT NOT NULL,             -- completed | cancelled
    total_pence INTEGER NOT NULL
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price_pence INTEGER NOT NULL
);

CREATE TABLE refunds (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    amount_pence INTEGER NOT NULL,
    created_at TEXT NOT NULL,         -- ISO-8601 UTC timestamp
    reason TEXT NOT NULL
);
"""


def _ts(d: date, rng: random.Random) -> str:
    # Business-hours timestamps only, so UTC vs UK-local never moves an order across a day boundary.
    t = datetime(d.year, d.month, d.day, rng.randint(8, 19), rng.randint(0, 59), rng.randint(0, 59))
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _random_date(start: date, end: date, rng: random.Random) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def build(db_path: Path = DB_PATH) -> None:
    rng = random.Random(SEED)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    for i, (sku, name, category, price, _w) in enumerate(PRODUCTS, start=1):
        conn.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)", (i, sku, name, category, price))

    customers: list[tuple[int, date]] = []
    used_emails: set[str] = set()
    cid = 0
    for _ in range(N_CUSTOMERS):
        cid += 1
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        email = f"{first}.{last}".lower().replace(" ", "") + f"{rng.randint(1, 999)}@example.com"
        while email in used_emails:
            email = email.replace("@", f"{rng.randint(0, 9)}@")
        used_emails.add(email)
        country = rng.choices([c for c, _ in COUNTRIES], weights=[w for _, w in COUNTRIES])[0]
        created = _random_date(date(2025, 1, 1), date(2026, 8, 31), rng)
        conn.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)", (cid, f"{first} {last}", email, country, _ts(created, rng))
        )
        customers.append((cid, created))

    # Internal staff / QA accounts. They look like customers but never place real orders.
    for n in range(1, N_TEST_ACCOUNTS + 1):
        cid += 1
        created = _random_date(date(2025, 1, 1), date(2025, 12, 31), rng)
        conn.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
            (cid, f"QA Test Account {n}", f"qa+{n}@grindstonecoffee.co.uk", "United Kingdom", _ts(created, rng)),
        )

    product_ids = list(range(1, len(PRODUCTS) + 1))
    weights = [p[4] for p in PRODUCTS]
    order_id = item_id = refund_id = 0
    day = FIRST_ORDER_DATE
    while day <= LAST_ORDER_DATE:
        # Gentle growth over time plus a weekend bump.
        months_in = (day.year - FIRST_ORDER_DATE.year) * 12 + day.month - FIRST_ORDER_DATE.month
        base = 5 + months_in * 0.35 + (2 if day.weekday() >= 5 else 0)
        n_orders = max(0, int(rng.gauss(base, 2)))
        eligible = [c for c, created in customers if created <= day]
        for _ in range(n_orders):
            order_id += 1
            customer_id = rng.choice(eligible)
            status = "cancelled" if rng.random() < CANCEL_RATE else "completed"
            ts = _ts(day, rng)
            total = 0
            chosen = rng.choices(product_ids, weights=weights, k=rng.choice([1, 1, 1, 2, 2, 3]))
            for pid in set(chosen):
                qty = rng.choice([1, 1, 1, 2, 3])
                price = PRODUCTS[pid - 1][3]
                item_id += 1
                conn.execute("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", (item_id, order_id, pid, qty, price))
                total += qty * price
            conn.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", (order_id, customer_id, ts, status, total))

            if status == "completed" and rng.random() < REFUND_RATE:
                refund_id += 1
                full = rng.random() < 0.6
                amount = total if full else max(100, int(total * rng.choice([0.25, 0.5])) // 10 * 10)
                refunded_on = min(day + timedelta(days=rng.randint(2, 20)), LAST_ORDER_DATE)
                reason = rng.choice(["damaged in transit", "wrong grind", "late delivery", "changed mind"])
                conn.execute(
                    "INSERT INTO refunds VALUES (?, ?, ?, ?, ?)",
                    (refund_id, order_id, amount, _ts(refunded_on, rng), reason),
                )
        day += timedelta(days=1)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    build()
    print(f"Wrote {DB_PATH}")
