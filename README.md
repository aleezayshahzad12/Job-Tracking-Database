# Job Tracking Database

A lightweight, full-stack Streamlit application that automates your job search. Submit a job posting URL, and the app automatically parses and stores key details like title, company, and location, eliminating manual data entry.

**🚀 Impact:** Drastically reduces time spent manually logging applications, providing a centralized dashboard to track your entire job search.

![Built with Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)

## 🌟 Features

- **URL-Based Data Extraction:** Paste a job URL from platforms like Lever or Greenhouse; the app handles the parsing
- **Dual-Phase Parsing Pipeline:**
  - **Structured:** Precisely extracts data from JSON-LD JobPosting schema for high accuracy
  - **Fallback:** Parses HTML meta tags and page titles when JSON-LD is unavailable
- **Centralized Dashboard:** View, search, and filter all saved jobs in a sortable table
- **Data Integrity:** SQLite with unique constraints prevents duplicate entries
- **Export Data:** Download your job list as a CSV file

## 🛠 Tech Stack

- **Frontend:** Streamlit
- **Backend:** Python
- **Web Scraping:** BeautifulSoup4, Requests
- **Database:** SQLite
- **Data Handling:** Pandas

## 🗃️ How It Works

1.  **Input:** Submit a job URL through the Streamlit interface
2.  **Fetch:** App retrieves HTML content of the page
3.  **Phase 1 - JSON-LD:** Parser looks for structured data in `<script type="application/ld+json">` tags
4.  **Phase 2 - Meta Tags:** Falls back to parsing HTML `<meta>` tags if no structured data found
5.  **Storage:** Parsed data saves to a local SQLite database (`jobs.db`)

## 🔧 Current Status

**✅ Fully Implemented:**
- URL ingestion and parsing pipeline
- SQLite database with unique constraints
- Dashboard view and CSV export
- Dual-phase parsing (JSON-LD + HTML fallback)

**🔧 In Progress:**
- Status management UI to update application status (Saved → Applied → Interview, etc.)

**📋 Future Enhancements:**
- Natural language search queries ("cs internships in virginia")
- Improved HTML parser for better compatibility
- Job description analysis for better categorization
- User authentication and cloud deployment

## 🚀 Installation & Setup

```bash
# Clone the repository
git clone https://github.com/aleezayshahzad12/Job-Tracking-Database.git
cd Job-Tracking-Database

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py

```

## 🤝 Development
This project was developed through collaborative pair programming sessions, focusing on creating a robust backend parsing system and database architecture. The development emphasized:

## 📄 License
MIT License



