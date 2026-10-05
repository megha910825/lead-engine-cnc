"""
Module 1: Data Sourcing + Parsing Engine
─────────────────────────────────────────
Pulls CNC/VMC listings from public sources,
filters by category, and applies your markup.
"""

import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import time
import re
import sqlite3
import os

# ── Lead Data Model ────────────────────────────────────────────────────────────

@dataclass
class MachineLead:
    source:          str
    title:           str
    brand:           str
    model:           str
    year:            str
    original_price:  float          # what seller is asking
    your_ask_price:  float = 0.0    # your price to buyer (with markup)
    markup_pct:      float = 17.5   # default 17.5% — adjust per deal
    currency:        str  = "USD"
    location:        str  = ""
    seller_contact:  str  = ""
    listing_url:     str  = ""
    category:        str  = ""      # VMC / CNC Lathe / EDM / etc.
    condition:       str  = ""      # Used / Refurbished / Unknown
    fetched_at:      str  = field(default_factory=lambda: datetime.now().isoformat())
    lead_score:      int  = 0       # 1–10, computed automatically

    def __post_init__(self):
        # Auto-calculate your ask price
        if self.original_price > 0 and self.your_ask_price == 0:
            self.your_ask_price = round(
                self.original_price * (1 + self.markup_pct / 100), 2
            )
        # Auto-score the lead
        self.lead_score = self._score()

    def _score(self) -> int:
        """
        Score 1–10 based on:
        - Known brand (+3)
        - Has price (+2)
        - Has year (+1)
        - Has seller contact (+2)
        - Recent year (+2)
        """
        score = 0
        top_brands = ["fanuc", "mazak", "haas", "dmg", "okuma",
                      "doosan", "makino", "hurco", "brother"]
        if any(b in self.brand.lower() for b in top_brands):
            score += 3
        if self.original_price > 0:
            score += 2
        if self.year and self.year.isdigit():
            score += 1
            if int(self.year) >= 2018:
                score += 2
        if self.seller_contact:
            score += 2
        return min(score, 10)

    @property
    def margin_usd(self) -> float:
        return round(self.your_ask_price - self.original_price, 2)

    def to_dict(self) -> dict:
        return {
            "source":         self.source,
            "title":          self.title,
            "brand":          self.brand,
            "model":          self.model,
            "year":           self.year,
            "original_price": self.original_price,
            "your_ask_price": self.your_ask_price,
            "markup_pct":     self.markup_pct,
            "margin_usd":     self.margin_usd,
            "currency":       self.currency,
            "location":       self.location,
            "seller_contact": self.seller_contact,
            "listing_url":    self.listing_url,
            "category":       self.category,
            "condition":      self.condition,
            "fetched_at":     self.fetched_at,
            "lead_score":     self.lead_score,
        }


# ── Price Parser ───────────────────────────────────────────────────────────────

def parse_price(raw: str) -> float:
    """Extract numeric price from messy strings like '$12,500', '₹8.5L', 'USD 45000'."""
    if not raw or raw in ("N/A", "POA", "Call", ""):
        return 0.0
    raw = raw.replace(",", "").replace(" ", "")
    # Handle Indian lakh notation: 8.5L → 850000
    lakh = re.search(r"([\d.]+)[Ll]", raw)
    if lakh:
        return float(lakh.group(1)) * 100_000
    # Extract plain number
    nums = re.findall(r"[\d.]+", raw)
    return float(nums[0]) if nums else 0.0


# ── Category Detector ──────────────────────────────────────────────────────────

CATEGORY_MAP = {
    "VMC":         ["vmc", "vertical machining", "vertical milling"],
    "HMC":         ["hmc", "horizontal machining"],
    "CNC Lathe":   ["lathe", "turning center", "turn-mill"],
    "EDM":         ["edm", "wire cut", "spark erosion", "die sinking"],
    "Grinding":    ["grinder", "grinding", "surface grind"],
    "Press":       ["press brake", "punching", "stamping"],
    "Laser":       ["laser cut", "fiber laser"],
    "Plasma":      ["plasma cut"],
    "Welding":     ["welding robot", "mig", "tig"],
}

