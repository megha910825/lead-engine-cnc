
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
            msg.body(f"Full specs for {lead[1]}:\n"
                     f"Price: ${lead[6]:,.0f}\n"
                     f"Location: {lead[9]}\n"
                     f"Link: {lead[11]}\n\n"
                     f"Reply CALL to schedule inspection.")
        else:
            msg.body("Sorry, lead not found. Reply LIST for fresh options.")

    elif incoming == "CALL":
        msg.body("📞 Our team will call you within 2 hours.\n"
                 "Or call us directly: +91-XXXXXXXXXX")

    elif incoming == "STOP":
        msg.body("You've been unsubscribed. Reply START to re-subscribe anytime.")

    else:
        msg.body("Commands:\n"
                 "YES [number] — get full specs\n"
                 "CALL — schedule inspection\n"
                 "LIST — see today's machines\n"
                 "STOP — unsubscribe")

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000)
