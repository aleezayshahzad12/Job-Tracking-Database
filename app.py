import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
import requests
import json
import re
from datetime import datetime


# Paths to the database and SQL schema
DB_PATH  = Path(__file__).parent / "jobs.db"
SQL_PATH = Path(__file__).parent / "jobs.sql"

# ---------- Built-in fallback schema (used if jobs.sql missing) ----------
FALLBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  source TEXT,
  url TEXT UNIQUE,
  company TEXT,
  title TEXT,
  location TEXT,
  salary TEXT,
  posted_date TEXT,
  deadline TEXT,
  job_type TEXT,
  experience_level TEXT,
  notes TEXT,
  status TEXT DEFAULT 'Saved',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# =========================
# URL Parsing Utilities
# =========================
def fetch_html(url: str):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.text, str(resp.url), None
    except Exception as e:
        return "", url, f"{type(e).__name__}: {e}"

def detect_platform(final_url: str, html_text: str):
    url = (final_url or "").lower()
    if any(k in url for k in ["jobs.lever.co", "lever.co"]):
        return "lever"
    if "greenhouse.io" in url:
        return "greenhouse"
    if "myworkdayjobs.com" in url or "workday" in url:
        return "workday"
    if "ashbyhq.com" in url:
        return "ashby"
    if "smartrecruiters.com" in url:
        return "smartrecruiters"
    return "generic"

def _as_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list):
        parts = []
        for x in v:
            if isinstance(x, (str, int, float)):
                parts.append(str(x).strip())
        return ", ".join(p for p in parts if p)
    return ""

def extract_jsonld_jobposting(html_text: str):
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
            except Exception:
                continue
            candidates = data if isinstance(data, list) else [data]
            for obj in candidates:
                if not isinstance(obj, dict):
                    continue
                if obj.get("@type") == "JobPosting":
                    return obj
                if "@graph" in obj and isinstance(obj["@graph"], list):
                    for g in obj["@graph"]:
                        if isinstance(g, dict) and g.get("@type") == "JobPosting":
                            return g
        return None
    except Exception:
        return None

def parse_from_jsonld(jobposting_obj: dict):
    if not isinstance(jobposting_obj, dict):
        return {}

    def _get_company(j):
        h = j.get("hiringOrganization")
        if isinstance(h, dict):
            return _as_text(h.get("name"))
        return _as_text(j.get("hiringOrganization"))

    def _get_location(j):
        loc = j.get("jobLocation")
        if isinstance(loc, list) and loc:
            loc = loc[0]
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                parts = [
                    _as_text(addr.get("addressLocality")),
                    _as_text(addr.get("addressRegion")),
                    _as_text(addr.get("addressCountry")),
                ]
                return ", ".join([p for p in parts if p])
        return _as_text(loc)

    def _salary(j):
        pay = j.get("baseSalary")
        if isinstance(pay, dict):
            val = pay.get("value")
            if isinstance(val, dict):
                amount = val.get("value") or val.get("minValue") or val.get("maxValue")
                unit = _as_text(val.get("unitText"))
                currency = _as_text(val.get("currency") or pay.get("currency"))
                if amount is not None and amount != "":
                    return f"{currency}{amount} {unit}".strip()
            currency = _as_text(pay.get("currency"))
            if currency:
                return currency
        return _as_text(pay)

    def _date(iso):
        try:
            return datetime.fromisoformat(str(iso).replace("Z","+00:00")).date().isoformat()
        except Exception:
            return ""

    title_txt = _as_text(jobposting_obj.get("title"))
    job_type_txt = _as_text(jobposting_obj.get("employmentType"))

    return {
        "title":        title_txt,
        "company":      _get_company(jobposting_obj),
        "location":     _get_location(jobposting_obj),
        "salary":       _salary(jobposting_obj),
        "posted_date":  _date(jobposting_obj.get("datePosted","")),
        "deadline":     _date(jobposting_obj.get("validThrough","")),
        "job_type":     job_type_txt,
    }

