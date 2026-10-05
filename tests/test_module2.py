"""
tests/test_module2.py
─────────────────────
Tests for: template rendering, MIME building,
           email sending (mock + live)
Run with: python tests/test_module2.py
"""

import sys
import os
import unittest
import base64
import email as email_lib
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module2_email import (
    send_lead_email,
    broadcast_emails,
    EMAIL_TEMPLATE,
    TEXT_TEMPLATE,
)
from jinja2 import Template


# ── Sample test data ───────────────────────────────────────────────────────────

def make_test_leads_df(n: int = 5) -> pd.DataFrame:
    """Create a fake leads DataFrame for testing."""
    return pd.DataFrame([
        {
            "title":          f"Mazak VMC-{i}",
            "brand":          "Mazak",
            "model":          f"VTC-{i * 100}",
            "year":           str(2018 + i),
            "original_price": float(10000 + i * 2000),
            "your_ask_price": float(11750 + i * 2350),
            "markup_pct":     17.5,
            "margin_usd":     float(1750 + i * 350),
            "currency":       "USD",
            "location":       "Germany",
            "listing_url":    f"https://machinio.com/listing/{i}",
            "category":       "VMC",
            "condition":      "Used",
            "lead_score":     7 + (i % 3),
            "source":         "Machinio",
        }
        for i in range(0, n)            # ← starts at 0: VMC-0, VMC-1 ...
    ])


# ── Helper: decode base64 email body ──────────────────────────────────────────

def decode_email_body(raw_email) -> str:
    """
    Emails with emojis get base64 encoded by Python's MIME library.
    This decodes all parts back to readable text for assertions.
    """
    if isinstance(raw_email, bytes):
        raw_email = raw_email.decode("utf-8", errors="ignore")

    decoded_parts = [raw_email]                # always include raw too

    try:
        msg = email_lib.message_from_string(raw_email)
        for part in msg.walk():
            cte     = part.get("Content-Transfer-Encoding", "")
            payload = part.get_payload()

            if cte.lower() == "base64" and isinstance(payload, str):
                try:
                    decoded = base64.b64decode(
                        payload.replace("\n", "")
                    ).decode("utf-8", errors="ignore")
                    decoded_parts.append(decoded)
                except Exception:
                    pass                       # skip malformed chunks
    except Exception:
        pass

    return "\n".join(decoded_parts)


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Template Rendering
# ══════════════════════════════════════════════════════════════════════════════

