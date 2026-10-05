"""
tests/test_module3.py
─────────────────────
Tests for: message formatting, Twilio calls,
           reply handler, broadcast
Run with: python tests/test_module3.py
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module3_whatsapp import (
    format_whatsapp_message,
    send_whatsapp,
    broadcast_whatsapp,
)

# ── Sample data ────────────────────────────────────────────────────────────────

def make_test_leads(n: int = 5) -> list[dict]:
    return [
        {
            "title":          f"Mazak VMC-{i}",
            "brand":          "Mazak",
            "year":           str(2018 + i),
            "original_price": float(10000 + i * 2000),
            "your_ask_price": float(11750 + i * 2350),
            "markup_pct":     17.5,
            "currency":       "USD",
            "location":       "Germany",
            "listing_url":    f"https://machinio.com/listing/{i}",
            "category":       "VMC",
            "lead_score":     7 + (i % 3),
        }
        for i in range(1, n + 1)
    ]


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Message Formatting
# ══════════════════════════════════════════════════════════════════════════════

class TestMessageFormatting(unittest.TestCase):

    def setUp(self):
        self.leads = make_test_leads(5)

    def test_message_is_string(self):
        """Output should be a string"""
        msg = format_whatsapp_message("Rajesh", self.leads)
        self.assertIsInstance(msg, str)

    def test_message_not_empty(self):
        """Message should not be empty"""
        msg = format_whatsapp_message("Rajesh", self.leads)
        self.assertGreater(len(msg), 50)

    def test_buyer_name_in_message(self):
        """Buyer name should appear in message"""
        msg = format_whatsapp_message("Rajesh", self.leads)
        self.assertIn("Rajesh", msg)

    def test_max_leads_respected(self):
        """Only max_leads items should appear"""
        msg = format_whatsapp_message("Rajesh", self.leads, max_leads=3)
        self.assertIn("Mazak VMC-1", msg)
        self.assertIn("Mazak VMC-2", msg)
        self.assertIn("Mazak VMC-3", msg)
        self.assertNotIn("Mazak VMC-4", msg)

    def test_message_under_4096_chars(self):
        """WhatsApp limit is 4096 characters"""
        msg = format_whatsapp_message("Rajesh", self.leads, max_leads=5)
        self.assertLessEqual(len(msg), 4096)

    def test_bold_formatting_present(self):
        """WhatsApp bold (*text*) should be used"""
        msg = format_whatsapp_message("Rajesh", self.leads)
        self.assertIn("*", msg)

    def test_price_in_message(self):
        """Price should appear in message"""
        msg = format_whatsapp_message("Rajesh", self.leads)
        self.assertIn("$", msg)

    def test_commands_footer_present(self):
        """Reply commands should be in message"""
        msg = format_whatsapp_message("Rajesh", self.leads)
        self.assertIn("YES",  msg)
        self.assertIn("CALL", msg)
        self.assertIn("STOP", msg)

    def test_empty_leads_no_crash(self):
        """Empty leads list should not crash"""
        try:
            msg = format_whatsapp_message("Rajesh", [], max_leads=5)
            self.assertIsInstance(msg, str)
        except Exception as e:
            self.fail(f"Empty leads crashed formatter: {e}")

    def test_star_rating_max_5(self):
        """Star rating should be max 5 stars"""
        leads = [{"lead_score": 10, **self.leads[0]}]
        msg   = format_whatsapp_message("Test", leads, max_leads=1)
        # Should have exactly 5 stars, not 10
        self.assertIn("⭐⭐⭐⭐⭐", msg)
        self.assertNotIn("⭐⭐⭐⭐⭐⭐", msg)

    def test_url_truncated(self):
        """URLs longer than 60 chars should be truncated"""
        leads = [{
            **self.leads[0],
            "listing_url": "https://www.machinio.com/" + "a" * 100
        }]
        msg = format_whatsapp_message("Test", leads, max_leads=1)
        # Full 100-char URL should not appear
        self.assertNotIn("a" * 100, msg)


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — WhatsApp Sending (Mocked)
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppSending(unittest.TestCase):

    def setUp(self):
        self.leads    = make_test_leads(3)
        self.leads_df = pd.DataFrame(self.leads)

    def _make_mock_client(self):
        """Create a mock Twilio client"""
        client             = MagicMock()
        mock_msg           = MagicMock()
        mock_msg.sid       = "SM1234567890abcdef"
        client.messages.create.return_value = mock_msg
        return client

    @patch.dict(os.environ, {
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"
    })
    def test_send_whatsapp_calls_twilio(self):
        """send_whatsapp should call Twilio messages.create"""
        client = self._make_mock_client()

        result = send_whatsapp("+919876543210", "Test message", client)

        client.messages.create.assert_called_once()
        self.assertTrue(result)

    @patch.dict(os.environ, {
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"
    })
    def test_send_whatsapp_correct_number_format(self):
        """Phone number should be prefixed with whatsapp:"""
        client = self._make_mock_client()

        send_whatsapp("+919876543210", "Test message", client)

        call_kwargs = client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["to"], "whatsapp:+919876543210")

    @patch.dict(os.environ, {
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"
    })
    def test_send_whatsapp_returns_false_on_error(self):
        """Should return False on Twilio error"""
        client = MagicMock()
        client.messages.create.side_effect = Exception("Twilio error")

        result = send_whatsapp("+919876543210", "Test", client)
        self.assertFalse(result)

    @patch.dict(os.environ, {
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"
    })
    def test_broadcast_sends_to_all_buyers(self):
        """broadcast_whatsapp should send to every buyer"""
        client = self._make_mock_client()

        buyers = [
            {"name": "Buyer 1", "phone": "+911111111111"},
            {"name": "Buyer 2", "phone": "+912222222222"},
            {"name": "Buyer 3", "phone": "+913333333333"},
        ]

        with patch("module3_whatsapp.get_twilio_client", return_value=client):
            broadcast_whatsapp(buyers, self.leads_df, max_leads_per_msg=3)

        self.assertEqual(client.messages.create.call_count, 3)

    @patch.dict(os.environ, {
        "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886"
    })
    def test_broadcast_tracks_failures(self, ):
        """Failed sends should be counted not crash broadcast"""
        client = MagicMock()
        # First succeeds, second fails, third succeeds
        client.messages.create.side_effect = [
            MagicMock(sid="SM111"),
            Exception("Twilio error"),
            MagicMock(sid="SM333"),
        ]

        buyers = [
            {"name": "Buyer 1", "phone": "+911111111111"},
            {"name": "Buyer 2", "phone": "+912222222222"},
            {"name": "Buyer 3", "phone": "+913333333333"},
        ]

        try:
            with patch("module3_whatsapp.get_twilio_client",
                       return_value=client):
                broadcast_whatsapp(buyers, self.leads_df)
        except Exception as e:
            self.fail(f"Broadcast crashed on partial failure: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — Live WhatsApp Test (sends real message to yourself)
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveWhatsApp(unittest.TestCase):

    @unittest.skipIf(
        not os.getenv("TWILIO_SID"),
        "TWILIO_SID not set in .env — skipping live WhatsApp test"
    )
    def test_send_real_whatsapp_to_self(self):
        """Send a real test WhatsApp to your own number"""
        your_number = os.getenv("TEST_PHONE_NUMBER", "")
        if not your_number:
            self.skipTest("TEST_PHONE_NUMBER not set in .env")

        leads   = make_test_leads(2)
        message = format_whatsapp_message(
            "TEST USER",
            leads,
            max_leads=2
        )
        message = "🧪 TEST MESSAGE\n\n" + message

        try:
            result = send_whatsapp(your_number, message)
            self.assertTrue(result)
            print("\n    ✅ Real WhatsApp sent — check your phone!")
        except Exception as e:
            self.fail(f"Live WhatsApp failed: {e}")


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  🧪 MODULE 3 TESTS — WhatsApp Engine")
    print("="*60 + "\n")
    unittest.main(verbosity=2, exit=False)
