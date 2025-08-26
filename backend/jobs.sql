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
