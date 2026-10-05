```markdown
# 🏭 CNC Lead Engine
### Automated Industrial Machine Sourcing & Lead Broadcasting System

A fully automated pipeline that sources used CNC/VMC machine listings
from multiple industrial marketplaces, scores them by quality, and
broadcasts personalized leads to buyers via Email and WhatsApp —
every single day at 8 AM without any manual work.

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Module Breakdown](#5-module-breakdown)
   - [Module 1 — Sourcing Engine](#module-1--sourcing-engine)
   - [Module 2 — Email Engine](#module-2--email-engine)
   - [Module 3 — WhatsApp Engine](#module-3--whatsapp-engine)
   - [Module 4 — Orchestrator](#module-4--orchestrator)
6. [Data Flow](#6-data-flow)
7. [Lead Scoring System](#7-lead-scoring-system)
8. [Installation & Setup](#8-installation--setup)
9. [Configuration](#9-configuration)
10. [Running the Engine](#10-running-the-engine)
11. [Testing](#11-testing)
12. [Buyer Management](#12-buyer-management)
13. [WhatsApp Reply Handler](#13-whatsapp-reply-handler)
14. [Database Schema](#14-database-schema)
15. [Sources & APIs](#15-sources--apis)
16. [Known Limitations](#16-known-limitations)
17. [Troubleshooting](#17-troubleshooting)
18. [Future Roadmap](#18-future-roadmap)

---

## 1. Project Overview

### What It Does
```
Every day at 08:00 AM automatically:

  Scrapes 5 industrial marketplaces
         ↓
  Parses 200-400 raw machine listings
         ↓
  Scores each lead 1-10 by quality
         ↓
  Applies your markup (default 17.5%)
         ↓
  Saves to local SQLite database
         ↓
  Deduplicates across days
         ↓
  Sends personalized emails to buyers
         ↓
  Sends personalized WhatsApp messages
         ↓
  Handles buyer replies automatically
         ↓
  Sleeps until tomorrow 08:00 AM
```

### Business Model
```
You act as a machine sourcing intermediary:

  Seller lists machine at $10,000
         ↓
  Your engine finds it automatically
         ↓
  You present it to buyer at $11,750 (+17.5%)
         ↓
  Buyer pays deposit → deal closes
         ↓
  You earn $1,750 commission per deal 💰
```

### Why This Exists
```
Problem:
  Industrial buyers need used CNC machines
  but listings are scattered across dozens
  of platforms in different countries.
  Manual searching takes hours daily.

Solution:
  One automated system that:
  → Aggregates all sources
  → Filters quality listings
  → Delivers to buyers' phones
  → Handles follow-up automatically
```

---

## 2. System Architecture

### High Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    LEAD ENGINE SYSTEM                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  MODULE 4: ORCHESTRATOR               │  │
│  │              (Scheduler + Pipeline Controller)        │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │ controls                            │
│         ┌─────────────┼─────────────┐                      │
│         ▼             ▼             ▼                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │MODULE 1  │  │MODULE 2  │  │MODULE 3  │                  │
│  │Sourcing  │  │  Email   │  │WhatsApp  │                  │
│  │ Engine   │  │ Engine   │  │ Engine   │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │             │             │                         │
│       ▼             ▼             ▼                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │5 Source  │  │  Gmail   │  │  Twilio  │                  │
│  │Websites  │  │  SMTP    │  │   API    │                  │
│  └────┬─────┘  └──────────┘  └──────────┘                  │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────┐                                               │
│  │SQLite DB │  leads.db                                     │
│  │(local)   │                                               │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘
```

### Pipeline Flow
```
08:00 AM — Scheduler triggers
     │
     ▼
[Health Check]
  ✅ Internet connected?
  ✅ Database accessible?
  ✅ Email credentials set?
  ✅ Twilio credentials set?
     │
     ▼
[STEP 1 — FETCH]
  Machinio (VMC query)     → ~80 leads
  Machinio (Lathe query)   → ~60 leads
  Exapro (3 categories)    → ~80 leads
  Surplex (4 categories)   → ~60 leads
  used-machines.net        → ~70 leads
  eBay API (optional)      → ~100 leads
  ─────────────────────────────────────
  Total raw                → ~200-450 leads
     │
     ▼
[STEP 2 — SAVE & DEDUPLICATE]
  Convert to MachineLead objects
  Apply 17.5% markup automatically
  Score each lead 1-10
  Save to leads.db
  Remove duplicates by listing URL
     │
     ▼
[STEP 3 — LOAD TOP LEADS]
  Filter: score ≥ 5
  Filter: price > 0
  Sort: highest score first
  Limit: top 50 leads
     │
     ▼
[STEP 4 — EMAIL BROADCAST]
  For each active buyer with email:
    Filter leads by buyer interests
    Render HTML + text email
    Send via Gmail SMTP
    Wait 1.5s (rate limit)
     │
     ▼
[STEP 5 — WHATSAPP BROADCAST]
  For each active buyer with phone:
    Filter leads by buyer interests
    Format WhatsApp message
    Send via Twilio API
    Wait 2s (rate limit)
     │
     ▼
[STEP 6 — LOG & REPORT]
  Save pipeline_log.json
  Export leads_YYYYMMDD.csv
  Export leads_YYYYMMDD.xlsx
  Print summary to terminal
     │
     ▼
Sleep until tomorrow 08:00 AM 😴
```

