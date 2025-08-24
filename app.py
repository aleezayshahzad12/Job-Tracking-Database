import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

# ---------- Title ----------
st.set_page_config(page_title="Job Tracking Database", layout="wide")
st.title("Job Tracking Database")

# Paths to the database and SQL schema
DB_PATH  = Path(__file__).parent / "jobs.db"
SQL_PATH = Path(__file__).parent / "jobs.sql"

# ---------- DB helpers ----------
# connects to the database
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

# initializes the database if it doesn't exist
def init_db():
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    with get_conn() as conn:
        conn.executescript(schema)

# ensures the database and tables exist
def ensure_db():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';"
        ).fetchone()
    if row is None:
        init_db()

def insert_job(row: dict):
    cols = ["source","url","company","title","location","salary",
            "posted_date","deadline","job_type","experience_level",
            "notes","status"]
    vals = [row.get(k, "") for k in cols]
    with get_conn() as conn:
        conn.execute(
            f"INSERT OR IGNORE INTO jobs ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
            vals
        )
        conn.commit()

def list_jobs(search: str = "", statuses=None) -> pd.DataFrame:
    q = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if search:
        q += " AND (company LIKE ? OR title LIKE ? OR url LIKE ?)"
        s = f"%{search}%"
        params += [s, s, s]
    if statuses:
        q += f" AND status IN ({','.join('?'*len(statuses))})"
        params += list(statuses)
    with get_conn() as conn:
        return pd.read_sql_query(q, conn, params=params)

# ---------- App ----------
ensure_db()

st.subheader("Add a job by URL")
with st.form("add_by_url"):
    url = st.text_input("Job URL (Indeed/LinkedIn/etc.)", placeholder="https://...")
    submitted = st.form_submit_button("Add me")
    if submitted and url.strip():
        # TODO: define company/title/notes/status yourself OR
        # replace this block to call build_job_from_url(url) and then insert_job(...)
        insert_job({
            "source": "User",
            "url": url.strip(),
            "company": company.strip(),
            "title": title.strip(),
            "location": "",
            "salary": "",
            "posted_date": "",
            "deadline": "",
            "job_type": "",
            "experience_level": "",
            "notes": notes.strip(),
            "status": status,
        })
        st.success("Saved")

st.subheader("JOB LISTINGS")
c1, c2 = st.columns([1,2])
with c1:
    f_status = st.multiselect("Filter by status", ["Saved","Applied","Interview","Offer","Rejected"])
with c2:
    f_search = st.text_input("Find:     (company / title / url)")

df = list_jobs(search=f_search, statuses=f_status)
st.dataframe(df, use_container_width=True)

# ---------- URL Parsing Stubs (fill these out) ----------
def fetch_html(url: str):
    """
    Fetch the HTML for the given URL.
    Return a tuple: (html_text: str, final_url: str, error: str|None).
    """
    pass

def detect_platform(final_url: str, html_text: str):
    """
    Inspect the URL/HTML and return a short platform key, e.g.:
    'lever', 'greenhouse', 'workday', 'ashby', 'smartrecruiters', 'generic'.
    """
    pass

def extract_jsonld_jobposting(html_text: str):
    """
    Return the first schema.org JobPosting object found in JSON-LD,
    or None if not present.
    """
    pass

def parse_from_jsonld(jobposting_obj: dict):
    """
    Map a JSON-LD JobPosting object to your schema fields:
    title, company, location, salary, posted_date, deadline, job_type.
    Return a dict with those keys (values may be empty strings).
    """
    pass

def parse_from_lever(final_url: str, html_text: str):
    """
    Parse Lever job pages (or Lever API) and return a dict mapped to your fields.
    """
    pass

def parse_from_greenhouse(final_url: str, html_text: str):
    """
    Parse Greenhouse job pages and return a dict mapped to your fields.
    """
    pass

def parse_from_workday(final_url: str, html_text: str):
    """
    Parse Workday job pages and return a dict mapped to your fields.
    """
    pass

def parse_from_ashby(final_url: str, html_text: str):
    """
    Parse Ashby job pages and return a dict mapped to your fields.
    """
    pass

def parse_from_smartrecruiters(final_url: str, html_text: str):
    """
    Parse SmartRecruiters job pages and return a dict mapped to your fields.
    """
    pass

def parse_generic_meta(html_text: str):
    """
    Generic fallback parser using <title>, og:site_name, meta description, etc.
    Return a dict with as many fields as you can infer.
    """
    pass

def normalize_job_record(raw: dict):
    """
    Trim strings, normalize dates to YYYY-MM-DD, convert salary to a readable string,
    and ensure all required keys exist with string values.
    """
    pass

def infer_experience_level(title_text: str, description_text: str | None = None):
    """
    Heuristics to infer experience level (e.g., Intern, New Grad, Entry, Senior).
    Return a short string or '' if unknown.
    """
    pass

def infer_job_type(text: str | None = None):
    """
    Heuristics to infer job type (Full-time, Internship, Contract) and/or
    workplace type (Remote/Hybrid/Onsite). Return a short string or ''.
    """
    pass

def extract_salary(text: str | None = None):
    """
    Extract salary/range/currency from free text. Return a human-readable string or ''.
    """
    pass

def extract_dates(text: str | None = None):
    """
    Extract posted_date and deadline from free text. Return a dict:
    {'posted_date': 'YYYY-MM-DD'|'', 'deadline': 'YYYY-MM-DD'|''}
    """
    pass

def choose_best_source(platform: str, has_jsonld: bool):
    """
    Decide precedence among platform-specific parser, JSON-LD, and generic meta.
    Return an ordered list of parser keys to try.
    """
    pass

def build_job_from_url(url: str):
    """
    Orchestrator:
      - fetch_html → detect_platform → choose_best_source
      - run the selected parser(s) and/or JSON-LD/generic fallback
      - normalize + infer (experience level, job type, salary, dates)
      - return a dict with all DB fields, including:
        source='URL', url, company, title, location, salary,
        posted_date, deadline, job_type, experience_level, notes, status='Saved'
    """
    pass

def validate_job_record(job: dict):
    """
    Validate required keys and basic types/lengths.
    Return (is_valid: bool, error_message: str|None).
    """
    pass

def sanitize_for_db(job: dict):
    """
    Final cleanup before insert (truncate long fields, strip control chars, etc.).
    Return the cleaned dict.
    """
    pass

def render_parse_diagnostics(raw_signals: dict | None = None):
    """
    (Optional) Return a small dict/string describing which parser filled which fields,
    to help with debugging or UI display.
    """
    pass
