"""
tests/test_module4.py
─────────────────────
Tests for: health check, pipeline flow,
           buyer filtering, error handling
Run with: python tests/test_module4.py
"""

import sys
import os
import sqlite3
import unittest
from unittest.mock import patch, MagicMock, call
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module4_orchestrator import (
    run_daily_pipeline,
    health_check,
    _filter_for_buyer,
    _print_summary_table,
    CONFIG,
    BUYER_LIST,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_leads_df(n: int = 10) -> pd.DataFrame:
    categories = ["VMC", "CNC Lathe", "EDM", "Grinding", "VMC"]
    return pd.DataFrame([
        {
            "title":          f"Machine {i}",
            "brand":          "Mazak",
            "year":           "2020",
            "original_price": 10000.0,
            "your_ask_price": 11750.0,
            "markup_pct":     17.5,
            "margin_usd":     1750.0,
            "currency":       "USD",
            "location":       "Germany",
            "listing_url":    f"https://example.com/{i}",
            "category":       categories[i % len(categories)],
            "condition":      "Used",
            "lead_score":     7,
            "source":         "Machinio",
        }
        for i in range(n)
    ])


def make_mock_leads(n: int = 5):
    """
    Return real MachineLead objects so save_to_db() works correctly.
    Using strings like ["mock_lead"] causes save_to_db to fail.
    """
    from module1_sourcing import MachineLead
    return [
        MachineLead(
            source         = "Test",
            title          = f"Test Machine {i}",
            brand          = "Mazak",
            model          = f"VMC-{i}",
            year           = "2020",
            original_price = 10000.0,
            listing_url    = f"https://example.com/{i}",
            category       = "VMC",
        )
        for i in range(n)
    ]


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Health Check
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthCheck(unittest.TestCase):

    # ── Fix: patch "requests.get" directly, not via orchestrator ──────────────

    @patch("requests.get")                          # ← patched at source
    @patch("sqlite3.connect")                       # ← patched at source
    def test_returns_true_when_all_ok(self,
                                       mock_db,
                                       mock_get):
        """Should return True when internet + DB are accessible"""
        mock_get.return_value  = MagicMock(status_code=200)
        mock_conn              = MagicMock()
        mock_db.return_value   = mock_conn

        with patch.dict(os.environ, {
            "EMAIL_SENDER":   "test@test.com",
            "EMAIL_PASSWORD": "pass",
            "TWILIO_SID":     "AC123",
            "TWILIO_AUTH":    "auth",
        }):
            result = health_check()

        self.assertTrue(result)

    @patch("requests.get")                          # ← patched at source
    def test_returns_false_when_no_internet(self, mock_get):
        """Should return False when internet is down"""
        mock_get.side_effect = Exception("No connection")

        with patch("sqlite3.connect") as mock_db:
            mock_db.return_value = MagicMock()
            result = health_check()

        self.assertFalse(result)

    @patch("requests.get")                          # ← patched at source
    @patch("sqlite3.connect")                       # ← patched at source
    def test_returns_false_when_db_fails(self,
                                          mock_db,
                                          mock_get):
        """Should return False when DB is inaccessible"""
        mock_get.return_value = MagicMock(status_code=200)
        mock_db.side_effect   = Exception("DB locked")

        result = health_check()
        self.assertFalse(result)


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — Buyer Filtering
# ══════════════════════════════════════════════════════════════════════════════

class TestBuyerFiltering(unittest.TestCase):

    def setUp(self):
        self.leads_df = make_leads_df(10)

    def test_filter_by_vmc(self):
        """VMC buyer should only get VMC leads"""
        buyer  = {"name": "Test", "interests": ["VMC"]}
        result = _filter_for_buyer(self.leads_df, buyer)
        self.assertTrue(all(result["category"] == "VMC"))

    def test_filter_by_multiple_categories(self):
        """Buyer with multiple interests gets all matching"""
        buyer  = {"name": "Test", "interests": ["VMC", "EDM"]}
        result = _filter_for_buyer(self.leads_df, buyer)
        self.assertTrue(
            all(result["category"].isin(["VMC", "EDM"]))
        )

    def test_no_interests_returns_all(self):
        """Buyer with no interests should get all leads"""
        buyer  = {"name": "Test", "interests": []}
        result = _filter_for_buyer(self.leads_df, buyer)
        self.assertEqual(len(result), len(self.leads_df))

    def test_no_matches_returns_fallback(self):
        """If no category matches return top 5 fallback"""
        buyer  = {"name": "Test", "interests": ["Laser"]}
        result = _filter_for_buyer(self.leads_df, buyer)
        self.assertGreater(len(result), 0)
        self.assertLessEqual(len(result), 5)

    def test_missing_interests_key_returns_all(self):
        """Buyer dict without interests key should get all leads"""
        buyer  = {"name": "Test"}
        result = _filter_for_buyer(self.leads_df, buyer)
        self.assertEqual(len(result), len(self.leads_df))


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — Full Pipeline (All Mocked)
# ══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline(unittest.TestCase):

    def setUp(self):
        self.mock_leads_df = make_leads_df(10)
        self.mock_leads    = make_mock_leads(5)

    @patch("module4_orchestrator.health_check",      return_value=True)
    @patch("module4_orchestrator.fetch_all_sources")
    def test_pipeline_aborts_if_no_leads(self,
                                          mock_fetch,
                                          mock_health):
        """Pipeline should abort gracefully if fetch returns nothing"""
        mock_fetch.return_value = []           # empty — no leads

        try:
            run_daily_pipeline()
        except Exception as e:
            self.fail(f"Pipeline crashed on empty leads: {e}")

    @patch("module4_orchestrator.health_check", return_value=False)
    def test_pipeline_aborts_if_health_fails(self, mock_health):
        """Pipeline should abort if health check fails"""
        with patch("module4_orchestrator.fetch_all_sources") as mock_fetch:
            run_daily_pipeline()
            mock_fetch.assert_not_called()     # fetch should NOT run

    @patch("module4_orchestrator.health_check",      return_value=True)
    @patch("module4_orchestrator.fetch_all_sources")
    @patch("module4_orchestrator.save_to_db")
    @patch("module4_orchestrator.load_top_leads")
    @patch("module4_orchestrator.send_lead_email")
    @patch("module4_orchestrator.send_whatsapp")
    @patch("module4_orchestrator.format_whatsapp_message", return_value="msg")
    def test_full_pipeline_calls_all_steps(
        self,
        mock_fmt,
        mock_wa,
        mock_email,
        mock_load,
        mock_save,
        mock_fetch,
        mock_health,
    ):
        """All pipeline steps should be called"""
        mock_fetch.return_value = self.mock_leads
        mock_load.return_value  = self.mock_leads_df

        with patch.dict(os.environ, {
            "EMAIL_SENDER":         "test@test.com",
            "EMAIL_PASSWORD":       "pass",
            "TWILIO_SID":           "AC123",
            "TWILIO_AUTH":          "auth",
            "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
        }):
            # ── Fix: patch twilio.rest.Client at its source ───
            with patch("twilio.rest.Client") as mock_client_cls:
                mock_client = MagicMock()
                mock_client_cls.return_value = mock_client
                mock_client.messages.create.return_value = MagicMock(
                    sid="SM_test"
                )
                run_daily_pipeline()

        mock_fetch.assert_called_once()        # Step 1 ✅
        mock_save.assert_called_once()         # Step 2 ✅
        mock_load.assert_called_once()         # Step 3 ✅
        mock_email.assert_called()             # Step 4 ✅
        mock_wa.assert_called()                # Step 5 ✅

    @patch("module4_orchestrator.health_check",      return_value=True)
    @patch("module4_orchestrator.fetch_all_sources")
    @patch("module4_orchestrator.save_to_db")
    @patch("module4_orchestrator.load_top_leads")
    @patch("module4_orchestrator.send_lead_email",
           side_effect=Exception("SMTP down"))
    def test_email_failure_doesnt_stop_whatsapp(
        self,
        mock_email,
        mock_load,
        mock_save,
        mock_fetch,
        mock_health,
    ):
        """Email failure should not stop WhatsApp broadcast"""
        mock_fetch.return_value = self.mock_leads
        mock_load.return_value  = self.mock_leads_df

        with patch("module4_orchestrator.send_whatsapp") as mock_wa:
            with patch("module4_orchestrator.format_whatsapp_message",
                       return_value="msg"):
                with patch.dict(os.environ, {
                    "EMAIL_SENDER":         "t@t.com",
                    "EMAIL_PASSWORD":       "p",
                    "TWILIO_SID":           "AC123",
                    "TWILIO_AUTH":          "auth",
                    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
                }):
                    # ── Fix: patch at source ───────────────────
                    with patch("twilio.rest.Client") as mock_client_cls:
                        mock_client = MagicMock()
                        mock_client_cls.return_value = mock_client
                        mock_client.messages.create.return_value = MagicMock(
                            sid="SM_test"
                        )
                        run_daily_pipeline()

            mock_wa.assert_called()            # WhatsApp still ran ✅


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🧪 MODULE 4 TESTS — Orchestrator")
    print("=" * 60 + "\n")
    unittest.main(verbosity=2, exit=False)