### Two-Way Communication Flow
```
YOUR ENGINE          TWILIO           BUYER'S PHONE
    │                  │                   │
    │──── message ────►│──── WhatsApp ────►│
    │                  │                   │
    │                  │◄── "YES 1" ───────│
    │◄─── webhook ─────│                   │
    │                  │                   │
    │── full specs ───►│──── reply ───────►│
    │                  │                   │
    │                  │◄── "CALL" ────────│
    │◄─── webhook ─────│                   │
    │                  │                   │
    │── callback msg ─►│──── reply ───────►│
```

---

## 3. Technology Stack

### Core Language
```
Python 3.12
```

### Dependencies
```
Package          Version    Purpose
────────────────────────────────────────────────────────
requests         latest     HTTP calls to fetch listings
beautifulsoup4   latest     HTML parsing
lxml             latest     HTML parser backend
pandas           latest     Data manipulation / DataFrames
openpyxl         latest     Excel export
jinja2           latest     Email HTML templating
python-dotenv    latest     .env file loading
twilio           latest     WhatsApp messaging API
schedule         latest     Daily pipeline scheduling
rich             latest     Beautiful terminal output
coverage         latest     Test coverage reporting
sqlite3          built-in   Local database (no server needed)
smtplib          built-in   Email sending via SMTP
unittest         built-in   Test framework
```

### External Services
```
Service          Free Tier    Purpose
────────────────────────────────────────────────────────
Gmail SMTP       500/day      Email broadcasting
Twilio WhatsApp  Sandbox      WhatsApp messaging
eBay Finding API 5000/day     Machine listings (optional)
```

### Install All Dependencies
```bash
pip install requests beautifulsoup4 lxml pandas openpyxl \
            jinja2 python-dotenv twilio schedule rich coverage
```

---

## 4. Project Structure

```
lead-engine/
│
├── 📄 .env                        ← All secrets (never commit)
├── 📄 .gitignore                  ← Must include .env
│
├── 🐍 module1_sourcing.py         ← Fetch + Score + DB
├── 🐍 module2_email.py            ← Email broadcast engine
├── 🐍 module3_whatsapp.py         ← WhatsApp broadcast engine
├── 🐍 module4_orchestrator.py     ← Master pipeline controller
├── 🐍 whatsapp_reply_handler.py   ← Flask inbound reply handler
│
├── 📁 tests/
│   ├── 🧪 test_module1.py         ← 33 tests: parse, score, DB
│   ├── 🧪 test_module2.py         ← 15 tests: templates, email
│   ├── 🧪 test_module3.py         ← 17 tests: formatting, WhatsApp
│   ├── 🧪 test_module4.py         ← 12 tests: pipeline, health
│   └── 🧪 test_integration.py     ← 8 tests: end-to-end
│
├── 💾 leads.db                    ← SQLite database (auto-created)
├── 📊 pipeline_log.json           ← Run history (auto-created)
│
└── 📁 reports/                    ← Daily exports (auto-created)
    ├── leads_20261004.csv
    ├── leads_20261004.xlsx
    └── ...
```

---

## 5. Module Breakdown

---

### Module 1 — Sourcing Engine

**File:** `module1_sourcing.py`

**Responsibility:** Fetch machine listings from public
industrial marketplaces, parse and clean the data,
score each lead, and persist to SQLite database.

#### Key Components

##### MachineLead Dataclass
```python
@dataclass
class MachineLead:
    source:          str      # "Machinio", "Exapro" etc.
    title:           str      # "Mazak VTC-200B VMC"
    brand:           str      # "Mazak"
    model:           str      # "VTC-200B"
    year:            str      # "2019"
    original_price:  float    # 10000.0
    your_ask_price:  float    # AUTO: 10000 × 1.175 = 11750.0
    markup_pct:      float    # 17.5 (default)
    currency:        str      # "USD"
    location:        str      # "Germany"
    seller_contact:  str      # contact info if available
    listing_url:     str      # full URL to listing
    category:        str      # AUTO: "VMC", "EDM" etc.
    condition:       str      # "Used", "Refurbished"
    fetched_at:      str      # AUTO: ISO timestamp
    lead_score:      int      # AUTO: 1-10
```

##### Auto-calculations on creation
```python
# 1. Ask price calculated automatically
your_ask_price = original_price × (1 + markup_pct / 100)
# Example: 10000 × 1.175 = 11750.0

# 2. Margin computed as property
margin_usd = your_ask_price - original_price
# Example: 11750 - 10000 = 1750.0

# 3. Lead scored automatically
lead_score = _score()   # see scoring section
```

##### parse_price() — Handles All Price Formats
```python
Input           →  Output
"$12,500"       →  12500.0
"USD 45 000"    →  45000.0
"8.5L"          →  850000.0   (Indian lakh)
"₹1,20,000"     →  120000.0
"POA"           →  0.0
"Call"          →  0.0
""              →  0.0
None            →  0.0
```

##### detect_category() — Auto Tags Machine Type
```python
Title                                  →  Category
"Mazak Vertical Machining Center 2019" →  "VMC"
"Fanuc CNC Lathe turning center"       →  "CNC Lathe"
"Mitsubishi Wire Cut EDM"              →  "EDM"
"Studer Surface Grinding Machine"      →  "Grinding"
"Trumpf Fiber Laser 3015"             →  "Laser"
"Unknown XYZ Machine"                 →  "CNC Other"
```

##### Data Sources
```python
# Tier 1: Public HTML (no auth needed)
fetch_machinio(query, max_pages, markup)
fetch_exapro(max_pages, markup)
fetch_surplex(max_pages, markup)
fetch_used_machines_net(max_pages, markup)

# Tier 2: Official APIs (free key needed)
fetch_ebay_cnc(app_id, keywords, max_results, markup)

# Unified caller (used by orchestrator)
fetch_all_sources(markup, ebay_app_id)
```

