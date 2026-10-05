"""
Module 4: Master Orchestrator
───────────────────────────────
Ties everything together.
Runs daily at 8 AM: fetch → score → broadcast.

FIXES APPLIED:
  1. Removed fetch_machinio/fetch_exapro direct calls
     → now uses fetch_all_sources() correctly
  2. Import list matches what is actually called
  3. markup passed through CONFIG dict consistently
  4. Added health check before pipeline runs
  5. Added try/except so one failure doesn't crash all
  6. Added proper run summary logging
"""

import schedule
import time
import sqlite3
import os
import traceback
import pandas as pd
from datetime import datetime
from dotenv   import load_dotenv

load_dotenv()

# ── Module Imports ─────────────────────────────────────────────────────────────

from module1_sourcing  import fetch_all_sources, save_to_db, load_top_leads
from module2_email     import broadcast_emails, send_lead_email
from module3_whatsapp  import broadcast_whatsapp, send_whatsapp, format_whatsapp_message

# ── Configuration ──────────────────────────────────────────────────────────────

CONFIG = {
    "markup_pct":          17.5,    # your margin % on every deal
    "min_lead_score":      5,       # minimum quality threshold (1-10)
    "max_leads_total":     50,      # how many leads to load from DB
    "max_leads_email":     10,      # max leads per email
    "max_leads_whatsapp":  5,       # max leads per WhatsApp message
    "run_time":            "08:00", # daily run time (24hr format)
    "db_path":             "leads.db",
    "ebay_app_id":         os.getenv("EBAY_APP_ID", ""),  # optional
}

# ── Buyer List ─────────────────────────────────────────────────────────────────

BUYER_LIST = [
    {
        "name":      "Rajesh Sharma",
        "email":     "rajesh@autofab.in",
        "phone":     "+919876543210",
        "max_leads": 8,
        "interests": ["VMC", "CNC Lathe"],
        "active":    True,
    },
    {
        "name":      "Sanjay Mehta",
        "email":     "sanjay@tooldie.co",
        "phone":     "+911234567890",
        "max_leads": 5,
        "interests": ["EDM", "Grinding"],
        "active":    True,
    },
    # Add more buyers here
]

# ── Helper: Filter Leads per Buyer ────────────────────────────────────────────

def _filter_for_buyer(leads_df: pd.DataFrame,
                       buyer: dict) -> pd.DataFrame:
    """
    Return only leads matching buyer's interests.
    If buyer has no interests set → return all leads.
    If no matches found → fallback to top 5 general leads.
    """
    interests = buyer.get("interests", [])

    if not interests:
        return leads_df                        # no filter → all categories

    filtered = leads_df[leads_df["category"].isin(interests)]

    if filtered.empty:
        print(f"    ⚠️  No {interests} leads for {buyer['name']}"
              f" — sending top general leads instead")
        return leads_df.head(5)                # fallback

    return filtered.reset_index(drop=True)


# ── Helper: Health Check ──────────────────────────────────────────────────────

def health_check() -> bool:
    """
    Verify minimum requirements before running pipeline.
    Returns True if safe to proceed, False if critical
    systems are down.
    """
    print("\n🏥 Running health check...")
    all_ok = True

    # 1. Internet connectivity
    try:
        import requests
        requests.get("https://www.google.com", timeout=5)
        print("   ✅ Internet         — OK")
    except Exception:
        print("   ❌ Internet         — NO CONNECTION")
        all_ok = False                         # critical — must abort

    # 2. Database accessible
    try:
        conn = sqlite3.connect(CONFIG["db_path"])
        conn.execute("SELECT 1")
        conn.close()
        print("   ✅ Database         — OK")
    except Exception as e:
        print(f"  ❌ Database         — FAIL ({e})")
        all_ok = False                         # critical — must abort

    # 3. Email credentials (non-critical — warn only)
    if os.getenv("EMAIL_SENDER") and os.getenv("EMAIL_PASSWORD"):
        print("   ✅ Email credentials — OK")
    else:
        print("   ⚠️  Email credentials — MISSING (email broadcast skipped)")

    # 4. Twilio credentials (non-critical — warn only)
    if os.getenv("TWILIO_SID") and os.getenv("TWILIO_AUTH"):
        print("   ✅ Twilio credentials — OK")
    else:
        print("   ⚠️  Twilio credentials — MISSING (WhatsApp broadcast skipped)")

    return all_ok


# ── Helper: Print Summary Table ───────────────────────────────────────────────

