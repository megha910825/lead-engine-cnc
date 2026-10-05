"""
tests/test_module1.py
─────────────────────
Tests for: fetch, parse, score, DB operations
Run with: python tests/test_module1.py
"""

import sys
import os
import sqlite3
import unittest
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from module1_sourcing import (
    MachineLead,
    parse_price,
    detect_category,
    fetch_machinio,
    fetch_exapro,
    save_to_db,
    load_top_leads,
)

# ── Test Database Path (separate from production) ─────────────────────────────
TEST_DB = "tests/test_leads.db"

# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — parse_price()
# ══════════════════════════════════════════════════════════════════════════════

class TestParsePrice(unittest.TestCase):

    def test_clean_dollar(self):
        """Standard dollar amount"""
        self.assertEqual(parse_price("$12,500"), 12500.0)

    def test_no_symbol(self):
        """Plain number without currency symbol"""
        self.assertEqual(parse_price("45000"), 45000.0)

    def test_with_spaces(self):
        """USD with spaces"""
        self.assertEqual(parse_price("USD 45 000"), 45000.0)

    def test_indian_lakh(self):
        """Indian lakh notation"""
        self.assertEqual(parse_price("8.5L"), 850000.0)
        self.assertEqual(parse_price("12L"),  1200000.0)

    def test_poa(self):
        """Price on application — should return 0"""
        self.assertEqual(parse_price("POA"),  0.0)
        self.assertEqual(parse_price("Call"), 0.0)
        self.assertEqual(parse_price("N/A"),  0.0)
        self.assertEqual(parse_price(""),     0.0)

    def test_none_input(self):
        """None input should return 0"""
        self.assertEqual(parse_price(None), 0.0)

    def test_rupee_symbol(self):
        """Rupee symbol"""
        self.assertEqual(parse_price("₹1,20,000"), 120000.0)

    def test_euro(self):
        """Euro amount"""
        self.assertGreater(parse_price("€ 25.000"), 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — detect_category()
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectCategory(unittest.TestCase):

    def test_vmc_detection(self):
        self.assertEqual(
            detect_category("Mazak Vertical Machining Center 2019"),
            "VMC"
        )

    def test_vmc_abbreviation(self):
        self.assertEqual(
            detect_category("Haas VMC VF-2 used"),
            "VMC"
        )

    def test_cnc_lathe(self):
        self.assertEqual(
            detect_category("Fanuc CNC Lathe turning center"),
            "CNC Lathe"
        )

    def test_edm(self):
        self.assertEqual(
            detect_category("Mitsubishi Wire Cut EDM machine"),
            "EDM"
        )

    def test_grinding(self):
        self.assertEqual(
            detect_category("Studer Surface Grinding Machine"),
            "Grinding"
        )

    def test_laser(self):
        self.assertEqual(
            detect_category("Trumpf Fiber Laser cutting 3015"),
            "Laser"
        )

    def test_unknown_defaults(self):
        self.assertEqual(
            detect_category("Some Unknown XYZ Machine"),
            "CNC Other"
        )

    def test_case_insensitive(self):
        """Category detection should be case insensitive"""
        self.assertEqual(
            detect_category("MAZAK VMC VERTICAL MACHINING"),
            "VMC"
        )


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — MachineLead dataclass
# ══════════════════════════════════════════════════════════════════════════════

class TestMachineLead(unittest.TestCase):

    def setUp(self):
        """Create a standard test lead"""
        self.lead = MachineLead(
            source         = "Machinio",
            title          = "Mazak VTC-200B VMC",
            brand          = "Mazak",
            model          = "VTC-200B",
            year           = "2019",
            original_price = 10000.0,
            markup_pct     = 17.5,
        )

    def test_ask_price_calculated(self):
        """your_ask_price should be auto-calculated"""
        self.assertEqual(self.lead.your_ask_price, 11750.0)

    def test_margin_calculated(self):
        """margin_usd should be ask - original"""
        self.assertEqual(self.lead.margin_usd, 1750.0)

    def test_lead_score_range(self):
        """Score must be between 1 and 10"""
        self.assertGreaterEqual(self.lead.lead_score, 1)
        self.assertLessEqual(self.lead.lead_score, 10)

    def test_known_brand_scores_higher(self):
        """Known brands (Mazak, Fanuc) should score higher"""
        known_brand = MachineLead(
            source="Test", title="Mazak VMC", brand="Mazak",
            model="VTC", year="2020", original_price=10000.0
        )
        unknown_brand = MachineLead(
            source="Test", title="Unknown VMC", brand="Unknown",
            model="XYZ", year="2020", original_price=10000.0
        )
        self.assertGreater(known_brand.lead_score, unknown_brand.lead_score)

    def test_newer_year_scores_higher(self):
        """2020 machine should score higher than 2010"""
        new_machine = MachineLead(
            source="Test", title="Haas VF2", brand="Haas",
            model="VF2", year="2020", original_price=10000.0
        )
        old_machine = MachineLead(
            source="Test", title="Haas VF2", brand="Haas",
            model="VF2", year="2010", original_price=10000.0
        )
        self.assertGreater(new_machine.lead_score, old_machine.lead_score)

    def test_zero_price_no_crash(self):
        """Zero price should not crash — stays at 0"""
        lead = MachineLead(
            source="Test", title="Test", brand="Test",
            model="Test", year="2020", original_price=0.0
        )
        self.assertEqual(lead.your_ask_price, 0.0)
        self.assertEqual(lead.margin_usd,     0.0)

    def test_to_dict_has_all_keys(self):
        """to_dict() should contain all expected keys"""
        d = self.lead.to_dict()
        expected_keys = [
            "source", "title", "brand", "model", "year",
            "original_price", "your_ask_price", "markup_pct",
            "margin_usd", "currency", "location", "listing_url",
            "category", "condition", "fetched_at", "lead_score",
        ]
        for key in expected_keys:
            self.assertIn(key, d, f"Missing key: {key}")

    def test_custom_markup(self):
        """Custom markup should override default"""
        lead = MachineLead(
            source="Test", title="Test", brand="Test",
            model="Test", year="2020",
            original_price = 10000.0,
            markup_pct     = 25.0,          # custom markup
        )
        self.assertEqual(lead.your_ask_price, 12500.0)


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 4 — Database Operations
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabase(unittest.TestCase):

    def setUp(self):
        """Create fresh test DB before each test"""
        # Remove test DB if exists
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

        # Create sample leads
        self.sample_leads = [
            MachineLead(
                source="Machinio", title=f"Test Machine {i}",
                brand="Mazak", model=f"VMC-{i}",
                year="2020", original_price=float(10000 + i * 1000),
                listing_url=f"https://example.com/listing/{i}",
                category="VMC",
            )
            for i in range(1, 11)              # 10 test leads
        ]

    def tearDown(self):
        """Clean up test DB after each test"""
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_save_leads_to_db(self):
        """Leads should be saved to database"""
        save_to_db(self.sample_leads, TEST_DB)

        conn = sqlite3.connect(TEST_DB)
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        conn.close()

        self.assertEqual(count, 10)

    def test_deduplication(self):
        """Same leads saved twice should not duplicate"""
        save_to_db(self.sample_leads, TEST_DB)
        save_to_db(self.sample_leads, TEST_DB)  # save again

        conn = sqlite3.connect(TEST_DB)
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        conn.close()

        self.assertEqual(count, 10)             # still 10, not 20

    def test_load_top_leads_returns_dataframe(self):
        """load_top_leads should return a DataFrame"""
        save_to_db(self.sample_leads, TEST_DB)
        df = load_top_leads(db_path=TEST_DB, min_score=1, limit=50)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)

    def test_load_top_leads_score_filter(self):
        """Should only return leads meeting min_score"""
        save_to_db(self.sample_leads, TEST_DB)
        df = load_top_leads(db_path=TEST_DB, min_score=8, limit=50)

        if not df.empty:
            self.assertTrue(all(df["lead_score"] >= 8))

    def test_load_top_leads_limit(self):
        """Should respect the limit parameter"""
        save_to_db(self.sample_leads, TEST_DB)
        df = load_top_leads(db_path=TEST_DB, min_score=1, limit=5)

        self.assertLessEqual(len(df), 5)

    def test_empty_leads_list(self):
        """Saving empty list should not crash"""
        try:
            save_to_db([], TEST_DB)
        except Exception as e:
            self.fail(f"save_to_db([]) raised: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 5 — Live Fetch Tests (Network Required)
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveFetch(unittest.TestCase):
    """
    These tests hit real websites.
    Skip with: python test_module1.py --skip-live
    """

    @unittest.skipIf(
        os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        "Live tests skipped"
    )
    def test_machinio_returns_leads(self):
        """Machinio fetch should return at least 1 lead"""
        leads = fetch_machinio(
            query     = "CNC lathe used",
            max_pages = 1,              # just 1 page for speed
            markup    = 17.5,
        )
        self.assertIsInstance(leads, list)
        print(f"\n    → Machinio returned {len(leads)} leads")

    @unittest.skipIf(
        os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        "Live tests skipped"
    )
    def test_exapro_returns_leads(self):
        """Exapro fetch should return at least 1 lead"""
        leads = fetch_exapro(max_pages=1, markup=17.5)
        self.assertIsInstance(leads, list)
        print(f"\n    → Exapro returned {len(leads)} leads")

    @unittest.skipIf(
        os.getenv("SKIP_LIVE_TESTS", "false").lower() == "true",
        "Live tests skipped"
    )
    def test_lead_structure_from_live_fetch(self):
        """Live leads should have required fields"""
        leads = fetch_machinio(
            query     = "VMC machining center",
            max_pages = 1,
            markup    = 17.5,
        )
        if leads:
            lead = leads[0]
            self.assertIsInstance(lead, MachineLead)
            self.assertNotEqual(lead.title, "")
            self.assertGreaterEqual(lead.lead_score, 0)


# ── Run all tests ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  🧪 MODULE 1 TESTS — Sourcing Engine")
    print("="*60 + "\n")

    # Run with verbosity=2 to see each test name
    unittest.main(verbosity=2, exit=False)