##### Database Operations
```python
# Save with automatic deduplication
save_to_db(leads, db_path="leads.db")

# Guard: empty list handled gracefully
if not leads:
    print("⚠️ save_to_db() called with empty list")
    return

# Deduplication SQL
DELETE FROM leads WHERE rowid NOT IN (
    SELECT MIN(rowid) FROM leads GROUP BY listing_url
)

# Load top leads for broadcasting
load_top_leads(db_path, min_score=5, limit=50)
```

---

### Module 2 — Email Engine

**File:** `module2_email.py`

**Responsibility:** Render personalized HTML emails
using Jinja2 templates and deliver them via Gmail SMTP.

#### Key Components

##### Two-Part MIME Email Structure
```
MIMEMultipart("alternative")
├── MIMEText(plain_text, "plain")   ← fallback for old clients
└── MIMEText(html_body,  "html")    ← shown in modern clients
```

##### Jinja2 HTML Template
```
Key template variables:
  {{ buyer_name }}              → personalized greeting
  {{ date }}                    → "04 Oct 2026"
  {{ leads }}                   → list of lead dicts
  {{ lead.title }}              → machine name
  {{ lead.original_price }}     → seller price
  {{ lead.your_ask_price }}     → your price to buyer
  {{ lead.lead_score * 10 }}%   → score bar width
  {{ lead.listing_url }}        → link to listing

Email sections rendered:
  ┌─────────────────────────────────┐
  │  HEADER: title + date           │
  ├─────────────────────────────────┤
  │  GREETING: Hi {buyer_name},     │
  ├─────────────────────────────────┤
  │  LEAD CARDS (loop):             │
  │    Title + Score badge          │
  │    Original → Ask price         │
  │    Score bar (visual %)         │
  │    Location | Year | Category   │
  │    [View Listing →] button      │
  ├─────────────────────────────────┤
  │  FOOTER: unsubscribe note       │
  └─────────────────────────────────┘
```

##### Gmail SMTP Flow
```python
smtplib.SMTP("smtp.gmail.com", 587)
  → ehlo()          # handshake
  → starttls()      # encrypt connection
  → login(email, app_password)
  → sendmail(from, to, message)
  → auto-close (context manager)
```

##### Rate Limiting
```python
time.sleep(1.5)   # between each buyer
# Gmail free: 500 emails/day max
# 1.5s delay prevents spam flags
```

---

### Module 3 — WhatsApp Engine

**File:** `module3_whatsapp.py`

**Responsibility:** Format and send lead messages via
WhatsApp using Twilio API, and handle inbound replies
automatically via a Flask webhook.

#### Key Components

##### Message Format
```
🏭 *Daily Machine Alert — 04 Oct 2026*
Hi Rajesh, here are today's top picks:

*1. Mazak VTC-200B VMC*
   💰 $10,000 → *$11,750* (+17.5%)
   📍 Germany  |  🗓️ 2019
   🏷️ VMC  |  ⭐⭐⭐⭐
   🔗 https://machinio.com/listing/...

─────────────────────────
💬 Reply *YES [number]* to get full specs
📞 Reply *CALL* to schedule inspection
🚫 Reply *STOP* to unsubscribe
```

##### WhatsApp Formatting Rules
```
*text*     → Bold
_text_     → Italic
~text~     → Strikethrough
Max length → 4096 characters
Stars      → capped at 5 (lead_score × 10% maps to ⭐)
URLs       → truncated to 60 chars to avoid layout breaks
```

##### Twilio Integration
```python
client.messages.create(
    from_ = "whatsapp:+14155238886",   # Twilio sandbox
    to    = "whatsapp:+919876543210",  # buyer number
    body  = formatted_message
)
# Returns message SID for delivery tracking
```

##### Inbound Reply Handler Commands
```
Buyer sends  →  System does              →  System replies
─────────────────────────────────────────────────────────
"YES 1"      →  fetch lead #1 from DB   →  full specs + link
"YES 3"      →  fetch lead #3 from DB   →  full specs + link
"CALL"       →  log callback request    →  "We'll call in 2hrs"
"STOP"       →  mark unsubscribed       →  "Unsubscribed ✅"
"LIST"       →  fetch today's leads     →  fresh message
anything     →  show help menu          →  commands list
```

##### Flask Webhook (whatsapp_reply_handler.py)
```python
# Twilio sends POST to your server when buyer replies
@app.route("/whatsapp-reply", methods=["POST"])
def whatsapp_reply():
    incoming = request.form.get("Body").strip().upper()
    # Parse command → fetch from DB → send TwiML response
```

---

### Module 4 — Orchestrator

**File:** `module4_orchestrator.py`

**Responsibility:** Master controller that ties all
three modules together, runs on a daily schedule,
handles errors gracefully, and logs everything.

#### Key Components

##### CONFIG Dictionary
```python
CONFIG = {
    "markup_pct":          17.5,    # margin on every deal
    "min_lead_score":      5,       # quality threshold
    "max_leads_total":     50,      # leads from DB per run
    "max_leads_email":     10,      # leads per email
    "max_leads_whatsapp":  5,       # leads per WhatsApp
    "run_time":            "08:00", # daily schedule time
    "db_path":             "leads.db",
    "ebay_app_id":         "",      # optional eBay key
}
# Change one value here → affects entire pipeline
```

##### BUYER_LIST Structure
```python
BUYER_LIST = [
    {
        "name":      "Rajesh Sharma",
        "email":     "rajesh@autofab.in",
        "phone":     "+919876543210",
        "max_leads": 8,
        "interests": ["VMC", "HMC"],   # filtered leads
        "active":    True,             # False = skip
    },
]
```

