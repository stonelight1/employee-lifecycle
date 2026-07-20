import sqlite3

conn = sqlite3.connect('D:/python/project/employee-lifecycle/backend/data/employee_lifecycle.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cur.fetchall()

for t in tables:
    table_name = t[0]
    print(f'=== Table: {table_name} ===')
    cur.execute(f'PRAGMA table_info("{table_name}")')
    cols = cur.fetchall()
    for c in cols:
        nullable = "YES" if c[3] == 0 else "NO"
        default = c[4] if c[4] is not None else ""
        print(f'  {c[1]:35s} {c[2]:20s} nullable={nullable:3s}  pk={c[5]}  default={default}')
    print()

conn.close()
