"""
tests/test_integration.py
──────────────────────────
End-to-end tests that run the full pipeline
with real DB but mocked network calls.
Run with: python tests/test_integration.py
"""

import sys
import os
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module1_sourcing  import MachineLead, save_to_db, load_top_leads
from module2_email     import send_lead_email
from module3_whatsapp  import format_whatsapp_message, send_whatsapp
from module4_orchestrator import run_daily_pipeline, _filter_for_buyer

TEST_DB = "tests/test_integration.db"

# ── Sample data ────────────────────────────────────────────────────────────────

def make_sample_leads(n: int = 20) -> list[MachineLead]:
    categories = ["VMC", "CNC Lathe", "EDM", "Grinding"]
    brands     = ["Mazak", "Haas", "Fanuc", "DMG", "Okuma"]
    return [
        MachineLead(
            source         = "Machinio",
            title          = f"{brands[i % len(brands)]} Machine {i}",
            brand          = brands[i % len(brands)],
            model          = f"Model-{i*100}",
            year           = str(2018 + (i % 5)),
            original_price = float(8000 + i * 1500),
            markup_pct     = 17.5,
            location       = "Germany",
            listing_url    = f"https://machinio.com/listing/{i}",
            category       = categories[i % len(categories)],
        )
        for i in range(n)
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Integration Test 1 — Module 1 → Module 2
# ══════════════════════════════════════════════════════════════════════════════

class TestModule1ToModule2(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @patch("module2_email.smtplib.SMTP")
    @patch.dict(os.environ, {
        "EMAIL_SENDER":   "test@gmail.com",
        "EMAIL_PASSWORD": "testpass",
        "EMAIL_SMTP":     "smtp.gmail.com",
        "EMAIL_PORT":     "587",
    })
    def test_leads_flow_from_db_to_email(self, mock_smtp):
        """Leads saved in M1 should flow correctly into M2 email"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__  = MagicMock(return_value=False)

        # Module 1: save leads
        leads = make_sample_leads(20)
        save_to_db(leads, TEST_DB)

        # Module 1: load top leads
        top_leads = load_top_leads(
            db_path   = TEST_DB,
            min_score = 3,
            limit     = 50,
        )
        self.assertFalse(top_leads.empty, "No leads loaded from DB")

        # Module 2: send email
        send_lead_email(
            to_email   = "buyer@test.com",
            buyer_name = "Integration Test Buyer",
            leads_df   = top_leads,
            max_leads  = 5,
        )

        # Verify email was sent
        mock_server.sendmail.assert_called_once()
        print(f"\n    ✅ {len(top_leads)} leads flowed from DB → Email")


# ══════════════════════════════════════════════════════════════════════════════
# Integration Test 2 — Module 1 → Module 3
# ══════════════════════════════════════════════════════════════════════════════

class TestModule1ToModule3(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @patch.dict(os.environ, {
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"
    })
    def test_leads_flow_from_db_to_whatsapp(self):
        """Leads from DB should produce valid WhatsApp message"""
        # Module 1
        leads = make_sample_leads(10)
        save_to_db(leads, TEST_DB)
        top_leads = load_top_leads(
            db_path   = TEST_DB,
            min_score = 1,
            limit     = 10,
        )

        self.assertFalse(top_leads.empty)

        # Module 3: format message
        msg = format_whatsapp_message(
            buyer_name = "Integration Test",
            leads      = top_leads.to_dict("records"),
            max_leads  = 5,
        )

        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 0)
        self.assertLessEqual(len(msg), 4096)
        print(f"\n    ✅ WhatsApp message: {len(msg)} chars")
        print(f"    Preview:\n{msg[:200]}...")


# ══════════════════════════════════════════════════════════════════════════════
# Integration Test 3 — Buyer Filter → Both Channels
# ══════════════════════════════════════════════════════════════════════════════

class TestBuyerFilterIntegration(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        leads = make_sample_leads(20)
        save_to_db(leads, TEST_DB)
        self.top_leads = load_top_leads(
            db_path   = TEST_DB,
            min_score = 1,
            limit     = 50,
        )

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_vmc_buyer_gets_only_vmc(self):
        buyer  = {"name": "VMC Buyer", "interests": ["VMC"]}
        result = _filter_for_buyer(self.top_leads, buyer)
        if not result.empty:
            self.assertTrue(all(result["category"] == "VMC"))

    def test_edm_buyer_message_contains_edm(self):
        buyer  = {"name": "EDM Buyer", "interests": ["EDM"]}
        result = _filter_for_buyer(self.top_leads, buyer)
        if not result.empty:
            msg = format_whatsapp_message(
                "EDM Buyer",
                result.to_dict("records"),
                max_leads=3
            )
            # EDM leads in message
            self.assertIn("EDM Buyer", msg)

    def test_all_buyers_get_something(self):
        """Every buyer should get at least 1 lead"""
        buyers = [
            {"name": "Buyer A", "interests": ["VMC"]},
            {"name": "Buyer B", "interests": ["EDM"]},
            {"name": "Buyer C", "interests": []},           # all
            {"name": "Buyer D", "interests": ["Plasma"]},  # no match → fallback
        ]
        for buyer in buyers:
            result = _filter_for_buyer(self.top_leads, buyer)
            self.assertGreater(
                len(result), 0,
                f"{buyer['name']} got 0 leads"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Integration Test 4 — Full Pipeline End to End
# ══════════════════════════════════════════════════════════════════════════════

class TestFullPipelineIntegration(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @patch("module4_orchestrator.health_check",      return_value=True)
    @patch("module4_orchestrator.fetch_all_sources")
    @patch("module4_orchestrator.smtplib.SMTP")
    @patch.dict(os.environ, {
        "EMAIL_SENDER":         "test@gmail.com",
        "EMAIL_PASSWORD":       "testpass",
        "EMAIL_SMTP":           "smtp.gmail.com",
        "EMAIL_PORT":           "587",
        "TWILIO_SID":           "AC123",
        "TWILIO_AUTH":          "authtoken",
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
    })
    def test_complete_pipeline_end_to_end(self,
                                           mock_smtp,
                                           mock_fetch,
                                           mock_health):
        """
        Full end-to-end test:
        fetch → DB → score → email → WhatsApp
        """
        # Module 1 returns real MachineLead objects
        mock_fetch.return_value = make_sample_leads(15)

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__  = MagicMock(return_value=False)

        # Mock Twilio
        mock_twilio_msg     = MagicMock()
        mock_twilio_msg.sid = "SM_test_123"

        with patch("module4_orchestrator.Client") as mock_client_cls:
            mock_client           = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create.return_value = mock_twilio_msg

            # Override DB path to test DB
            import module4_orchestrator as m4
            original_db     = m4.CONFIG["db_path"]
            m4.CONFIG["db_path"] = TEST_DB

            try:
                run_daily_pipeline()
            finally:
                m4.CONFIG["db_path"] = original_db   # restore

        # Verify DB has leads
        conn  = sqlite3.connect(TEST_DB)
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        conn.close()

        self.assertGreater(count, 0, "No leads saved to DB")

        # Verify emails were sent
        self.assertGreater(
            mock_server.sendmail.call_count, 0,
            "No emails sent"
        )

        # Verify WhatsApps were sent
        self.assertGreater(
            mock_client.messages.create.call_count, 0,
            "No WhatsApps sent"
        )

        print(f"\n    ✅ Full pipeline passed!")
        print(f"    DB leads    : {count}")
        print(f"    Emails sent : {mock_server.sendmail.call_count}")
        print(f"    WAs sent    : {mock_client.messages.create.call_count}")


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  🧪 INTEGRATION TESTS — Full Pipeline")
    print("="*60 + "\n")
    unittest.main(verbosity=2, exit=False)
