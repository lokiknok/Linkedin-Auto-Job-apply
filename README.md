# LinkedIn Job Application Assistant (Python + Playwright)

A production-quality, **human-in-the-loop** LinkedIn job application assistant built with **Python, Playwright, FastAPI, SQLite / SQLAlchemy, a modern responsive frontend, and Telegram Bot notifications**.

---

## 🛡️ Important Safety & Design Requirement

This project is an **application assistant**, **NOT a mass-application bot or bot-detection-evasion tool**.

* **Human-in-the-Loop:** The assistant searches for jobs, filters suitable listings, opens application forms, fills standard details from your profile, uploads your resume, and optionally suggests answers for custom questions.
* **Strict Pause Before Submission:** The automation **always stops and pauses before the final "Submit application" button**.
* **Manual Review & Submission:** You review the filled details and uploaded resume directly in the browser and click "Submit" yourself on LinkedIn.
* **No Platform Bypass:** Does not attempt to bypass LinkedIn security, CAPTCHA, rate limits, or authentication protections. If a CAPTCHA or checkpoint appears, automation halts and alerts you to complete it manually.

---

## 🚀 Features

1. **Job Search & Scraping:** Scrapes job listings from LinkedIn searches (title, company, location, URL, description, posted date, Easy Apply badge).
2. **Relevance Scoring Engine:**
   $$\text{Match Score} = (0.40 \times \text{Title}) + (0.30 \times \text{Skills}) + (0.20 \times \text{Location}) + (0.10 \times \text{Experience})$$
3. **Form Detection & Safe Filling:** Identifies standard fields (`first_name`, `last_name`, `email`, `phone`, `city`, `country`, `linkedin_url`, `portfolio_url`) and fills them only from configured settings. Unrecognized fields are never guessed.
4. **Resume Management:** Validates PDF format, checks file existence and size, and attaches to application file inputs.
5. **AI Question Assistant:** Uses OpenAI (or intelligent rule-based heuristic matcher) to generate suggested answers with confidence scores for custom questions.
6. **Application Tracker & Dashboard:** SQLite database tracking applications across statuses (`FOUND`, `REVIEWING`, `READY_TO_SUBMIT`, `APPLIED`, `INTERVIEW`, `TECHNICAL_ROUND`, `OFFER`, `REJECTED`, `WITHDRAWN`).
7. **Telegram Bot Integration:**
   * Instant alerts for: *Job Found*, *Application Ready for Review*, *Unfamiliar Question Detected*, *CAPTCHA Alert*, *Application Marked as Applied*, and *Errors*.
   * Supported commands (authorized chat ID only): `/start`, `/status`, `/jobs`, `/applications`, `/help`.
   * Gracefully degrades if Telegram credentials are not configured.
8. **Modern Responsive Web UI:** Dashboard statistics, interactive job filter cards, applications tracker table with status updater, and settings panel.

---

## 🏗️ Architecture & Project Structure

```text
linkedin-job-assistant/
│
├── app.py                      # Main entrypoint: FastAPI app & static server
├── config.py                   # Pydantic Settings, environment & logging setup
├── requirements.txt            # Python dependencies
├── .env.example                # Example environment template
├── .env                        # Local environment secrets
├── .gitignore                  # Git ignore rules
├── README.md                   # Full documentation
│
├── browser/
│   ├── __init__.py
│   └── linkedin_browser.py     # Playwright persistent context, login check, CAPTCHA detection
│
├── jobs/
│   ├── __init__.py
│   ├── search.py               # LinkedIn search URL generator & query coordinator
│   ├── scraper.py              # Scrapes job cards and provides mock/demo generator
│   └── filters.py              # 40-30-20-10 relevance scoring & deduplication
│
├── application/
│   ├── __init__.py
│   ├── form_detector.py        # DOM form field classifier & question detector
│   ├── form_filler.py          # Safe field population & next-step navigation
│   ├── resume_upload.py        # PDF validation & file upload handling
│   └── workflow.py             # Human-in-the-loop preparation & pause coordination
│
├── ai/
│   ├── __init__.py
│   └── question_answerer.py    # OpenAI & heuristic QA generator
│
├── database/
│   ├── __init__.py
│   ├── database.py             # SQLAlchemy engine & session maker
│   └── models.py               # Application & JobListing ORM models
│
├── api/
│   ├── __init__.py
│   ├── jobs.py                 # Job search & retrieval endpoints
│   ├── applications.py         # Application CRUD & preparation endpoints
│   ├── settings.py             # Settings & resume upload endpoints
│   ├── browser_routes.py       # Browser lifecycle endpoints
│   └── telegram_routes.py      # Telegram connection test endpoint
│
├── telegram/
│   ├── __init__.py
│   └── notifier.py             # Telegram notifications & bot command polling
│
├── frontend/
│   ├── index.html              # Main responsive web application
│   ├── css/
│   │   └── style.css           # Modern CSS styling
│   └── js/
│       ├── app.js              # SPA navigation & browser state polling
│       ├── dashboard.js        # Metrics cards & high-match preview
│       ├── jobs.js             # Job search UI & application modal
│       ├── applications.js     # Applications table, notes, and status updater
│       └── settings.js         # Profile form, PDF upload, Telegram tester
│
├── tests/
│   ├── test_filters.py         # Unit tests for scoring & keywords
│   ├── test_database.py        # Unit tests for DB operations & unique URL
│   ├── test_form_detector.py   # Unit tests for field mapping & detection
│   ├── test_ai_qa.py           # Unit tests for AI QA & fallback logic
│   ├── test_telegram.py        # Unit tests for Telegram notifier & security
│   └── test_api.py             # Integration tests for FastAPI endpoints
│
├── data/                       # SQLite DB & persistent browser profile (gitignored)
├── logs/                       # Rotating application logs (gitignored)
└── resumes/                    # User PDF resumes (gitignored)
```