def detect_category(title: str) -> str:
    t = title.lower()
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in t for kw in keywords):
            return cat
    return "CNC Other"


# ── Machinio Fetcher ───────────────────────────────────────────────────────────

def fetch_machinio(query: str = "CNC VMC machining center",
                   max_pages: int = 5,
                   markup: float = 17.5) -> list[MachineLead]:

    leads = []
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}

    for page in range(1, max_pages + 1):
        print(f"  [Machinio] Page {page} | '{query}'", end=" → ")
        try:
            resp = requests.get(
                "https://www.machinio.com/search",
                params={"q": query, "page": page},
                headers=HEADERS, timeout=15
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Error: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select(
            "div[class*='listing'], article[class*='listing'], "
            "div[class*='machine-card'], div[class*='search-result']"
        )
        print(f"{len(cards)} cards")

        for card in cards:
            title_el   = card.select_one("h2, h3, [class*='title']")
            price_el   = card.select_one("[class*='price']")
            loc_el     = card.select_one("[class*='location'], [class*='country']")
            year_el    = card.select_one("[class*='year']")
            link_el    = card.select_one("a[href]")

            raw_title  = title_el.get_text(strip=True) if title_el else ""
            raw_price  = price_el.get_text(strip=True) if price_el else ""
            raw_year   = year_el.get_text(strip=True)  if year_el  else ""

            # Try to extract brand from title (first word usually)
            brand = raw_title.split()[0] if raw_title else "Unknown"

            href = link_el["href"] if link_el else ""
            url  = ("https://www.machinio.com" + href
                    if href.startswith("/") else href)

            price = parse_price(raw_price)
            lead = MachineLead(
                source         = "Machinio",
                title          = raw_title,
                brand          = brand,
                model          = raw_title,
                year           = raw_year,
                original_price = price,
                markup_pct     = markup,
                location       = loc_el.get_text(strip=True) if loc_el else "",
                listing_url    = url,
                category       = detect_category(raw_title),
            )
            leads.append(lead)

        time.sleep(2)

    return leads


# ── Exapro Fetcher ─────────────────────────────────────────────────────────────

def fetch_exapro(max_pages: int = 5, markup: float = 17.5) -> list[MachineLead]:
    leads = []
    HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/124.0"}
    categories = [
        "/cat/machining-centers-cnc",
        "/cat/cnc-lathes",
        "/cat/edm-machines",
    ]

    for cat in categories:
        for page in range(1, max_pages + 1):
            url = f"https://www.exapro.com{cat}" + (f"?page={page}" if page > 1 else "")
            print(f"  [Exapro] {cat} page {page}", end=" → ")

            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"Error: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select(".machine-item, [class*='product-card'], [class*='listing-item']")
            print(f"{len(cards)} cards")
            if not cards:
                break

            for card in cards:
                title_el = card.select_one("h2, h3, [class*='title']")
                price_el = card.select_one("[class*='price']")
                year_el  = card.select_one("[class*='year']")
                brand_el = card.select_one("[class*='brand'], [class*='maker']")
                link_el  = card.select_one("a[href]")

                raw_title = title_el.get_text(strip=True) if title_el else ""
                href      = link_el["href"] if link_el else ""
                price     = parse_price(price_el.get_text(strip=True) if price_el else "")

                lead = MachineLead(
                    source         = "Exapro",
                    title          = raw_title,
                    brand          = brand_el.get_text(strip=True) if brand_el else raw_title.split()[0],
                    model          = raw_title,
                    year           = year_el.get_text(strip=True) if year_el else "",
                    original_price = price,
                    markup_pct     = markup,
                    listing_url    = "https://www.exapro.com" + href if href.startswith("/") else href,
                    category       = detect_category(raw_title),
                )
                leads.append(lead)

            time.sleep(2)

    return leads

"""
Surplex: Public auction listings for used industrial machines.
No login required to browse. Based in Germany/Europe.
"""

def fetch_surplex(max_pages: int = 5,
                  markup: float = 17.5) -> list[MachineLead]:

    leads   = []
    HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/124.0",
               "Accept-Language": "en-US,en;q=0.9"}

    # Surplex category URLs for CNC machines
    categories = {
        "VMC":       "https://www.surplex.com/en/machines/c/machining-centers.html",
        "CNC Lathe": "https://www.surplex.com/en/machines/c/lathes.html",
        "Grinding":  "https://www.surplex.com/en/machines/c/grinding-machines.html",
        "EDM":       "https://www.surplex.com/en/machines/c/edm-machines.html",
    }

    for category, base_url in categories.items():
        for page in range(1, max_pages + 1):
            url = f"{base_url}?page={page}" if page > 1 else base_url
            print(f"  [Surplex] {category} | Page {page}", end=" → ")

            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"Error: {e}")
                break

            soup  = BeautifulSoup(resp.text, "lxml")

            # Surplex listing cards
            cards = soup.select(
                ".machine-item, .auction-item, "
                "[class*='machine-list-item'], [class*='lot-item']"
            )
            print(f"{len(cards)} cards")
            if not cards:
                break

            for card in cards:
                title_el  = card.select_one("h2, h3, [class*='title'], [class*='name']")
                price_el  = card.select_one("[class*='price'], [class*='bid']")
                year_el   = card.select_one("[class*='year'], [class*='built']")
                loc_el    = card.select_one("[class*='location'], [class*='country']")
                link_el   = card.select_one("a[href]")

                raw_title = title_el.get_text(strip=True) if title_el else ""
                href      = link_el["href"] if link_el else ""
                full_url  = ("https://www.surplex.com" + href
                             if href.startswith("/") else href)

                lead = MachineLead(
                    source         = "Surplex",
                    title          = raw_title,
                    brand          = raw_title.split()[0] if raw_title else "Unknown",
                    model          = raw_title,
                    year           = year_el.get_text(strip=True) if year_el else "",
                    original_price = parse_price(price_el.get_text(strip=True)
                                                 if price_el else ""),
                    markup_pct     = markup,
                    location       = loc_el.get_text(strip=True) if loc_el else "Europe",
                    listing_url    = full_url,
                    category       = category,
                    condition      = "Auction",
                )
                leads.append(lead)

            time.sleep(2)

    print(f"  ✅ Surplex: {len(leads)} leads fetched")
    return leads