class TestTemplateRendering(unittest.TestCase):

    def setUp(self):
        self.leads_df   = make_test_leads_df(5)
        self.leads_list = self.leads_df.to_dict("records")
        self.context    = {
            "batch_title": "Test Batch",
            "subtitle":    "5 machines matched",
            "date":        "04 Oct 2026",
            "buyer_name":  "Test Buyer",
            "leads":       self.leads_list,
            "sender_name": "Test Sender",
        }

    def test_html_template_renders(self):
        """HTML template should render without errors"""
        try:
            html = Template(EMAIL_TEMPLATE).render(**self.context)
            self.assertIsInstance(html, str)
            self.assertGreater(len(html), 100)
        except Exception as e:
            self.fail(f"HTML template render failed: {e}")

    def test_text_template_renders(self):
        """Text template should render without errors"""
        try:
            text = Template(TEXT_TEMPLATE).render(**self.context)
            self.assertIsInstance(text, str)
            self.assertGreater(len(text), 50)
        except Exception as e:
            self.fail(f"Text template render failed: {e}")

    def test_buyer_name_in_html(self):
        """Buyer name should appear in rendered HTML"""
        html = Template(EMAIL_TEMPLATE).render(**self.context)
        self.assertIn("Test Buyer", html)

    def test_buyer_name_in_text(self):
        """Buyer name should appear in rendered text"""
        text = Template(TEXT_TEMPLATE).render(**self.context)
        self.assertIn("Test Buyer", text)

    def test_all_leads_in_html(self):
        """All lead titles should appear in HTML"""
        html = Template(EMAIL_TEMPLATE).render(**self.context)
        for lead in self.leads_list:
            self.assertIn(lead["title"], html)

    def test_price_formatted_in_html(self):
        """Prices should be formatted with commas"""
        html = Template(EMAIL_TEMPLATE).render(**self.context)
        self.assertIn("10,000", html)          # VMC-0 original_price=10,000

    def test_score_bar_in_html(self):
        """Score bar should be in HTML"""
        html = Template(EMAIL_TEMPLATE).render(**self.context)
        self.assertIn("score-fill", html)
        self.assertIn("score-bar",  html)

    def test_empty_leads_no_crash(self):
        """Empty leads list should not crash template"""
        context = {**self.context, "leads": []}
        try:
            html = Template(EMAIL_TEMPLATE).render(**context)
            self.assertIsInstance(html, str)
        except Exception as e:
            self.fail(f"Empty leads crashed template: {e}")

    def test_special_chars_in_title(self):
        """Special characters in title should not crash"""
        context = {**self.context}
        context["leads"][0]["title"] = "Mazak <VMC> & 'Lathe' 2019"
        try:
            html = Template(EMAIL_TEMPLATE).render(**context)
            self.assertIsInstance(html, str)
        except Exception as e:
            self.fail(f"Special chars crashed template: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — Email Sending (Mocked — no real emails sent)
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailSending(unittest.TestCase):

    def setUp(self):
        self.leads_df = make_test_leads_df(5)

    def _make_mock_server(self):
        """Reusable mock SMTP server."""
        mock_server = MagicMock()
        mock_server.sendmail.return_value = {}
        return mock_server

    # ── Test 1 ─────────────────────────────────────────────────────────────────

    @patch("module2_email.smtplib.SMTP")
    @patch.dict(os.environ, {
        "EMAIL_SENDER":   "test@gmail.com",
        "EMAIL_PASSWORD": "testpassword1",
        "EMAIL_SMTP":     "smtp.gmail.com",
        "EMAIL_PORT":     "587",
    })
    def test_send_lead_email_calls_smtp(self, mock_smtp):
        """send_lead_email should connect to SMTP server"""
        mock_server = self._make_mock_server()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__  = MagicMock(return_value=False)

        send_lead_email(
            to_email   = "buyer@test.com",
            buyer_name = "Test Buyer",
            leads_df   = self.leads_df,
        )

        mock_smtp.assert_called_with("smtp.gmail.com", 587)

    # ── Test 2 ─────────────────────────────────────────────────────────────────

    @patch("module2_email.smtplib.SMTP")
    @patch.dict(os.environ, {
        "EMAIL_SENDER":   "test@gmail.com",
        "EMAIL_PASSWORD": "testpassword1",
        "EMAIL_SMTP":     "smtp.gmail.com",
        "EMAIL_PORT":     "587",
    })
    def test_send_lead_email_calls_sendmail(self, mock_smtp):
        """send_lead_email should call sendmail"""
        mock_server = self._make_mock_server()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__  = MagicMock(return_value=False)

        send_lead_email(
            to_email   = "buyer@test.com",
            buyer_name = "Test Buyer",
            leads_df   = self.leads_df,
        )

        mock_server.sendmail.assert_called_once()

    # ── Test 3 ─────────────────────────────────────────────────────────────────

    @patch("module2_email.smtplib.SMTP")
    @patch.dict(os.environ, {
        "EMAIL_SENDER":   "test@gmail.com",
        "EMAIL_PASSWORD": "testpassword1",
        "EMAIL_SMTP":     "smtp.gmail.com",
        "EMAIL_PORT":     "587",
    })
    def test_broadcast_loops_all_buyers(self, mock_smtp):
        """broadcast_emails should send to every buyer"""
        mock_server = self._make_mock_server()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__  = MagicMock(return_value=False)

        buyers = [
            {"name": "Buyer 1", "email": "b1@test.com"},
            {"name": "Buyer 2", "email": "b2@test.com"},
            {"name": "Buyer 3", "email": "b3@test.com"},
        ]

        broadcast_emails(buyers, self.leads_df)

        self.assertEqual(mock_server.sendmail.call_count, 3)

    # ── Test 4 ─────────────────────────────────────────────────────────────────

    @patch("module2_email.smtplib.SMTP")
    @patch.dict(os.environ, {
        "EMAIL_SENDER":   "test@gmail.com",
        "EMAIL_PASSWORD": "testpassword1",
        "EMAIL_SMTP":     "smtp.gmail.com",
        "EMAIL_PORT":     "587",
    })
    def test_max_leads_respected(self, mock_smtp):
        """Email should contain only max_leads leads"""
        mock_server = self._make_mock_server()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__  = MagicMock(return_value=False)

        large_df = make_test_leads_df(20)

        send_lead_email(
            to_email   = "test@test.com",
            buyer_name = "Test",
            leads_df   = large_df,
            max_leads  = 3,                    # ← only 3 leads allowed
        )

        # ── Decode the base64 encoded email body ──────────────
        call_args    = mock_server.sendmail.call_args
        raw_email    = call_args[0][2]         # 3rd positional arg
        full_content = decode_email_body(raw_email)

        # ── Only 3 leads should be present ────────────────────
        self.assertIn("Mazak VMC-0",    full_content)   # lead 1 ✅
        self.assertIn("Mazak VMC-1",    full_content)   # lead 2 ✅
        self.assertIn("Mazak VMC-2",    full_content)   # lead 3 ✅
        self.assertNotIn("Mazak VMC-3", full_content)   # lead 4 absent ✅

    # ── Test 5 ─────────────────────────────────────────────────────────────────

    def test_send_handles_smtp_error_gracefully(self):
        """SMTP failure should not crash the program"""
        with patch("module2_email.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("Connection refused")
            try:
                send_lead_email(
                    to_email   = "test@test.com",
                    buyer_name = "Test",
                    leads_df   = self.leads_df,
                )
            except Exception as e:
                self.fail(f"SMTP error was not handled gracefully: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — Live Email Test
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveEmail(unittest.TestCase):

    @unittest.skipIf(
        not os.getenv("EMAIL_SENDER"),
        "EMAIL_SENDER not set in .env — skipping live email test"
    )
    def test_send_real_email_to_self(self):
        """Send a real test email to yourself to verify formatting"""
        leads_df = make_test_leads_df(3)

        try:
            send_lead_email(
                to_email    = os.getenv("EMAIL_SENDER"),
                buyer_name  = "TEST — Please ignore",
                leads_df    = leads_df,
                batch_title = "🧪 TEST EMAIL — Module 2 Verification",
                max_leads   = 3,
            )
            print("\n    ✅ Real email sent — check your inbox!")

        except Exception as e:
            self.fail(f"Live email send failed: {e}")


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🧪 MODULE 2 TESTS — Email Engine")
    print("=" * 60 + "\n")
    unittest.main(verbosity=2, exit=False)