def parse_generic_meta(html_text: str):
    out = {"title": "", "company": "", "location": "", "salary": "",
           "posted_date": "", "deadline": "", "job_type": ""}
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        title_tag = (soup.title.string or "").strip() if soup.title else ""
        og_site = soup.find("meta", property="og:site_name")
        og_title = soup.find("meta", property="og:title")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        out["title"] = (og_title["content"].strip() if og_title and og_title.has_attr("content") else title_tag)
        maybe_company = og_site["content"].strip() if og_site and og_site.has_attr("content") else ""
        if " - " in out["title"] and not maybe_company:
            parts = out["title"].split(" - ")
            if len(parts) >= 2:
                maybe_company = parts[-1].strip()
                out["title"] = " - ".join(parts[:-1]).strip()
        out["company"] = maybe_company
        return out
    except Exception:
        return out

def _normalize_date(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except Exception:
            pass
    return ""

def normalize_job_record(raw: dict):
    keys = [
        "source","url","company","title","location","salary",
        "posted_date","deadline","job_type","experience_level","notes","status"
    ]
    out = {k: (raw.get(k, "") or "") for k in keys}
    for k in keys:
        if isinstance(out[k], str):
            out[k] = out[k].strip()
    for dk in ["posted_date","deadline"]:
        out[dk] = _normalize_date(out[dk])
    return out

def infer_experience_level(title_text: str, description_text: str | None = None):
    t = (title_text or "").lower()
    d = (description_text or "").lower()
    text = f"{t} {d}"
    if any(k in text for k in ["intern", "internship", "co-op", "co op", "coop"]):
        return "Intern"
    if any(k in text for k in ["new grad", "new-grad", "graduate program"]):
        return "New Grad"
    if any(k in text for k in ["entry level", "entry-level", "junior", "jr."]):
        return "Entry"
    if any(k in text for k in ["senior", "sr.", "staff", "principal", "lead"]):
        return "Senior+"
    return ""

def infer_job_type(text: str | None = None):
    t = (text or "").lower()
    if any(k in t for k in ["full time", "full-time", "fulltime"]):
        return "Full-time"
    if any(k in t for k in ["part time", "part-time", "parttime"]):
        return "Part-time"
    if "contract" in t:
        return "Contract"
    if "intern" in t or "internship" in t:
        return "Internship"
    if "temporary" in t:
        return "Temporary"
    return ""

def build_job_from_url(url: str):
    html, final_url, fetch_err = fetch_html(url)
    record = {
        "source": "URL",
        "url": final_url or url,
        "company": "",
        "title": "",
        "location": "",
        "salary": "",
        "posted_date": "",
        "deadline": "",
        "job_type": "",
        "experience_level": "",
        "notes": "",
        "status": "Saved",
    }
    if fetch_err:
        record["notes"] = f"Fetch error: {fetch_err}"
        return normalize_job_record(record)

    jp = extract_jsonld_jobposting(html)
    parsed = {}
    if jp:
        parsed = parse_from_jsonld(jp)
    if not (parsed.get("title") or parsed.get("company")):
        parsed = parse_generic_meta(html)

    record.update({k: v for k, v in parsed.items() if k in record})
    record["experience_level"] = infer_experience_level(record.get("title",""))
    if not record.get("job_type"):
        record["job_type"] = infer_job_type(record.get("title",""))
    return normalize_job_record(record)

# =========================
# DB helpers
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def _table_exists(conn) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';"
    ).fetchone()
    return row is not None

def init_db():
    with get_conn() as conn:
        if SQL_PATH.exists():
            with open(SQL_PATH, "r", encoding="utf-8") as f:
                schema = f.read()
            conn.executescript(schema)
        else:
            conn.executescript(FALLBACK_SCHEMA)

def ensure_db():
    with get_conn() as conn:
        if not _table_exists(conn):
            init_db()

def insert_job(row: dict):
    cols = [
        "source","url","company","title","location","salary",
        "posted_date","deadline","job_type","experience_level",
        "notes","status"
    ]
    vals = [row.get(k, "") for k in cols]
    with get_conn() as conn:
        before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.execute(
            f"INSERT OR IGNORE INTO jobs ({','.join(cols)}) "
            f"VALUES ({','.join('?'*len(cols))})",
            vals
        )
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        if after > before:
            return True, None
        else:
            url = row.get("url","")
            dup = conn.execute("SELECT 1 FROM jobs WHERE url = ?", (url,)).fetchone()
            if dup:
                return False, "duplicate URL (ignored)"
            return False, "ignored (likely schema mismatch or constraint)"