"""
eBay Finding API — completely free, official, no ToS issues.
Register at: https://developer.ebay.com  (free sandbox + production keys)
"""

def fetch_ebay_cnc(app_id: str,
                   keywords: str = "CNC machining center VMC used",
                   max_results: int = 100,
                   markup: float = 17.5) -> list[MachineLead]:
    """
    Uses eBay's official Finding API.
    app_id: Get free at developer.ebay.com → My Keys
    """
    leads = []
    url   = "https://svcs.ebay.com/services/search/FindingService/v1"

    params = {
        "OPERATION-NAME":          "findItemsByKeywords",
        "SERVICE-VERSION":         "1.0.0",
        "SECURITY-APPNAME":        app_id,          # Your free eBay App ID
        "RESPONSE-DATA-FORMAT":    "JSON",
        "keywords":                keywords,
        "categoryId":              "12584",          # eBay: Metalworking Equipment
        "paginationInput.entriesPerPage": "100",
        "paginationInput.pageNumber":     "1",
        "itemFilter(0).name":      "Condition",
        "itemFilter(0).value":     "Used",
        "itemFilter(1).name":      "ListingType",
        "itemFilter(1).value(0)":  "FixedPrice",
        "itemFilter(1).value(1)":  "Auction",
        "sortOrder":               "PricePlusShippingLowest",
    }

    print(f"  [eBay API] Searching: '{keywords}'", end=" → ")

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"Error: {e}")
        return []

    # Navigate eBay's nested JSON response
    try:
        items = (data
                 ["findItemsByKeywordsResponse"][0]
                 ["searchResult"][0]
                 ["item"])
    except (KeyError, IndexError):
        print("No items in response")
        return []

    print(f"{len(items)} items")

    for item in items:
        title     = item.get("title",         [""])[0]
        price_raw = (item.get("sellingStatus",  [{}])[0]
                         .get("currentPrice",   [{}])[0]
                         .get("__value__",      "0"))
        currency  = (item.get("sellingStatus",  [{}])[0]
                         .get("currentPrice",   [{}])[0]
                         .get("@currencyId",    "USD"))
        location  =  item.get("location",       [""])[0]
        url_link  = (item.get("viewItemURL",    [""])[0])
        condition = (item.get("condition",      [{}])[0]
                         .get("conditionDisplayName", ["Used"])[0])

        lead = MachineLead(
            source         = "eBay",
            title          = title,
            brand          = title.split()[0] if title else "Unknown",
            model          = title,
            year           = "",                    # eBay rarely has year in API
            original_price = float(price_raw or 0),
            markup_pct     = markup,
            currency       = currency,
            location       = location,
            listing_url    = url_link,
            category       = detect_category(title),
            condition      = condition,
        )
        leads.append(lead)

    print(f"  ✅ eBay: {len(leads)} leads fetched")
    return leads