##### _filter_for_buyer() — Personalization
```python
# VMC buyer → only VMC leads sent
# EDM buyer → only EDM leads sent
# Empty interests → all categories sent
# No matches → fallback top 5 general leads
```

##### Health Check
```python
health_check() verifies:
  ✅ Internet connectivity (requests.get google.com)
  ✅ Database accessible (sqlite3 connect + SELECT 1)
  ⚠️  Email credentials (warns, non-critical)
  ⚠️  Twilio credentials (warns, non-critical)

Returns:
  True  → safe to run pipeline
  False → abort, log error
```

##### Error Isolation
```python
# Email failure does NOT stop WhatsApp
# WhatsApp failure does NOT stop logging
# One buyer failure does NOT stop other buyers
# Each step wrapped in try/except independently
```

##### Scheduler
```python
schedule.every().day.at("08:00").do(run_daily_pipeline)

while True:
    schedule.run_pending()
    time.sleep(60)       # check every minute
```

---

## 6. Data Flow

### Complete End-to-End Flow
```
INTERNET
  │
  ├── machinio.com/search?q=VMC
  ├── exapro.com/cat/machining-centers
  ├── surplex.com/en/machines/c/machining-centers
  ├── used-machines.net/en/search/machining-center-cnc
  └── svcs.ebay.com/FindingService (API)
  │
  ▼
requests.get() → HTML response
  │
  ▼
BeautifulSoup.select("div[class*='listing']")
  │
  ▼
Extract fields:
  title_el   → raw_title
  price_el   → parse_price() → float
  year_el    → year string
  loc_el     → location string
  link_el    → full URL
  │
  ▼
MachineLead(
  original_price = 10000.0
  your_ask_price = 11750.0   ← auto
  lead_score     = 8         ← auto
  category       = "VMC"     ← auto
)
  │
  ▼
save_to_db()
  → pd.DataFrame([lead.to_dict()])
  → df.to_sql("leads", conn, if_exists="append")
  → DELETE duplicates by listing_url
  │
  ▼
leads.db (SQLite)
  │
  ▼
load_top_leads(min_score=5, limit=50)
  → SELECT * FROM leads
    WHERE lead_score >= 5
    AND original_price > 0
    ORDER BY lead_score DESC
    LIMIT 50
  │
  ├────────────────────────────────────┐
  ▼                                    ▼
EMAIL PATH                         WHATSAPP PATH
  │                                    │
  _filter_for_buyer()              _filter_for_buyer()
  → buyer interests match          → buyer interests match
  │                                    │
  Template(EMAIL_TEMPLATE)         format_whatsapp_message()
  .render(**context)               → *bold* formatting
  → HTML + plain text              → ⭐ star ratings
  │                                → 4096 char limit
  MIMEMultipart build              │
  │                                send_whatsapp()
  smtplib.SMTP                     → client.messages.create()
  → starttls()                     → Twilio API
  → login()                        │
  → sendmail()                     ▼
  │                            BUYER'S PHONE 📱
  ▼
BUYER'S INBOX 📧
```

---

## 7. Lead Scoring System

### Scoring Criteria
```
Condition                              Points
────────────────────────────────────────────
Brand is in known top brands             +3
  (Fanuc, Mazak, Haas, DMG, Okuma,
   Doosan, Makino, Hurco, Brother)

Has a listed price > 0                   +2

Has a year field                         +1

Year is 2018 or newer                    +2

Has seller contact info                  +2
────────────────────────────────────────────
Maximum possible score                   10
```

### Score Examples
```
Machine                                Score  Priority
──────────────────────────────────────────────────────
2021 Mazak VMC with price + contact    10/10  🔥 Top
2019 Haas VF-2 with price              8/10   ✅ High
2020 Unknown brand with price          5/10   ⚠️  Med
Old machine, no price, no contact      1/10   ❌ Skip
```

### Score → WhatsApp Stars
```python
stars = "⭐" * min(lead_score, 5)
# Score 10 → ⭐⭐⭐⭐⭐
# Score 8  → ⭐⭐⭐⭐⭐
# Score 5  → ⭐⭐⭐⭐⭐
# Score 4  → ⭐⭐⭐⭐
# Score 2  → ⭐⭐
# Capped at 5 to fit WhatsApp message width
```

---

## 8. Installation & Setup

### Prerequisites
```
Python 3.10 or higher
pip or pipx
A Gmail account (for sending emails)
A Twilio account (for WhatsApp)
```

### Step 1 — Clone / Create Project
```bash
mkdir lead-engine
cd lead-engine
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# OR
.venv\Scripts\activate          # Windows
```

### Step 2 — Install Dependencies
```bash
pip install requests beautifulsoup4 lxml pandas openpyxl \
            jinja2 python-dotenv twilio schedule rich coverage
```

### Step 3 — Create .env File
```bash
nano .env
```

```env
# ── Email (Gmail) ────────────────────────────────────
EMAIL_SENDER=youremail@gmail.com
EMAIL_PASSWORD=abcdefghijklmnop    # 16-char App Password
EMAIL_SMTP=smtp.gmail.com
EMAIL_PORT=587

# ── Twilio WhatsApp ──────────────────────────────────
TWILIO_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# ── Optional ─────────────────────────────────────────
EBAY_APP_ID=YourApp-XXXX-XXXX        # free at developer.ebay.com
TEST_PHONE_NUMBER=+91XXXXXXXXXX      # your number for testing
SKIP_LIVE_TESTS=false                # true = skip network tests
```

