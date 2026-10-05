"""
Module 3: WhatsApp Broadcast Engine
─────────────────────────────────────
Uses Twilio WhatsApp sandbox (free) or
Business API for formatted lead messages.
"""

from twilio.rest import Client
from dotenv      import load_dotenv
import os
import pandas as pd
from datetime import datetime

load_dotenv()

# ── Twilio Client ──────────────────────────────────────────────────────────────

def get_twilio_client() -> Client:
    return Client(
        os.getenv("TWILIO_SID"),
        os.getenv("TWILIO_AUTH")
    )


# ── Message Formatter ──────────────────────────────────────────────────────────

def format_whatsapp_message(buyer_name: str,
                             leads: list[dict],
                             max_leads: int = 5) -> str:
    """
    WhatsApp messages support basic formatting.
    Keep under 4096 chars. Send top 5 per message.
    """
    lines = [
        f"🏭 *Daily Machine Alert — {datetime.now():%d %b %Y}*",
        f"Hi {buyer_name}, here are today's top picks:\n",
    ]

    for i, lead in enumerate(leads[:max_leads], 1):
        orig  = f"${lead['original_price']:,.0f}"  if lead['original_price'] else "POA"
        ask   = f"${lead['your_ask_price']:,.0f}"  if lead['your_ask_price'] else "POA"
        score = "⭐" * min(lead['lead_score'], 5)

        lines += [
            f"*{i}. {lead['title']}*",
            f"   💰 {orig} → *{ask}* (+{lead['markup_pct']}%)",
            f"   📍 {lead['location']}  |  🗓️ {lead.get('year','N/A')}",
            f"   🏷️ {lead['category']}  |  {score}",
            f"   🔗 {lead['listing_url'][:60]}..." if len(lead.get('listing_url','')) > 60
                else f"   🔗 {lead.get('listing_url','')}",
            "",
        ]

    lines += [
        "─────────────────────────",
        "💬 Reply *YES [number]* to get full specs",
        "📞 Reply *CALL* to schedule an inspection",
        "🚫 Reply *STOP* to unsubscribe",
    ]

    return "\n".join(lines)


# ── Single Send ────────────────────────────────────────────────────────────────