"""
Used-machines.net — European industrial marketplace.
Fully public listings. No login required.
"""

def fetch_used_machines_net(max_pages: int = 5,
                             markup: float = 17.5) -> list[MachineLead]:

    leads   = []
    HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/124.0",
               "Accept-Language": "en-US,en;q=0.9"}

    search_queries = [
        "machining-center-cnc",
        "cnc-lathe",
        "edm-machine",
        "surface-grinding-machine",
    ]

    for query in search_queries:
        for page in range(1, max_pages + 1):
            url = (f"https://www.used-machines.net/en/search/"
                   f"{query}/page/{page}/")
            print(f"  [used-machines.net] {query} | page {page}", end=" → ")

            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"Error: {e}")
                break

            soup  = BeautifulSoup(resp.text, "lxml")
            cards = soup.select(
                ".machine, .listing, "
                "[class*='machine-item'], [class*='search-item']"
            )
            print(f"{len(cards)} cards")
            if not cards:
                break

            for card in cards:
                title_el = card.select_one("h2, h3, [class*='title']")
                price_el = card.select_one("[class*='price']")
                year_el  = card.select_one("[class*='year'], [class*='built']")
                loc_el   = card.select_one("[class*='location'], [class*='country']")
                link_el  = card.select_one("a[href]")

                raw_title = title_el.get_text(strip=True) if title_el else ""
                href      = link_el["href"] if link_el else ""
                full_url  = ("https://www.used-machines.net" + href
                             if href.startswith("/") else href)

                lead = MachineLead(
                    source         = "used-machines.net",
                    title          = raw_title,
                    brand          = raw_title.split()[0] if raw_title else "Unknown",
                    model          = raw_title,
                    year           = year_el.get_text(strip=True) if year_el else "",
                    original_price = parse_price(
                                         price_el.get_text(strip=True)
                                         if price_el else ""
                                     ),
                    markup_pct     = markup,
                    location       = loc_el.get_text(strip=True) if loc_el else "Europe",
                    listing_url    = full_url,
                    category       = detect_category(raw_title),
                )
                leads.append(lead)

            time.sleep(2)

    print(f"  ✅ used-machines.net: {len(leads)} leads fetched")
    return leads