def delete_job(job_id: int) -> tuple[bool, str | None]:
    try:
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (int(job_id),))
            conn.commit()
            if cur.rowcount and cur.rowcount > 0:
                return True, None
            return False, "id not found"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

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
    q += " ORDER BY created_at DESC, id DESC"
    with get_conn() as conn:
        return pd.read_sql_query(q, conn, params=params)

def total_rows() -> int:
    with get_conn() as conn:
        if not _table_exists(conn):
            return 0
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

# =========================
# App UI
# =========================
def run_app():
    ensure_db()

    # ===== CSS THEME =====
    st.markdown(
        """
        <style>
            .stApp {
                background-color: #e6f2ff; /* baby blue */
                color: black; /* default text */
            }
            .stApp h1 {
                color: #003366; /* dark blue title */
                text-align: center;
                font-weight: 700;
            }
            .stMarkdown, .stText, p, div {
                color: black !important;
            }
            .formwrap {
                background: white;
                padding: 1.5em;
                border-radius: 10px;
                box-shadow: 0px 2px 6px rgba(0,0,0,0.15);
            }
            div.stButton > button {
                background-color: #003366;
                color: white;
                border-radius: 8px;
                font-weight: bold;
            }
            div.stButton > button:hover {
                background-color: #002244;
                color: white;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ===== HERO =====
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    st.title("Job Tracking Database")
    st.markdown(
        "<p>Save job postings by URL, keep notes, and manage your application flow.</p>",
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ===== ADD-BY-URL FORM =====
    with st.container():
        st.markdown('<div class="formwrap">', unsafe_allow_html=True)
        with st.form("add_by_url", clear_on_submit=True):
            url = st.text_input("Job URL (Indeed/LinkedIn/etc.)", placeholder="https://…")
            notes_input = st.text_area("Notes (optional)", placeholder="Any personal notes…", height=100)
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                submitted = st.form_submit_button("Add me", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if submitted and url.strip():
        record = build_job_from_url(url.strip())
        if notes_input.strip():
            existing = record.get("notes", "")
            record["notes"] = (existing + "\n" + notes_input).strip() if existing else notes_input.strip()
        inserted, reason = insert_job(record)
        if inserted:
            st.success(f"Saved ✓ (total rows now: {total_rows()})")
        else:
            st.error(f"Not saved: {reason}")

    st.markdown("")

    # ===== JOB LISTINGS =====
    try:
        @st.dialog("Job Listings")
        def job_listings_dialog():
            c1, c2 = st.columns([1,2])
            with c1:
                f_status_d = st.multiselect(
                    "Filter by status",
                    ["Saved","Applied","Interview","Offer","Rejected"],
                    key="dlg_status_filter"
                )
            with c2:
                f_search_d = st.text_input(
                    "Find (company / title / url)",
                    key="dlg_search_filter"
                )
            df_d = list_jobs(search=f_search_d, statuses=f_status_d)
            st.dataframe(df_d, use_container_width=True, hide_index=True)
            if not df_d.empty:
                st.download_button(
                    "Export CSV",
                    df_d.to_csv(index=False).encode("utf-8"),
                    "jobs.csv",
                    "text/csv",
                    key="dlg_export_csv"
                )
            st.markdown("---")
            del_id = st.number_input("Delete row (enter ID)", min_value=1, step=1, value=None)
            if st.button("Delete"):
                if del_id is None:
                    st.error("Please enter an ID.")
                else:
                    ok, reason = delete_job(int(del_id))
                    if ok:
                        st.success(f"Deleted {int(del_id)} ✓ (total rows now: {total_rows()})")
                        st.rerun()

        s1, s2, s3 = st.columns([1,2,1])
        with s2:
            if st.button("Show Job Listings", use_container_width=True):
                job_listings_dialog()
    except AttributeError:
        s1, s2, s3 = st.columns([1,2,1])
        with s2:
            if st.button("Show Job Listings", use_container_width=True):
                with st.expander("Job Listings", expanded=True):
                    df = list_jobs()
                    st.dataframe(df, use_container_width=True, hide_index=True)

run_app()
