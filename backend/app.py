# app.py
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
import requests
import json
import re
from datetime import datetime

# ---------- Title ----------
st.set_page_config(page_title="Job Tracking Database", layout="wide")
st.title("Job Tracking Database")

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
# URL Parsing Utilities (FIRST so they’re defined before use)
# =========================
def fetch_html(url: str):
    """Fetch HTML and return (html_text, final_url, error)."""
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
    """Return a platform key like 'lever', 'greenhouse', 'workday', 'ashby', 'smartrecruiters', or 'generic'."""
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
    """Coerce JSON-LD values (str | list | number | None) to a clean string."""
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
    """Return the first schema.org JobPosting object in JSON-LD, or None."""
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
    """Map JSON-LD JobPosting → our fields, tolerating lists or scalars."""
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
    """Fallback using <title>, meta description, og tags."""
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
        desc_text = meta_desc["content"] if (meta_desc and meta_desc.has_attr("content")) else ""
        out["salary"] = extract_salary(desc_text)
        out["job_type"] = infer_job_type(desc_text)
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
    """Ensure all required keys exist and strings are trimmed."""
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

def extract_salary(text: str | None = None):
    """Very light regex to pull $80,000, $40–50/hr, 120k, etc."""
    t = (text or "")
    m = re.search(
        r"\$?\s?\d{2,3}(?:,\d{3})?(?:\s*[-–]\s*\$?\d{2,3}(?:,\d{3})?)?\s*(?:k|K|/yr|per year|per hour|/hr|hour|annually)?",
        t
    )
    if m:
        return m.group(0).strip()
    return ""

def extract_dates(text: str | None = None):
    """Placeholder date extractor."""
    return {"posted_date": "", "deadline": ""}

def choose_best_source(platform: str, has_jsonld: bool):
    """Decide precedence among parsers (we use JSON-LD then generic)."""
    order = []
    if has_jsonld:
        order.append("jsonld")
    order.append("generic")
    return order

def build_job_from_url(url: str):
    """
    Orchestrator:
      - fetch_html → detect_platform → choose_best_source
      - run JSON-LD and/or generic fallback
      - normalize + infer (experience level, job type, salary, dates)
    """
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

def validate_job_record(job: dict):
    """Validate required keys and basic types."""
    must = ["source","url","company","title","status"]
    for k in must:
        if k not in job:
            return False, f"missing key {k}"
        if not isinstance(job[k], str):
            return False, f"key {k} not a string"
    return True, None

def sanitize_for_db(job: dict):
    """Final cleanup before insert."""
    clean = {}
    for k, v in job.items():
        s = v if isinstance(v, str) else ""
        s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)  # drop control chars
        if k in {"notes"} and len(s) > 5000:
            s = s[:5000]
        if k in {"title","company","location","job_type","experience_level","status","salary"} and len(s) > 500:
            s = s[:500]
        clean[k] = s.strip()
    return clean

def render_parse_diagnostics(raw_signals: dict | None = None):
    """Optional diagnostics hook (unused)."""
    return {}

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
    """
    Ensure the 'jobs' table exists:
    - Use jobs.sql if present,
    - else create using FALLBACK_SCHEMA.
    """
    with get_conn() as conn:
        if SQL_PATH.exists():
            with open(SQL_PATH, "r", encoding="utf-8") as f:
                schema = f.read()
            conn.executescript(schema)
        else:
            conn.executescript(FALLBACK_SCHEMA)

def ensure_db():
    """Create the table if missing (using jobs.sql or fallback)."""
    with get_conn() as conn:
        if not _table_exists(conn):
            init_db()

def insert_job(row: dict):
    """
    Insert one job. Returns (inserted: bool, reason: str|None).
    Uses INSERT OR IGNORE so duplicates by URL won’t crash; we detect if ignored.
    """
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
    """Delete a job by primary key id. Returns (deleted, reason)."""
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
# App UI (runs AFTER all defs)
# =========================
def run_app():
    ensure_db()

    # ===== HERO (centered) =====
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    st.title("Job Tracking Database")
    st.markdown(
        "<p>Save job postings by URL, keep notes, and manage your application flow.</p>",
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ===== CENTERED ADD-BY-URL FORM =====
    with st.container():
        st.markdown('<div class="formwrap">', unsafe_allow_html=True)
        with st.form("add_by_url", clear_on_submit=True):
            url = st.text_input("Job URL (Indeed/LinkedIn/etc.)", placeholder="https://…")
            notes_input = st.text_area("Notes (optional)", placeholder="Any personal notes…", height=100)
            # Center the submit button by sandwiching it between empty columns
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                submitted = st.form_submit_button("Add me", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    if submitted and url.strip():
        record = build_job_from_url(url.strip())
        if notes_input.strip():
            existing = record.get("notes", "")
            record["notes"] = (existing + "\n" + notes_input).strip() if existing else notes_input.strip()

        ok, err = validate_job_record(record)
        if not ok:
            st.warning(f"Saving with minimal fields (parser issue: {err})")

        inserted, reason = insert_job(sanitize_for_db(record))
        if inserted:
            st.success(f"Saved ✓ (total rows now: {total_rows()})")
        else:
            st.error(f"Not saved: {reason}")

    st.markdown("")

    # ===== JOB LISTINGS POPUP =====
    # Define dialog once
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
            del_id = st.number_input(
                "Delete row (enter ID)",
                min_value=1, step=1, value=None,
                placeholder="Enter numeric id",
                key="dlg_del_id"
            )
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Delete", key="dlg_delete_btn"):
                    if del_id is None:
                        st.error("Please enter an ID.")
                    else:
                        ok, reason = delete_job(int(del_id))
                        if ok:
                            st.success(f"Deleted {int(del_id)} ✓ (total rows now: {total_rows()})")
                            st.rerun()
                        else:
                            st.error(f"Could not delete {int(del_id)}: {reason}")
            with b2:
                if st.button("Close", key="dlg_close_btn"):
                    st.rerun()

        # Centered "Show Job Listings" button
        s1, s2, s3 = st.columns([1,2,1])
        with s2:
            if st.button("Show Job Listings", use_container_width=True):
                job_listings_dialog()

    except AttributeError:
        # Fallback if your Streamlit version doesn't have st.dialog
        s1, s2, s3 = st.columns([1,2,1])
        with s2:
            if st.button("Show Job Listings", use_container_width=True):
                with st.expander("Job Listings", expanded=True):
                    c1, c2 = st.columns([1,2])
                    with c1:
                        f_status = st.multiselect(
                            "Filter by status",
                            ["Saved","Applied","Interview","Offer","Rejected"]
                        )
                    with c2:
                        f_search = st.text_input("Find (company / title / url)")

                    df = list_jobs(search=f_search, statuses=f_status)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    del_id = st.number_input(
                        "Delete row (enter ID)",
                        min_value=1, step=1, value=None,
                        placeholder="Enter numeric id"
                    )
                    if st.button("Delete"):
                        if del_id is None:
                            st.error("Please enter an ID.")
                        else:
                            ok, reason = delete_job(int(del_id))
                            if ok:
                                st.success(f"Deleted {int(del_id)} ✓ (total rows now: {total_rows()})")
                                st.rerun()
                            else:
                                st.error(f"Could not delete {int(del_id)}: {reason}")

    st.caption(f"Rows in database: {total_rows()}")

# Streamlit runs the script top-to-bottom; we call the app after all defs
run_app()