def fetch_all_sources(markup: float = 17.5,
                      ebay_app_id: str = "") -> list[MachineLead]:
    """
    Unified fetcher — pulls from ALL available sources.
    Add your eBay App ID from developer.ebay.com (free).
    """
    all_leads = []
    results   = {}

    # ── Tier 1: Public HTML (no auth needed) ──────────────────────────────────
    print("\n📡 TIER 1 — Public Listings\n")

    r = fetch_machinio("VMC machining center used", max_pages=5, markup=markup)
    results["Machinio-VMC"] = len(r); all_leads += r

    r = fetch_machinio("CNC lathe turning used", max_pages=3, markup=markup)
    results["Machinio-Lathe"] = len(r); all_leads += r

    r = fetch_exapro(max_pages=4, markup=markup)
    results["Exapro"] = len(r); all_leads += r

    r = fetch_surplex(max_pages=3, markup=markup)
    results["Surplex"] = len(r); all_leads += r

    r = fetch_used_machines_net(max_pages=3, markup=markup)
    results["used-machines.net"] = len(r); all_leads += r

    # ── Tier 2: Official APIs (free keys needed) ───────────────────────────────
    print("\n📡 TIER 2 — Official APIs\n")

    if ebay_app_id:
        r = fetch_ebay_cnc(ebay_app_id, markup=markup)
        results["eBay"] = len(r); all_leads += r
    else:
        print("  [eBay] Skipped — add your free App ID from developer.ebay.com")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "="*50)
    print("  📊 FETCH SUMMARY")
    print("="*50)
    for source, count in results.items():
        bar = "█" * min(count // 5, 30)
        print(f"  {source:<22} {bar} {count}")
    print(f"  {'TOTAL':<22} {len(all_leads)} raw leads")
    print("="*50 + "\n")

    return all_leads

# ── SQLite Persistence ─────────────────────────────────────────────────────────

def save_to_db(leads: list[MachineLead], db_path: str = "leads.db"):
    """Persist leads to SQLite — avoids duplicates across runs."""
     # ── Guard: nothing to save ─────────────────────────────────
    if not leads:
        print("  ⚠️  save_to_db() called with empty list — skipping")
        return
    # ───────────────────────────────────────────────────────────
    conn = sqlite3.connect(db_path)
    df = pd.DataFrame([l.to_dict() for l in leads])
    df.to_sql("leads", conn, if_exists="append", index=False)

    # Deduplicate on listing_url
    conn.execute("""
        DELETE FROM leads WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM leads GROUP BY listing_url
        )
    """)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    conn.close()
    print(f"  💾 DB: {len(leads)} new leads saved | {total} total unique leads")


def load_top_leads(db_path: str = "leads.db",
                   min_score: int = 5,
                   limit: int = 50) -> pd.DataFrame:
    """Load highest-scored leads from DB for broadcasting."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        f"""
        SELECT * FROM leads
        WHERE lead_score >= {min_score}
          AND original_price > 0
        ORDER BY lead_score DESC, fetched_at DESC
        LIMIT {limit}
        """,
        conn
    )
    conn.close()
    return df


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    MARKUP = 17.5  # % — adjust per deal type

    print("\n📡 Fetching CNC/VMC leads from public sources...\n")
    leads = []
    leads += fetch_machinio(query="VMC machining center used", max_pages=5, markup=MARKUP)
    leads += fetch_machinio(query="CNC lathe turning used",    max_pages=3, markup=MARKUP)
    leads += fetch_exapro(max_pages=4, markup=MARKUP)

    print(f"\n✅ Total raw leads: {len(leads)}")
    save_to_db(leads)

    top = load_top_leads(min_score=5, limit=50)
    print(f"\n🏆 Top {len(top)} leads ready for broadcast:\n")
    print(top[["brand","model","year","original_price",
               "your_ask_price","margin_usd","lead_score","location"]].to_string(index=False))
