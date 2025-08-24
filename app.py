import os
import uuid
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
import httpx
import sqlite3

st.title("Job Tracking Database")
# access the database path
DB_PATH = Path(__file__).parent / "jobs.db"


# connect the path to the database
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    return conn

# creates a table and inputs the columns in schema
def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)