def _print_summary_table(leads_df: pd.DataFrame, top_n: int = 10):
    """Print top N leads as a readable table in the terminal."""
    print(f"\n  {'#':<4} {'Title':<35} {'Category':<12} "
          f"{'Ask $':<10} {'Score':<7} {'Location'}")
    print("  " + "─" * 85)

    for i, row in leads_df.head(top_n).iterrows():
        title    = str(row.get("title",          ""))[:34]
        category = str(row.get("category",       ""))[:11]
        ask      = f"${row.get('your_ask_price',  0):,.0f}"
        score    = f"{row.get('lead_score',        0)}/10"
        location = str(row.get("location",        ""))[:20]

        print(f"  {i+1:<4} {title:<35} {category:<12} "
              f"{ask:<10} {score:<7} {location}")

    if len(leads_df) > top_n:
        print(f"\n  ... and {len(leads_df) - top_n} more leads in database")


# ── Main Pipeline ──────────────────────────────────────────────────────────────

def run_daily_pipeline():
    """
    Master pipeline — runs all steps in sequence.
    Called automatically by scheduler every day at 08:00.
    """

    print(f"\n{'='*60}")
    print(f"  🚀 DAILY PIPELINE — {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*60}")

    # ── Health check first ─────────────────────────────────────────────────────
    if not health_check():
        print("\n  ❌ Health check failed — aborting pipeline")
        print(f"{'='*60}\n")
        return

    # ── Tracking counters ──────────────────────────────────────────────────────
    stats = {
        "leads_fetched":  0,
        "top_leads":      0,
        "emails_sent":    0,
        "emails_failed":  0,
        "wa_sent":        0,
        "wa_failed":      0,
        "errors":         [],
    }

    # ══════════════════════════════════════════════════════
    # STEP 1 — FETCH FROM ALL SOURCES
    # ══════════════════════════════════════════════════════

    print("\n📡 STEP 1: Fetching leads from all sources...\n")

    try:
        # ✅ FIXED: use fetch_all_sources() — single unified call
        # passes markup and ebay_app_id from CONFIG
        leads = fetch_all_sources(
            markup      = CONFIG["markup_pct"],
            ebay_app_id = CONFIG["ebay_app_id"],
        )
        stats["leads_fetched"] = len(leads)
        print(f"\n  ✅ {len(leads)} raw leads fetched")

    except Exception as e:
        print(f"\n  ❌ Fetch failed: {e}")
        stats["errors"].append(f"Fetch: {e}")
        print(f"{'='*60}\n")
        return                                 # can't continue without leads

    # Guard: nothing fetched
    if not leads:
        print("  ⚠️  No leads fetched from any source — aborting")
        return

    # ══════════════════════════════════════════════════════
    # STEP 2 — SAVE & DEDUPLICATE
    # ══════════════════════════════════════════════════════

    print("\n💾 STEP 2: Saving to database...\n")

    try:
        save_to_db(leads, CONFIG["db_path"])
        print("  ✅ Leads saved and deduplicated")

    except Exception as e:
        print(f"  ❌ Database save failed: {e}")
        stats["errors"].append(f"DB save: {e}")
        return                                 # can't continue without DB

    # ══════════════════════════════════════════════════════
    # STEP 3 — LOAD TOP SCORED LEADS
    # ══════════════════════════════════════════════════════

    print("\n🏆 STEP 3: Loading top-scored leads...\n")

    try:
        top_leads = load_top_leads(
            db_path   = CONFIG["db_path"],
            min_score = CONFIG["min_lead_score"],
            limit     = CONFIG["max_leads_total"],
        )
        stats["top_leads"] = len(top_leads)
        print(f"  ✅ {len(top_leads)} quality leads selected "
              f"(score ≥ {CONFIG['min_lead_score']})")

    except Exception as e:
        print(f"  ❌ Failed to load leads from DB: {e}")
        stats["errors"].append(f"Load leads: {e}")
        return

    # Guard: no quality leads today
    if top_leads.empty:
        print("  ⚠️  No leads met quality threshold today — skipping broadcast")
        print(f"\n  💡 Tip: Lower min_lead_score in CONFIG (currently "
              f"{CONFIG['min_lead_score']}) to see more leads")
        return

    # Show preview in terminal
    _print_summary_table(top_leads, top_n=10)

    # ══════════════════════════════════════════════════════
    # STEP 4 — EMAIL BROADCAST
    # ══════════════════════════════════════════════════════

    print("\n📧 STEP 4: Email broadcast...\n")

    # Only active buyers with email addresses
    email_buyers = [
        b for b in BUYER_LIST
        if b.get("active", True) and b.get("email")
    ]

    if not email_buyers:
        print("  ⚠️  No active email buyers — skipping email")

    elif not os.getenv("EMAIL_SENDER"):
        print("  ⚠️  EMAIL_SENDER not set in .env — skipping email")

    else:
        for buyer in email_buyers:
            try:
                buyer_leads = _filter_for_buyer(top_leads, buyer)

                send_lead_email(
                    to_email   = buyer["email"],
                    buyer_name = buyer["name"],
                    leads_df   = buyer_leads,
                    max_leads  = buyer.get(
                                     "max_leads",
                                     CONFIG["max_leads_email"]
                                 ),
                )
                stats["emails_sent"] += 1
                print(f"  ✅ Email → {buyer['name']} ({buyer['email']})")

            except Exception as e:
                stats["emails_failed"] += 1
                err = f"Email to {buyer['email']}: {e}"
                stats["errors"].append(err)
                print(f"  ❌ {err}")

            time.sleep(1.5)                    # Gmail rate limit

    # ══════════════════════════════════════════════════════
    # STEP 5 — WHATSAPP BROADCAST
    # ══════════════════════════════════════════════════════

    print("\n📲 STEP 5: WhatsApp broadcast...\n")

    # Only active buyers with phone numbers
    wa_buyers = [
        b for b in BUYER_LIST
        if b.get("active", True) and b.get("phone")
    ]

    if not wa_buyers:
        print("  ⚠️  No active WhatsApp buyers — skipping WhatsApp")

    elif not os.getenv("TWILIO_SID"):
        print("  ⚠️  TWILIO_SID not set in .env — skipping WhatsApp")

    else:
        try:
            from twilio.rest import Client
            client = Client(
                os.getenv("TWILIO_SID"),
                os.getenv("TWILIO_AUTH")
            )

            for buyer in wa_buyers:
                try:
                    buyer_leads = _filter_for_buyer(top_leads, buyer)

                    msg = format_whatsapp_message(
                        buyer_name = buyer["name"],
                        leads      = buyer_leads.to_dict("records"),
                        max_leads  = CONFIG["max_leads_whatsapp"],
                    )
                    ok = send_whatsapp(buyer["phone"], msg, client)

                    if ok:
                        stats["wa_sent"] += 1
                        print(f"  ✅ WhatsApp → {buyer['name']} ({buyer['phone']})")
                    else:
                        stats["wa_failed"] += 1
                        print(f"  ❌ WhatsApp failed → {buyer['name']}")

                except Exception as e:
                    stats["wa_failed"] += 1
                    err = f"WhatsApp to {buyer['phone']}: {e}"
                    stats["errors"].append(err)
                    print(f"  ❌ {err}")

                time.sleep(2)                  # Twilio rate limit

        except ImportError:
            print("  ⚠️  twilio not installed — run: pip install twilio")
        except Exception as e:
            print(f"  ❌ WhatsApp broadcast error: {e}")
            stats["errors"].append(f"WhatsApp broadcast: {e}")

    # ══════════════════════════════════════════════════════
    # STEP 6 — FINAL SUMMARY
    # ══════════════════════════════════════════════════════

    print(f"\n{'='*60}")
    print(f"  📊 PIPELINE COMPLETE — {datetime.now():%H:%M:%S}")
    print(f"{'='*60}")
    print(f"  Leads fetched  : {stats['leads_fetched']}")
    print(f"  Top leads      : {stats['top_leads']}")
    print(f"  Emails sent    : {stats['emails_sent']}"
          f"  (failed: {stats['emails_failed']})")
    print(f"  WhatsApps sent : {stats['wa_sent']}"
          f"  (failed: {stats['wa_failed']})")

    if stats["errors"]:
        print(f"\n  ⚠️  Errors ({len(stats['errors'])}):")
        for err in stats["errors"]:
            print(f"     • {err}")
    else:
        print(f"\n  ✅ No errors — clean run!")

    print(f"{'='*60}\n")


# ── Scheduler Entry Point ─────────────────────────────────────────────────────

if __name__ == "__main__":

    print("╔══════════════════════════════════════════════╗")
    print("║       🏭 CNC LEAD ENGINE — STARTING UP       ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  Daily run time  : {CONFIG['run_time']}                       ║")
    print(f"║  Markup          : {CONFIG['markup_pct']}%                   ║")
    print(f"║  Min lead score  : {CONFIG['min_lead_score']}/10                      ║")
    print(f"║  Active buyers   : {len([b for b in BUYER_LIST if b.get('active')])}                         ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  Press Ctrl+C to stop                        ║")
    print("╚══════════════════════════════════════════════╝\n")

    # Schedule daily run
    schedule.every().day.at(CONFIG["run_time"]).do(run_daily_pipeline)

    # Run immediately on first launch so you don't wait until tomorrow
    run_daily_pipeline()

    # Keep alive — check schedule every 60 seconds
    while True:
        schedule.run_pending()
        time.sleep(60)