---

## 📦 Installation & Setup

### 1. Prerequisites
* Python 3.11+
* Windows / macOS / Linux

### 2. Create and Activate Virtual Environment

```powershell
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```powershell
playwright install chromium
```

---

## ⚙️ Configuration (`.env`)

Copy `.env.example` to `.env`:

```env
# Application Database & Logging
DATABASE_URL=sqlite:///./data/applications.db
LOG_LEVEL=INFO

# Google Gemini API (Recommended: fast & accurate application question answering)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Or OpenAI API (Optional alternative)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Optional: Telegram Bot Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Server Host & Port
PORT=8000
HOST=127.0.0.1
```

> [!NOTE]
> If neither `GEMINI_API_KEY` nor `OPENAI_API_KEY` are provided, the assistant continues running smoothly using built-in intelligent rule-based heuristic matchers.

---

## 🏃 Running the Application

Start the FastAPI application:

```powershell
python app.py
```

Then open your browser and navigate to:
```text
http://127.0.0.1:8000
```

---

## 📖 Complete User Workflow

```text
1. Open http://127.0.0.1:8000

2. Navigate to "Settings & Resume":
   - Fill in your name, contact info, LinkedIn URL, and skills.
   - Upload your PDF resume (validated automatically).
   - Click "Save Changes".

3. Click "Launch Browser" in the top bar:
   - Playwright opens a headed Chromium window.
   - Log into your LinkedIn account manually (sessions are saved in data/browser_profile).

4. Navigate to "Find Jobs":
   - Enter your target keywords and locations.
   - Click "Search Jobs".
   - The assistant calculates match scores (40% Title, 30% Skills, 20% Location, 10% Exp).

5. Select a job and click "Prepare Application":
   - Playwright navigates to the job listing.
   - Triggers Easy Apply.
   - Fills standard fields from your configured profile.
   - Attaches your resume PDF.
   - AI suggests answers for custom questions.
   - Automation stops and pauses before the final submit button.

6. Review in Browser:
   - Inspect the open LinkedIn browser window.
   - Confirm all fields, salary, and attachments.
   - Click "Submit application" manually on LinkedIn.

7. Mark as Applied:
   - Click "Mark as Applied" on the assistant dashboard.
   - Application status updates to APPLIED in SQLite.
   - Telegram notification is delivered with confirmation.
```

---

## 📱 Telegram Bot Setup & Commands

### Setup Instructions
1. Open Telegram and search for `@BotFather`.
2. Create a new bot with `/newbot` and copy the API token to `TELEGRAM_BOT_TOKEN` in `.env`.
3. Start a chat with your bot and send a message.
4. Get your Chat ID (using `@userinfobot` or `https://api.telegram.org/bot<TOKEN>/getUpdates`) and add to `TELEGRAM_CHAT_ID` in `.env`.
5. Go to the Settings page in the web UI and click **"Test Telegram Connection"**.

### Supported Commands (Authorized Chat Only)
* `/start` - Connects and displays welcome guide.
* `/status` - Live count of jobs discovered, prepared, applied, and active browser state.
* `/jobs` - Displays top matching recent job listings.
* `/applications` - Lists recent applications and their current status.
* `/help` - Displays available commands and safety reminder.

---

## 🧪 Running Automated Tests

Run the complete test suite:

```powershell
python -m pytest tests/ -v
```

All 25 unit and integration tests verify:
* Relevance scoring formula & keyword matching
* SQLite operations, duplicate URL prevention, and status transitions
* Form field detection and classification
* AI QA suggested answer heuristics and confidence
* Telegram notifications, authorization security, and commands
* FastAPI REST endpoints and dashboard metrics

---

## 🔒 Security & Privacy Considerations

* **No Hardcoded Credentials:** All tokens and keys reside in `.env` (gitignored).
* **Authorized Telegram Access:** Commands are strictly validated against `TELEGRAM_CHAT_ID`. Unknown users receive "Access denied."
* **No Auto-Submit:** Final submission is permanently manual, ensuring complete user control.
* **Persistent Session Isolation:** Browser user data is stored locally in `data/browser_profile/` and never transmitted externally.