### Step 4 — Gmail App Password
```
1. Go to myaccount.google.com/security
2. Enable 2-Step Verification (required)
3. Search "App Passwords"
4. Select: Mail → Other → type "LeadEngine"
5. Click Generate
6. Copy 16-char password → paste in .env
   ⚠️  Remove spaces: "abcd efgh" → "abcdefgh"
```

### Step 5 — Twilio WhatsApp Sandbox
```
1. Go to twilio.com/try-twilio → free account
2. Console → Messaging → Try WhatsApp
3. Note your sandbox number (+14155238886)
4. Each buyer texts "join <keyword>" to that number
5. Now you can message them via API
```

### Step 6 — Create Test Folder
```bash
mkdir tests
# Copy all test files into tests/
```

### Step 7 — Verify Setup
```bash
python -c "
from dotenv import load_dotenv
import os
load_dotenv()

checks = {
    'EMAIL_SENDER':   os.getenv('EMAIL_SENDER'),
    'EMAIL_PASSWORD': os.getenv('EMAIL_PASSWORD'),
    'TWILIO_SID':     os.getenv('TWILIO_SID'),
    'TWILIO_AUTH':    os.getenv('TWILIO_AUTH'),
}

for key, val in checks.items():
    status = '✅' if val else '❌'
    length = f'({len(val)} chars)' if val else '(missing)'
    print(f'{status} {key}: {length}')
"
```

---

## 9. Configuration

### Adjusting Markup
```python
# In module4_orchestrator.py → CONFIG
"markup_pct": 17.5    # change to 20.0 for 20% margin

# Per deal override: pass markup directly
leads = fetch_all_sources(markup=20.0)
```

### Adjusting Lead Quality Threshold
```python
"min_lead_score": 5   # raise to 7 for stricter quality
                      # lower to 3 for more volume
```

### Adjusting Schedule Time
```python
"run_time": "08:00"   # 24hr format
                      # "14:30" = 2:30 PM
                      # "20:00" = 8:00 PM
```

### Adding a Buyer
```python
BUYER_LIST = [
    {
        "name":      "New Buyer Name",
        "email":     "buyer@company.com",
        "phone":     "+911234567890",      # +countrycode format
        "max_leads": 10,                   # leads per message
        "interests": ["VMC", "CNC Lathe"], # [] = all types
        "active":    True,                 # False = pause
    },
]
```

### Pausing a Buyer
```python
{"name": "Old Contact", ..., "active": False}
# Pipeline skips inactive buyers automatically
```

---

## 10. Running the Engine

### Test SMTP Connection First
```bash
python -c "
import smtplib, os
from dotenv import load_dotenv
load_dotenv()
with smtplib.SMTP('smtp.gmail.com', 587) as s:
    s.ehlo(); s.starttls()
    s.login(os.getenv('EMAIL_SENDER'), os.getenv('EMAIL_PASSWORD'))
    print('✅ Gmail SMTP working')
"
```

### Run Once Manually
```bash
python module4_orchestrator.py
```

### Expected Terminal Output
```
╔══════════════════════════════════════════════╗
║       🏭 CNC LEAD ENGINE — STARTING UP       ║
╠══════════════════════════════════════════════╣
║  Daily run time  : 08:00                     ║
║  Markup          : 17.5%                     ║
║  Min lead score  : 5/10                      ║
║  Active buyers   : 2                         ║
╚══════════════════════════════════════════════╝

🏥 Running health check...
   ✅ Internet          — OK
   ✅ Database          — OK
   ✅ Email credentials  — OK
   ✅ Twilio credentials — OK

📡 STEP 1: Fetching leads from all sources...
  [Machinio] Page 1 'VMC machining center used' → 20 cards
  [Machinio] Page 2 'VMC machining center used' → 18 cards
  ...
  ✅ 287 raw leads fetched

💾 STEP 2: Saving to database...
  💾 DB: 287 new leads saved | 412 total unique leads

🏆 STEP 3: Loading top-scored leads...
  ✅ 50 quality leads selected (score ≥ 5)

  #    Title                     Category   Ask $    Score  Location
  ─────────────────────────────────────────────────────────────────
  1    Mazak VTC-200B VMC        VMC        $11,750  8/10   Germany
  2    Haas VF-2 Vertical        VMC        $8,695   7/10   USA
  ...

📧 STEP 4: Email broadcast...
  ✅ Email → Rajesh Sharma (rajesh@autofab.in)
  ✅ Email → Sanjay Mehta (sanjay@tooldie.co)

📲 STEP 5: WhatsApp broadcast...
  ✅ WhatsApp → Rajesh Sharma (+919876543210)
  ✅ WhatsApp → Sanjay Mehta (+911234567890)

════════════════════════════════════════════════
  📊 PIPELINE COMPLETE — 08:07:43
════════════════════════════════════════════════
  Leads fetched  : 287
  Top leads      : 50
  Emails sent    : 2  (failed: 0)
  WhatsApps sent : 2  (failed: 0)
  ✅ No errors — clean run!
════════════════════════════════════════════════
```

### Keep Running 24/7
```bash
# Option A: simple (stops if terminal closes)
python module4_orchestrator.py

# Option B: background process (Linux)
nohup python module4_orchestrator.py > engine.log 2>&1 &

# Option C: screen session (survives disconnect)
screen -S lead-engine
python module4_orchestrator.py
# Ctrl+A then D to detach

# Option D: systemd service (production)
# Create /etc/systemd/system/lead-engine.service
```

