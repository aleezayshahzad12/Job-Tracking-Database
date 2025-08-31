# libraies neceassary for database connection
# pyhton libraries with with SQLite database
import sqlite3
# working with files paths
from pathlib import Path

# finds where the database is located
DB_PATH = Path(__file__).parent / "jobs.db"

# opens a connection to the database above
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
