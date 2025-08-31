# Job Tracking Database


**A lightweight, full-stack Streamlit application** designed to automate your job search. Simply submit a job posting URL, and the app will automatically parse and store key details like title, company, and location, eliminating manual data entry.

**🚀 Impact:** Drastically reduces the time spent manually logging applications, providing a centralized dashboard to track and download your entire job search.


Webiste Link: https://chaincoevents.netlify.app/

## 🌟 Features

- **URL-Based Data Extraction:** Paste a job URL from platforms the app handles the rest. 
- **Dual-Phase Parsing Pipeline**:
  ###Structured: Precisely extracts data from JSON-LD JobPosting schema for high accuracy on supported sites.
  ###Fallback: If JSON-LD fails, falls back to parsing standard HTML meta tags and page titles for broader compatibility. 
- **Centralized Dashboard:** View, search, and filter all your saved jobs in a clean, sortable table.
- **Data Integrity:** Built on SQLite with unique constraints to prevent duplicate entries and WAL mode for reliability.  
- **Export Data:** Download your entire job list as a CSV file.
- **Designed and deployed** for a real event company in New York City. 
  
## 🛠 Tech Stack
- **Frontend:** Streamlit  
- **Programming Language:** Python
- **Web Scraping & Parsing:**  BeautifulSoup4, Requests
- **Database:** SQLite 
- **Data Handling:** Pandas
- 

## 🗃️ How It Works
- ** 1. Input:** You submit a job URL through the Streamlit interface.

- ** 2.Fetch:** The app retrieves the HTML content of the page.

- ** 3.Phase 1** - JSON-LD: The parser first looks for structured data within  tag. This is the most reliable method and extracts the data (title, company, location, salary, etc.).
  
- ** 4.Phase 2** - Meta Tags: If no structured data is found, it falls back to parsing the HTML tags (like og:title and og:site_name) to infer the job title and company.

- ** 5.Storage:** The parsed data is saved to a local SQLite database (jobs.db), which is automatically created on first run.

## 🔧 In Progress / Immediate Next Steps:

Status Management UI: Frontend controls to update the status field (e.g., change from "Saved" to "Applied") directly within the application dashboard.

## 📋 Future Roadmap & Enhancements (Planned):

Automated Job Discovery: Allowing users to search with natural language queries (e.g., "cs internships paid northern virginia") to automatically find and parse relevant postings from multiple platforms.

Advanced Fallback Parser: Improving the generic HTML parser to handle complex job board layouts beyond simple meta tags.

Job Description Analysis: Scraping the full job description to significantly improve the accuracy of automatic experience_level and job_type inference.

User Authentication & Cloud Deployment: Adding user login to support multiple users with separate job lists and deploying to a cloud platform.

## 🔧 Installation & Setup
```bash
# 1) Clone the repository
git clone https://github.com/aleezayshahzad12/Job-Tracking-Database.git
cd Job-Tracking-Database

# 2) Install dependencies
pip install -r requirements.txt

# 3) Set up environment variables
python -m venv venv
source venv/bin/activate

# 4) Run The application
streamlit run app.py

```
```

## 📄 License
This project is proprietary and maintained by Chai & Co.

## 🏆 Acknowledgments
OpenAI for powerful language model capabilities

Zoom for seamless video meeting integration

SendGrid for reliable email delivery services

MongoDB for robust data storage solutions








