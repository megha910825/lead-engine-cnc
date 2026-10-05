"""
Module 2: Email Broadcast Engine
──────────────────────────────────
Sends clean, professional lead emails
using Jinja2 HTML templates + Gmail SMTP.
"""

import smtplib
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from jinja2               import Template
from dotenv               import load_dotenv
import pandas             as pd
from datetime             import datetime

load_dotenv()

# ── HTML Email Template ────────────────────────────────────────────────────────

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body        { font-family: Arial, sans-serif; background: #f5f5f5; }
    .container  { max-width: 680px; margin: auto; background: white;
                  border-radius: 8px; overflow: hidden; }
    .header     { background: #1a1a2e; color: white; padding: 24px 32px; }
    .header h1  { margin: 0; font-size: 22px; }
    .header p   { margin: 4px 0 0; opacity: 0.7; font-size: 13px; }
    .body       { padding: 24px 32px; }
    .lead-card  { border: 1px solid #e0e0e0; border-radius: 6px;
                  padding: 16px; margin-bottom: 16px; background: #fafafa; }
    .lead-title { font-size: 16px; font-weight: bold; color: #1a1a2e; }
    .badge      { display: inline-block; background: #e8f5e9; color: #2e7d32;
                  border-radius: 4px; padding: 2px 8px; font-size: 12px;
                  font-weight: bold; margin-left: 8px; }
    .price-row  { margin: 10px 0; }
    .orig-price { color: #888; text-decoration: line-through; font-size: 14px; }
    .ask-price  { color: #c62828; font-size: 18px; font-weight: bold; }
    .margin     { color: #2e7d32; font-size: 13px; margin-left: 8px; }
    .meta       { font-size: 12px; color: #666; margin-top: 8px; }
    .cta        { display: inline-block; background: #1a1a2e; color: white;
                  padding: 10px 20px; border-radius: 4px; text-decoration: none;
                  font-size: 14px; margin-top: 10px; }
    .footer     { background: #f0f0f0; padding: 16px 32px;
                  font-size: 12px; color: #888; text-align: center; }
    .score-bar  { height: 6px; background: #e0e0e0; border-radius: 3px; margin-top: 8px; }
    .score-fill { height: 6px; background: #43a047; border-radius: 3px; }
  </style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>🏭 {{ batch_title }}</h1>
    <p>{{ subtitle }} &nbsp;|&nbsp; {{ date }}</p>
  </div>

  <div class="body">
    <p>Hi {{ buyer_name }},</p>
    <p>Here are today's best-matched machines based on your requirements.
       These are <strong>sourced, verified, and ready to inspect</strong>.</p>

    {% for lead in leads %}
    <div class="lead-card">
      <div class="lead-title">
        {{ loop.index }}. {{ lead.title }}
        <span class="badge">Score {{ lead.lead_score }}/10</span>
      </div>

      <div class="price-row">
        <span class="orig-price">{{ lead.currency }} {{ "{:,.0f}".format(lead.original_price) }}</span>
        &nbsp;→&nbsp;
        <span class="ask-price">{{ lead.currency }} {{ "{:,.0f}".format(lead.your_ask_price) }}</span>
        <span class="margin">(+{{ lead.markup_pct }}% service fee included)</span>
      </div>

      <div class="score-bar">
        <div class="score-fill" style="width: {{ lead.lead_score * 10 }}%;"></div>
      </div>

      <div class="meta">
        📍 {{ lead.location }} &nbsp;|&nbsp;
        🗓️ Year: {{ lead.year or 'N/A' }} &nbsp;|&nbsp;
        🏷️ {{ lead.category }} &nbsp;|&nbsp;
        📦 Condition: {{ lead.condition or 'Used' }}
      </div>

      {% if lead.listing_url %}
      <a class="cta" href="{{ lead.listing_url }}" target="_blank">
        View Listing →
      </a>
      {% endif %}
    </div>
    {% endfor %}

    <hr style="margin: 24px 0; border: none; border-top: 1px solid #eee;">
    <p style="font-size:13px; color:#555;">
      💬 Interested in any of these? Reply to this email or WhatsApp us directly.<br>
      We handle inspection, logistics, and payment security so you don't have to.
    </p>
  </div>

  <div class="footer">
    You're receiving this because you opted into our machine alerts.<br>
    Reply STOP to unsubscribe. &nbsp;|&nbsp; {{ sender_name }}
  </div>

</div>
</body>
</html>
"""

# ── Plain Text Fallback ────────────────────────────────────────────────────────

TEXT_TEMPLATE = """
{{ batch_title }} | {{ date }}
Hi {{ buyer_name }},

Today's top CNC/VMC deals matched to your profile:

{% for lead in leads %}
{{ loop.index }}. {{ lead.title }}
   Price: {{ lead.currency }} {{ "{:,.0f}".format(lead.your_ask_price) }}
   Year: {{ lead.year or 'N/A' }} | Location: {{ lead.location }}
   Score: {{ lead.lead_score }}/10
   Link: {{ lead.listing_url }}
{% endfor %}

Reply to this email or WhatsApp us to express interest.
{{ sender_name }}
"""

# ── Send Function ──────────────────────────────────────────────────────────────

def send_lead_email(
    to_email:     str,
    buyer_name:   str,
    leads_df:     pd.DataFrame,
    batch_title:  str = "🏭 Today's Top CNC/VMC Machines",
    sender_name:  str = "Your Machine Sourcing Partner",
    max_leads:    int = 10
):
    """
    Send a formatted lead digest email to one buyer.
    leads_df: DataFrame from load_top_leads()
    """
    leads_list = leads_df.head(max_leads).to_dict("records")

    # Render templates
    context = {
        "batch_title": batch_title,
        "subtitle":    f"{len(leads_list)} machines matched",
        "date":        datetime.now().strftime("%d %b %Y"),
        "buyer_name":  buyer_name,
        "leads":       leads_list,
        "sender_name": sender_name,
    }
    html_body = Template(EMAIL_TEMPLATE).render(**context)
    text_body = Template(TEXT_TEMPLATE).render(**context)

    # Build MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{batch_title} — {datetime.now():%d %b %Y}"
    msg["From"]    = os.getenv("EMAIL_SENDER")
    msg["To"]      = to_email

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))   # HTML wins if supported

    # Send via SMTP
    try:
        with smtplib.SMTP(os.getenv("EMAIL_SMTP"), int(os.getenv("EMAIL_PORT"))) as server:
            server.ehlo()
            server.starttls()
            server.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            server.sendmail(os.getenv("EMAIL_SENDER"), to_email, msg.as_string())
        print(f"  ✅ Email sent to {buyer_name} <{to_email}>")
    except Exception as e:
        print(f"  ❌ Failed to send to {to_email}: {e}")



def filter_leads_for_buyer(leads_df: pd.DataFrame,
                            interests: list[str]) -> pd.DataFrame:
    """
    Filter leads to match buyer's stated interests.
    interests = ["VMC", "CNC Lathe"]
    """
    if not interests:
        return leads_df  # no filter = send all

    mask = leads_df["category"].isin(interests)
    filtered = leads_df[mask]

    # Fallback: if no exact match, send top general leads
    if filtered.empty:
        return leads_df.head(5)

    return filtered


# Then in broadcast_emails():
def broadcast_emails(buyer_list: list[dict],
                     leads_df: pd.DataFrame):
    for buyer in buyer_list:

        # ← Add this personalization step
        buyer_leads = filter_leads_for_buyer(
            leads_df,
            interests = buyer.get("interests", [])
        )

        send_lead_email(
            to_email   = buyer["email"],
            buyer_name = buyer["name"],
            leads_df   = buyer_leads,        # ← personalized
            max_leads  = buyer.get("max_leads", 10),
        )
        time.sleep(1.5)