### Deploy WhatsApp Reply Handler
```bash
# Install Flask
pip install flask

# Option A: ngrok (local testing)
python whatsapp_reply_handler.py &
ngrok http 5000
# Copy https URL → paste in Twilio webhook settings

# Option B: Railway.app (free production)
railway login && railway init && railway up

# Set Twilio webhook:
# Console → Messaging → WhatsApp Sandbox Settings
# "When a message comes in" → your URL + /whatsapp-reply
```

---

## 11. Testing

### Test Architecture
```
tests/
├── test_module1.py      33 tests   Sourcing engine
├── test_module2.py      15 tests   Email engine
├── test_module3.py      17 tests   WhatsApp engine
├── test_module4.py      12 tests   Orchestrator
└── test_integration.py   8 tests   End-to-end pipeline
─────────────────────────────────────────────────────
Total                    85 tests
```

### Test Types Used
```
Unit Tests:
  → Test one function in isolation
  → Fast, no network needed
  → Example: test parse_price("8.5L") == 850000.0

Mock Tests:
  → Replace real services with fakes
  → No real emails/WhatsApps sent
  → No real API calls made
  → Example: mock SMTP server counts sendmail() calls

Integration Tests:
  → Test multiple modules working together
  → Real SQLite DB (test DB, cleaned after)
  → Mocked network calls
  → Example: leads saved in M1 flow into M2 email

Live Tests:
  → Hit real websites / send real messages
  → Skipped if credentials not set
  → Example: real email sent to yourself
```

### Running Tests

#### Individual Modules
```bash
# Module 1 — Sourcing (skip live if no internet)
SKIP_LIVE_TESTS=true python tests/test_module1.py

# Module 2 — Email
python tests/test_module2.py

# Module 3 — WhatsApp
python tests/test_module3.py

# Module 4 — Orchestrator
python tests/test_module4.py
```

#### Integration Tests
```bash
python tests/test_integration.py
```

#### All Tests Together
```bash
python -m unittest discover tests/ -v
```

#### With Coverage Report
```bash
coverage run -m unittest discover tests/ -v
coverage report -m
```

#### Expected Coverage
```
Name                        Stmts   Miss  Cover
───────────────────────────────────────────────
module1_sourcing.py           120      8    93%
module2_email.py               85      4    95%
module3_whatsapp.py            95      6    94%
module4_orchestrator.py       140     11    92%
───────────────────────────────────────────────
TOTAL                         440     29    93%
```

### Bugs Found and Fixed During Testing

#### Bug 1 — Module 1: Empty list crashes save_to_db
```
Test:    test_empty_leads_list
Error:   sqlite3.OperationalError: near ")": syntax error
Cause:   pandas tries CREATE TABLE leads () with no columns
Fix:     Added guard: if not leads: return
```

#### Bug 2 — Module 2: Missing import time
```
Test:    test_broadcast_loops_all_buyers
Error:   NameError: name 'time' is not defined
Cause:   broadcast_emails() uses time.sleep() but
         module2_email.py had no import time
Fix:     Added import time at top of module2_email.py
```

#### Bug 3 — Module 2: Wrong test data range
```
Test:    test_price_formatted_in_html
Error:   AssertionError: '10,000' not found in HTML
Cause:   range(1, n+1) made first lead VMC-1 at $12,000
         test looked for $10,000 which never existed
Fix:     Changed to range(0, n) so VMC-0 at $10,000 exists
```

#### Bug 4 — Module 2: Email body is base64 encoded
```
Test:    test_max_leads_respected
Error:   AssertionError: 'Mazak VMC-1' not found in body
Cause:   Emojis in template trigger Python MIME base64 encoding
         Test searched raw bytes, not decoded content
Fix:     Added decode_email_body() helper using
         email.message_from_string() + base64.b64decode()
```

#### Bug 5 — Module 2: Indentation error
```
Error:   IndentationError + NameError: raw_email not defined
Cause:   Pasted fix code landed at class level not inside method
         Python treated it as class-level code
Fix:     Replaced entire test file with correctly indented version
```

#### Bug 6 — Module 3: Missing parameter
```
Test:    test_broadcast_sends_to_all_buyers
Error:   TypeError: unexpected keyword argument 'max_leads_per_msg'
Cause:   broadcast_whatsapp() signature was missing the parameter
Fix:     Added max_leads_per_msg: int = 5 to function signature
```

#### Bug 7 — Module 3: client used before creation
```
Test:    test_broadcast_tracks_failures
Error:   NameError: name 'client' is not defined
Cause:   broadcast_whatsapp() called send_whatsapp(..., client)
         but get_twilio_client() was never called
Fix:     Added client = get_twilio_client() at function start
```

#### Bug 8 — Module 4: requests not imported at module level
```
Test:    test_returns_false_when_no_internet (and 2 others)
Error:   AttributeError: module has no attribute 'requests'
Cause:   health_check() used requests.get() but requests
         was not imported at top of module4_orchestrator.py
Fix:     Added import requests at top of module4_orchestrator.py
         Changed patch path to "requests.get" (at source)
```

#### Bug 9 — Module 4: Client imported locally not at module level
```
Test:    test_full_pipeline_calls_all_steps (and 1 other)
Error:   AttributeError: module has no attribute 'Client'
Cause:   from twilio.rest import Client was inside
         run_daily_pipeline() function body
         patch() can't find names inside function scope
Fix:     Moved import to top of module4_orchestrator.py
         Changed patch to "twilio.rest.Client" (at source)
```