def send_whatsapp(to_number: str,
                  message:   str,
                  client:    Client = None) -> bool:
    """
    Send one WhatsApp message via Twilio.
    to_number format: "+919876543210"
    """
    if client is None:
        client = get_twilio_client()

    try:
        msg = client.messages.create(
            from_= os.getenv("TWILIO_WHATSAPP_FROM"),
            to   = f"whatsapp:{to_number}",
            body = message
        )
        print(f"  ✅ WhatsApp sent to {to_number} | SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"  ❌ WhatsApp failed for {to_number}: {e}")
        return False


# ── Broadcast ──────────────────────────────────────────────────────────────────

def broadcast_whatsapp(buyer_list: list[dict],
                        leads_df: pd.DataFrame,
                        max_leads_per_msg: int = 5):
    """
    buyer_list = [
        {"name": "Rajesh", "phone": "+919876543210"},
        {"name": "Sanjay", "phone": "+911234567890"},
    ]
    """
    client      = get_twilio_client()
    leads_list  = leads_df.to_dict("records")
    sent = failed = 0

    print(f"\n📲 WhatsApp broadcast → {len(buyer_list)} buyers...\n")

    for buyer in buyer_list:
        msg = format_whatsapp_message(
            buyer_name = buyer["name"],
            leads      = leads_list,
            max_leads  = max_leads_per_msg
        )
        ok = send_whatsapp(buyer["phone"], msg, client)
        if ok: sent += 1
        else:  failed += 1

        import time; time.sleep(2)  # Twilio rate limit

    print(f"\n📊 Broadcast result: {sent} sent | {failed} failed")


# ── Inbound Reply Handler ──────────────────────────────────────────────────────
# Deploy this with Flask to handle buyer replies automatically

REPLY_LOGIC = """
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import sqlite3

app = Flask(__name__)

@app.route("/whatsapp-reply", methods=["POST"])
def whatsapp_reply():
    incoming = request.form.get("Body", "").strip().upper()
    from_num = request.form.get("From", "")
    resp     = MessagingResponse()
    msg      = resp.message()

    if incoming.startswith("YES"):
        # Extract lead number
        parts = incoming.split()
        lead_no = int(parts[1]) if len(parts) > 1 else 1
        # Fetch full specs from DB
        conn = sqlite3.connect("leads.db")
        lead = conn.execute(
            "SELECT * FROM leads ORDER BY lead_score DESC LIMIT 1 OFFSET ?",
            (lead_no - 1,)
        ).fetchone()
        conn.close()
        if lead:
            msg.body(f"Full specs for {lead[1]}:\\n"
                     f"Price: ${lead[6]:,.0f}\\n"
                     f"Location: {lead[9]}\\n"
                     f"Link: {lead[11]}\\n\\n"
                     f"Reply CALL to schedule inspection.")
        else:
            msg.body("Sorry, lead not found. Reply LIST for fresh options.")

    elif incoming == "CALL":
        msg.body("📞 Our team will call you within 2 hours.\\n"
                 "Or call us directly: +91-XXXXXXXXXX")

    elif incoming == "STOP":
        msg.body("You've been unsubscribed. Reply START to re-subscribe anytime.")

    else:
        msg.body("Commands:\\n"
                 "YES [number] — get full specs\\n"
                 "CALL — schedule inspection\\n"
                 "LIST — see today's machines\\n"
                 "STOP — unsubscribe")

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000)
"""

print("💡 Inbound reply handler code saved to: whatsapp_reply_handler.py")
with open("whatsapp_reply_handler.py", "w") as f:
    f.write(REPLY_LOGIC)


# Check if message was actually read
def check_delivery(sid: str, client: Client) -> str:
    status = client.messages(sid).fetch().status
    # "queued" → "sent" → "delivered" → "read"
    return status

# Track opt-outs properly
def handle_stop(phone: str, db_path: str = "leads.db"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO unsubscribed "
        "(phone, timestamp) VALUES (?, ?)",
        (phone, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# Check before sending
def is_unsubscribed(phone: str) -> bool:
    conn = sqlite3.connect(db_path)
    row  = conn.execute(
        "SELECT 1 FROM unsubscribed WHERE phone=?",
        (phone,)
    ).fetchone()
    conn.close()
    return row is not None

# Same pattern as Module 2
def broadcast_whatsapp(buyer_list: list[dict],
                        leads_df: pd.DataFrame,
                        max_leads_per_msg: int = 5):   # ← Fix 1: add parameter
    """
    buyer_list = [
        {"name": "Rajesh", "phone": "+919876543210"},
        {"name": "Sanjay", "phone": "+911234567890"},
    ]
    """
    leads_list = leads_df.to_dict("records")
    sent = failed = 0

    # ── Fix 2: create client ONCE here ────────────────────────
    try:
        client = get_twilio_client()             # ← Fix 2: create client
    except Exception as e:
        print(f"  ❌ Twilio client creation failed: {e}")
        return

    print(f"\n📲 WhatsApp broadcast → {len(buyer_list)} buyers...\n")

    for buyer in buyer_list:
        try:
            msg = format_whatsapp_message(
                buyer_name = buyer["name"],
                leads      = leads_list,
                max_leads  = max_leads_per_msg,  # ← Fix 1: use parameter
            )
            ok = send_whatsapp(buyer["phone"], msg, client)
            if ok: sent   += 1
            else:  failed += 1

        except Exception as e:
            failed += 1
            print(f"  ❌ Failed for {buyer.get('phone', '?')}: {e}")

        import time; time.sleep(2)

    print(f"\n📊 Broadcast result: {sent} sent | {failed} failed")