#### Bug 10 — Module 4: Mock leads as strings not MachineLead objects
```
Test:    test_full_pipeline_calls_all_steps
Error:   Pipeline fetches 0 leads, aborts early
Cause:   return_value=["mock_lead"] passes strings
         save_to_db() calls .to_dict() which fails on strings
Fix:     Created make_mock_leads() that returns real
         MachineLead objects save_to_db() can handle
```

### Definition of Done
```
✅ All 85 tests passing
✅ Coverage above 80%
✅ Real email received in inbox
✅ Real WhatsApp received on phone
✅ Full pipeline runs without errors
✅ Leads appear in leads.db
✅ Reports appear in reports/ folder
```

---

## 12. Buyer Management

### Adding Buyers
```python
# In module4_orchestrator.py → BUYER_LIST
{
    "name":      "Company Name",
    "email":     "contact@company.com",
    "phone":     "+919876543210",
    "max_leads": 10,
    "interests": ["VMC", "CNC Lathe"],
    "active":    True,
}
```

### Available Machine Categories
```
"VMC"         Vertical Machining Centers
"HMC"         Horizontal Machining Centers
"CNC Lathe"   CNC Turning / Lathes
"EDM"         Wire Cut / Spark Erosion
"Grinding"    Surface / Cylindrical Grinders
"Press"       Press Brakes / Stamping
"Laser"       Fiber / CO2 Laser Cutting
"Plasma"      Plasma Cutting
"Welding"     Welding Robots
"CNC Other"   Everything else
```

### Buyer Filtering Logic
```
interests = ["VMC", "HMC"]
  → buyer gets only VMC and HMC leads

interests = []
  → buyer gets all categories (top 50)

interests = ["Plasma"]  (nothing available)
  → fallback: buyer gets top 5 general leads
  → warning printed to terminal
```

### Google Sheets Integration (Optional)
```python
# Load buyers from a shared Google Sheet
# instead of editing code directly

buyers = load_buyers_from_sheets(
    sheet_url = "https://docs.google.com/..."
)
# Sheet columns:
# name | email | phone | interests | max_leads | active | tier
```

---

## 13. WhatsApp Reply Handler

**File:** `whatsapp_reply_handler.py`

### Setup
```bash
pip install flask
python whatsapp_reply_handler.py
# Runs on localhost:5000
```

### Expose Publicly
```bash
# For testing
ngrok http 5000
# → https://abc123.ngrok.io

# For production
railway up
# → https://your-app.up.railway.app
```

### Twilio Webhook Config
```
Twilio Console
  → Messaging
  → Settings
  → WhatsApp Sandbox Settings
  → When a message comes in:
    https://your-url.com/whatsapp-reply
  → HTTP POST
  → Save
```

### Conversation Example
```
[08:00] Engine → Rajesh:
  🏭 Daily Machine Alert — 04 Oct 2026
  1. Mazak VTC-200B → $11,750
  2. Haas VF-2      → $8,695
  Reply YES [n] for full specs

[08:15] Rajesh → Engine:
  YES 1

[08:15] Engine → Rajesh:
  Full specs: Mazak VTC-200B
  Price: $11,750 | Year: 2019
  Location: Bavaria, Germany
  Link: machinio.com/listing/...
  Reply CALL to schedule inspection

[08:17] Rajesh → Engine:
  CALL

[08:17] Engine → Rajesh:
  Our team will call within 2 hours.
  Direct: +91-XXXXXXXXXX

[10:00] You call Rajesh → Deal discussed 🤝
        Client pays deposit
        Commission earned 💰
```

---

## 14. Database Schema

### leads Table
```sql
CREATE TABLE leads (
    source          TEXT,     -- "Machinio", "Exapro" etc.
    title           TEXT,     -- full machine title
    brand           TEXT,     -- manufacturer name
    model           TEXT,     -- model number
    year            TEXT,     -- manufacture year
    original_price  REAL,     -- seller's listed price
    your_ask_price  REAL,     -- your price (with markup)
    markup_pct      REAL,     -- markup percentage used
    margin_usd      REAL,     -- your_ask - original
    currency        TEXT,     -- "USD", "EUR" etc.
    location        TEXT,     -- city/country
    seller_contact  TEXT,     -- contact info if scraped
    listing_url     TEXT,     -- full URL (unique key)
    category        TEXT,     -- "VMC", "EDM" etc.
    condition       TEXT,     -- "Used", "Refurbished"
    fetched_at      TEXT,     -- ISO timestamp
    lead_score      INTEGER   -- 1-10 quality score
)
```

### Useful Queries
```sql
-- Top 10 leads today
SELECT title, your_ask_price, lead_score, location
FROM leads
WHERE date(fetched_at) = date('now')
ORDER BY lead_score DESC
LIMIT 10;

-- All VMC leads above score 7
SELECT * FROM leads
WHERE category = 'VMC'
AND lead_score >= 7
AND original_price > 0;

-- Total leads by source
SELECT source, COUNT(*) as count
FROM leads
GROUP BY source
ORDER BY count DESC;

-- Average margin by category
SELECT category,
       ROUND(AVG(margin_usd), 2) as avg_margin,
       COUNT(*) as leads
FROM leads
GROUP BY category;
```

---

## 15. Sources & APIs

### Tier 1 — Public HTML Scraping
```
Source              URL                         Auth    Cost
──────────────────────────────────────────────────────────
Machinio            machinio.com/search         None    Free
Exapro              exapro.com/cat/...          None    Free
Surplex             surplex.com/en/machines/... None    Free
used-machines.net   used-machines.net/en/...    None    Free
```

### Tier 2 — Official APIs
```
Source   URL                              Auth          Cost
──────────────────────────────────────────────────────────
eBay     svcs.ebay.com/FindingService     App ID key   Free tier
```

### Blocked Sources (Cannot Scrape)
```
Source          Reason                    Alternative
──────────────────────────────────────────────────────────
IndiaMART       ToS ban + CAPTCHA         Paid API
Alibaba         Cloudflare + JS render    Official API
MachineryTrader Cloudflare 403            None
IronPlanet      Login required            None
Ritchie Bros    Login + ToS ban           None
Craigslist      Aggressive bot blocking   None
```

---

## 16. Known Limitations

```
1. Website structure changes
   → If a marketplace redesigns their HTML,
     CSS selectors may stop matching
   → Fix: update selectors in fetch_*() functions
   → Symptom: 0 cards found on a source

2. Gmail 500/day limit
   → Free Gmail: 500 emails/day maximum
   → For larger lists use SendGrid free tier

3. Twilio sandbox opt-in requirement
   → Each buyer must text "join <keyword>"
     before receiving sandbox messages
   → Production WhatsApp Business API removes this

4. Training data cutoff
   → Machine prices in DB reflect scrape date
   → Old leads may have outdated prices

5. No image support
   → WhatsApp messages are text only
   → Email has no machine photos (no scraping images)

6. Single timezone schedule
   → Runs at 08:00 in server's local timezone
   → Adjust run_time for your buyers' timezone
```

---

## 17. Troubleshooting

### Engine starts but fetches 0 leads
```
Cause 1: Website changed their HTML structure
  Fix: Open machinio.com manually, inspect a listing card
       Update CSS selector in fetch_machinio()

Cause 2: IP temporarily blocked
  Fix: Wait 1 hour, try again
       Reduce max_pages to be less aggressive

Cause 3: Network/DNS issue
  Fix: python -c "import requests; requests.get('https://machinio.com')"
```

### Emails not sending
```
Cause 1: Wrong App Password
  Fix: Regenerate at myaccount.google.com/apppasswords
       Ensure no spaces in .env

Cause 2: 2FA not enabled
  Fix: Enable at myaccount.google.com/security
       App Passwords require 2FA to be on

Cause 3: Port 587 blocked
  Fix: Try on different network (some corporate networks block it)
```

### WhatsApp not sending
```
Cause 1: Buyer not opted in
  Fix: Buyer must text "join <keyword>" to +14155238886

Cause 2: Wrong phone format
  Fix: Must be +919876543210 not 09876543210

Cause 3: Twilio credentials wrong
  Fix: Check TWILIO_SID starts with "AC"
       TWILIO_AUTH is the auth token not the SID
```

### Tests failing
```
NameError: name 'X' not defined
  → Missing import in the module file

AttributeError: module has no attribute 'X'
  → Patching wrong path in test
  → Check if attribute is at module level

IndentationError: unexpected unindent
  → Code accidentally outside a method
  → Ensure 8 spaces for method body
  → Ensure 4 spaces for class body
```

---

## 18. Future Roadmap

### Phase 2 — Analytics Dashboard
```
Streamlit web dashboard showing:
  → Live lead pipeline visualization
  → Buyer activity tracking
  → Source performance comparison
  → Daily/weekly revenue projections
  → Best-performing machine categories
```

### Phase 3 — CRM Integration
```
  → Google Sheets buyer management
  → Deal stage tracking (lead → deposit → closed)
  → Commission calculation per deal
  → Buyer follow-up reminders
```

### Phase 4 — Expanded Sources
```
  → IndiaMART API integration (paid)
  → Alibaba Official API
  → TradeIndia integration
  → Regional auction house feeds
  → Bankruptcy notice monitoring (IBBI India)
```

### Phase 5 — Intelligence Layer
```
  → Price trend analysis
    (same model tracked across weeks)
  → Fast-moving model detection
    (which machines sell quickest)
  → Demand forecasting by region
  → Automated price negotiation suggestions
```

### Phase 6 — Production Hardening
```
  → Docker containerization
  → AWS/GCP cloud deployment
  → PostgreSQL (replace SQLite)
  → Redis queue for large buyer lists
  → Prometheus + Grafana monitoring
  → SendGrid for email at scale
  → WhatsApp Business API (remove sandbox)
```

---

## Quick Reference

### Most Used Commands
```bash
# Start the engine
python module4_orchestrator.py

# Run all tests
python -m unittest discover tests/ -v

# Run one module test
python tests/test_module1.py

# Check test coverage
coverage run -m unittest discover tests/ -v
coverage report -m

# Check DB stats
sqlite3 leads.db "SELECT source, COUNT(*) FROM leads GROUP BY source;"

# Skip live network tests
SKIP_LIVE_TESTS=true python -m unittest discover tests/ -v
```

### Environment Variables Summary
```bash
EMAIL_SENDER          # Gmail address
EMAIL_PASSWORD        # 16-char App Password (no spaces)
EMAIL_SMTP            # smtp.gmail.com
EMAIL_PORT            # 587
TWILIO_SID            # starts with AC
TWILIO_AUTH           # auth token
TWILIO_WHATSAPP_FROM  # whatsapp:+14155238886
EBAY_APP_ID           # optional
TEST_PHONE_NUMBER     # your number for live tests
SKIP_LIVE_TESTS       # true/false
```

---

*Built with Python 3.12 | Tested on Ubuntu 22.04*
*Last updated: October 2026*
```

---

Save this as `README.md` in your project root:

```bash
nano README.md
# Paste entire content above
# Ctrl+X → Y → Enter to save

# Verify it renders correctly
cat README.md | head -50
```

This README covers every decision we made, every bug we fixed, and every test we wrote — complete documentation for anyone (including future you) picking this up cold. 🚀
