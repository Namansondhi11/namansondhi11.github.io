#!/usr/bin/env python3
"""
update_prices.py — nightly portfolio refresher for namansondhi's site.

What it does
------------
1. Fetches latest closes for US + Indian stocks (Yahoo Finance via yfinance)
   and latest NAVs for Indian mutual funds (mfapi.in, free AMFI mirror).
2. Recomputes each holding's P&L % ( = price/avg - 1 ) and weight %
   ( = current value / book total ), plus each book's overall P&L.
3. Rewrites the JSON data block inside index.html between the
   <!--PF_DATA_START--> ... <!--PF_DATA_END--> markers.

Only percentages are ever written to the page — no absolute amounts.

Usage
-----
  python update_prices.py                 # live fetch, updates ./index.html
  python update_prices.py --offline       # uses baked screenshot prices (testing)
  python update_prices.py --file path.html

Edit YOUR THESES and holdings in CONFIG below. This file is the single
source of truth — the HTML is regenerated from it every night.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

# ============================================================
# CONFIG — holdings, cost basis, and investment theses.
# qty/avg define the cost basis; th is the thesis shown on hover.
# Edit th strings freely; they are re-injected every run.
# ============================================================

CONFIG = {
    "instk": {
        "name": "India · Stocks",
        "kind": "yf",  # Yahoo Finance, NSE
        "holdings": [
            {"t": "UJJIVANSFB", "yf": "UJJIVANSFB.NS", "qty": 14000, "avg": 32.33,
             "th": "Fundamental: a small-finance bank compounding low-cost deposits in underbanked India, with microfinance stress fading and a universal-bank licence in play. Technical: accumulated through the long post-listing base; the multi-year breakout confirmed the re-rating, so I let the winner run."},
            {"t": "CONFIPET", "yf": "CONFIPET.NS", "qty": 7500, "avg": 52.65,
             "th": "Fundamental: LPG cylinders, bottling plants and auto-LPG — picks and shovels for India's clean-cooking transition, with capacity added ahead of demand. Technical: entered during the consolidation after the first markup leg; higher lows ever since keep the position on."},
            {"t": "SPIC", "yf": "SPIC.NS", "qty": 7000, "avg": 73.18,
             "th": "Fundamental: a fertilizer turnaround with policy-backed demand, a deleveraged balance sheet and land-bank optionality the market ignores. Technical: a classic deep-value coil — long sideways base on shrinking volume. I'm paid in patience until the range breaks."},
            {"t": "NATCOPHARM", "yf": "NATCOPHARM.NS", "qty": 500, "avg": 802.24,
             "th": "Fundamental: specialty generics with lumpy but lucrative Para-IV launches, net cash, and a pipeline the street forgets between events. Technical: bought the post-earnings drawdown near long-term support — an asymmetric setup where one approval re-prices the stock."},
            {"t": "OIL", "yf": "OIL.NS", "qty": 900, "avg": 414.83,
             "th": "Fundamental: upstream PSU with low-cost reserves, a fat dividend and energy-security tailwinds from policy. Technical: rides its rising 200-day average — I add on pullbacks to it and collect the payout while crude makes up its mind."},
            {"t": "SYRMA", "yf": "SYRMA.NS", "qty": 250, "avg": 1320.00,
             "th": "Fundamental: electronics manufacturing riding Make-in-India outsourcing, with the order book mixing toward higher-margin industrial and auto work. Technical: the post-IPO base resolved upward; the position stays while the structure of higher lows survives."},
            {"t": "TATAPOWER", "yf": "TATAPOWER.NS", "qty": 350, "avg": 137.85,
             "th": "Fundamental: a legacy utility rebuilt into renewables, transmission and rooftop solar — a regulated-return core funding a growth story. Technical: bought in the double digits before the re-rating; a textbook stage-two trend since. The +172% is why you respect exits, not targets."},
            {"t": "ETHOSLTD", "yf": "ETHOSLTD.NS", "qty": 50, "avg": 2546.59,
             "th": "Fundamental: India's luxury-watch gatekeeper — exclusive brand tie-ups, boutique expansion, and the premiumizing affluent consumer. Technical: entered after the froth cooled off the highs; slightly underwater and unbothered while same-store growth compounds."},
            {"t": "SPARC", "yf": "SPARC.NS", "qty": 500, "avg": 233.30,
             "th": "Fundamental: pure-play drug R&D where a single clinical win re-rates the whole company — binary by design. Technical: entered near multi-year lows and sized like the lottery ticket it is. The volatility is the feature, not the bug."},
            {"t": "SOUTHBANK", "yf": "SOUTHBANK.NS", "qty": 1100, "avg": 46.88,
             "th": "Fundamental: an old private bank scrubbing its loan book and rebuilding CASA while trading below book value. Technical: a long accumulation range with improving delivery volumes — cheap enough that patience is the only edge required."},
            {"t": "ETERNAL", "yf": "ETERNAL.NS", "qty": 100, "avg": 247.02,
             "th": "Fundamental: food delivery plus Blinkit quick-commerce — the logistics layer of urban India with take-rates still maturing. Technical: entered on the correction after profitability flipped positive. Momentum names get bought on pullbacks, not chased."},
            {"t": "BAJAJHFL", "yf": "BAJAJHFL.NS", "qty": 214, "avg": 70.00,
             "th": "Fundamental: housing finance with Bajaj underwriting DNA at the start of a decade-long mortgage upcycle. Technical: an anchor position taken at the IPO price — letting institutional discovery play out before sizing up."},
            {"t": "TANLA", "yf": "TANLA.NS", "qty": 3, "avg": 524.86,
             "th": "Fundamental: CPaaS rails for India's messaging economy — every OTP and RCS push is a toll collected. Technical: a tracker position taken after the de-rating; watching for the base to complete before committing real size."},
        ],
    },
    "inmf": {
        "name": "India · Mutual funds",
        "kind": "mf",  # mfapi.in NAVs
        "holdings": [
            {"t": "Kotak Midcap Fund", "mf_q": "Kotak Midcap", "qty": 947.032, "avg": 147.82,
             "th": "The core midcap compounding engine, delegated to a manager with a long runway. Entered via staggered tranches rather than one timed entry — SIP discipline does the technical work here."},
            {"t": "Tata Small Cap Fund", "mf_q": "Tata Small Cap", "qty": 2384.835, "avg": 41.92,
             "th": "Small-cap beta without single-stock blowup risk — the fund takes the concentration, I take the category. Tranches go in during corrections; small caps get bought when the headlines are worst."},
            {"t": "HDFC Mid Cap Fund", "mf_q": "HDFC Mid Cap", "qty": 341.778, "avg": 204.80,
             "th": "A second midcap engine with a different manager style — diversifying process risk, not just holdings. Accumulated on drawdowns below the fund's one-year average NAV."},
            {"t": "Mirae Large & Midcap", "mf_q": "Mirae Asset Large", "qty": 428.142, "avg": 163.48,
             "th": "The ballast-with-upside sleeve: large-cap stability with a midcap kicker in one fund. Bought steadily and rebalanced whenever equity drifts past its target allocation."},
            {"t": "Kotak Bond Short Term", "mf_q": "Kotak Bond Short Term", "qty": 1243.583, "avg": 56.28,
             "th": "Short-duration debt — dry powder that still earns while waiting for equity fat pitches. Duration is kept short on purpose: this is the war chest, not a rate bet."},
            {"t": "HDFC Corporate Bond", "mf_q": "HDFC Corporate Bond", "qty": 2148.204, "avg": 32.58,
             "th": "High-grade corporate carry for the stability sleeve. AAA-heavy and boring by design — the portfolio's shock absorber for the days equities gap down."},
            {"t": "HDFC Small Cap Fund", "mf_q": "HDFC Small Cap", "qty": 463.968, "avg": 150.86,
             "th": "Value-tilted small caps to complement a growth-heavy stock book — a different factor inside the same category. Deployed in tranches through smallcap corrections."},
            {"t": "HSBC Corporate Bond", "mf_q": "HSBC Corporate Bond", "qty": 789.359, "avg": 76.00,
             "th": "More investment-grade carry, deliberately held at a second fund house to spread credit-desk risk. Yield, with a seatbelt."},
        ],
    },
    "us": {
        "name": "United States",
        "kind": "yf",
        "holdings": [
            {"t": "NVDA", "yf": "NVDA", "qty": 14.0, "avg": 120.2283,
             "th": "Fundamental: the tollbooth of the AI buildout — CUDA lock-in, datacenter demand outrunning supply, margins that make software jealous. Technical: core position from the $120s; I trim into parabolic stretches and rebuild on tests of the 100-day. Conviction hold."},
            {"t": "GOOGL", "yf": "GOOGL", "qty": 1.75, "avg": 167.8998,
             "th": "Fundamental: the search cash machine funding Gemini, Cloud, Waymo and TPUs — bought when the street said AI would kill it. Technical: entered in the $160s at peak pessimism; more than a double since. Buy quality when the narrative is broken, not the business."},
            {"t": "META", "yf": "META", "qty": 0.75, "avg": 503.1941,
             "th": "Fundamental: an attention monopoly with AI-sharpened ad targeting, brutal cost discipline, and optionality from Llama to glasses. Technical: bought after the reset year — it treats its 200-day like a floor and earns its keep every earnings cycle."},
            {"t": "AAPL", "yf": "AAPL", "qty": 1.274698, "avg": 206.1519,
             "th": "Fundamental: the ecosystem annuity — services margin layered over two billion devices and consumer tech's most loyal installed base. Technical: accumulated near long-term support around $200; the sleep-well compounder that funds the riskier sleeves."},
            {"t": "TWLO", "yf": "TWLO", "qty": 1.5, "avg": 145.1123,
             "th": "Fundamental: the communications API layer of the software economy, now pairing growth with real operating leverage after the activist reset. Technical: bought the multi-year drawdown near the lows — re-acceleration plus buybacks is the setup. A turnaround, priced like one."},
            {"t": "AVGO", "yf": "AVGO", "qty": 0.780469, "avg": 351.9676,
             "th": "Fundamental: custom AI silicon for hyperscalers plus VMware's sticky software cash flows — Hock Tan compounds capital like few operators alive. Technical: a recent entry on the post-earnings dip; starter size, scaling on confirmation."},
            {"t": "TSLA", "yf": "TSLA", "qty": 0.5, "avg": 371.5648,
             "th": "Fundamental: an option on autonomy, robotics and energy storage wrapped in a car company — the auto business pays for the free calls. Technical: a half-position by design; adds happen only at fear extremes. The volatility is both tuition and opportunity."},
            {"t": "JNJ", "yf": "JNJ", "qty": 0.7, "avg": 156.9170,
             "th": "Fundamental: healthcare's steadiest compounder — pharma innovation plus medtech behind a fortress balance sheet and a six-decade dividend streak. Technical: an old core holding in a slow uptrend. The +67% is what boring looks like, given enough years."},
            {"t": "O", "yf": "O", "qty": 2.593985, "avg": 56.2864,
             "th": "Fundamental: the monthly-dividend REIT — triple-net leases to investment-grade tenants; a bond proxy that raises its own coupon. Technical: accumulated while rate fears crushed REIT prices. Locking the yield at the lows was the whole trade."},
            {"t": "KO", "yf": "KO", "qty": 1.557523, "avg": 66.7619,
             "th": "Fundamental: the world's best distribution moat, with pricing power inflation only strengthens. Technical: a defensive anchor bought at a fair price — it rallies when growth wobbles, which is exactly its job in this book."},
            {"t": "V", "yf": "V", "qty": 0.350316, "avg": 280.7427,
             "th": "Fundamental: a toll on global commerce at 50%+ operating margins — the network compounds with every card issued. Technical: entered on a routine pullback to trend. The kind of chart you check quarterly, not daily."},
            {"t": "MCD", "yf": "MCD", "qty": 0.4, "avg": 274.2134,
             "th": "Fundamental: a real-estate and franchising empire that happens to sell burgers — royalty streams with recession resistance. Technical: bought at the value end of its historical multiple range. Low-drama ballast."},
            {"t": "MSFT", "yf": "MSFT", "qty": 0.25, "avg": 428.2158,
             "th": "Fundamental: enterprise AI distribution at unmatched scale — Copilot rides rails Office spent thirty years laying. Technical: underwater on an entry near the highs; the thesis is intact, so the red is a cost-averaging opportunity, not a mistake to flee."},
            {"t": "SNDK", "yf": "SNDK", "qty": 0.003885, "avg": 1724.4787,
             "th": "Fundamental: pure-play flash memory from the Western Digital split, geared to an AI-driven storage upcycle. Technical: a spin-off stub — kept because spin-offs are historically mispriced, sized small because memory is brutally cyclical."},
            {"t": "SPCX", "yf": None, "static_price": 162.00, "qty": 0.012099, "avg": 184.3213,
             "th": "Fundamental: pre-IPO SpaceX exposure — Starlink's cash engine funding Starship's option value. A moonshot, literally. Technical: none; private marks move on their own schedule. Sized so 'what if it halves?' answers itself: fine."},
        ],
    },
}

# Pin a fund to an exact mfapi.in scheme code if auto-matching ever
# picks the wrong plan: e.g. {"HDFC Mid Cap Fund": 118989}
SCHEME_OVERRIDES = {}

# Screenshot closes — used by --offline for testing without network.
BAKED = {
    "UJJIVANSFB.NS": 59.60, "CONFIPET.NS": 74.17, "SPIC.NS": 70.10,
    "NATCOPHARM.NS": 932.60, "OIL.NS": 422.40, "SYRMA.NS": 1376.90,
    "TATAPOWER.NS": 375.25, "ETHOSLTD.NS": 2494.80, "SPARC.NS": 239.37,
    "SOUTHBANK.NS": 46.11, "ETERNAL.NS": 281.65, "BAJAJHFL.NS": 91.35,
    "TANLA.NS": 539.05,
    "MF:Kotak Midcap Fund": 169.95, "MF:Tata Small Cap Fund": 43.45,
    "MF:HDFC Mid Cap Fund": 229.59, "MF:Mirae Large & Midcap": 178.15,
    "MF:Kotak Bond Short Term": 61.03, "MF:HDFC Corporate Bond": 35.26,
    "MF:HDFC Small Cap Fund": 158.70, "MF:HSBC Corporate Bond": 82.76,
    "NVDA": 194.83, "GOOGL": 359.91, "META": 582.90, "AAPL": 308.63,
    "TWLO": 209.31, "AVGO": 360.45, "TSLA": 393.45, "JNJ": 263.04,
    "O": 63.84, "KO": 84.14, "V": 362.13, "MCD": 280.63, "MSFT": 390.49,
    "SNDK": 1745.00,
}

MARKER_RE = re.compile(
    r"(<!--PF_DATA_START-->).*?(<!--PF_DATA_END-->)", re.DOTALL
)


# ------------------------------------------------------------
# Fetchers
# ------------------------------------------------------------

def fetch_yahoo(tickers):
    """Return {ticker: last_close}. Tries a bulk download, then falls back to
    per-ticker requests so one bad symbol can't take down the whole run."""
    import yfinance as yf
    out = {}

    # Pass 1 — bulk (fast). Wrapped because yfinance's frame shape varies.
    try:
        data = yf.download(tickers, period="7d", progress=False,
                           auto_adjust=False, group_by="ticker", threads=True)
        for t in tickers:
            try:
                if len(tickers) > 1:
                    closes = data[t]["Close"].dropna()
                else:
                    closes = data["Close"].dropna()
                if len(closes):
                    out[t] = float(closes.iloc[-1])
            except Exception:
                pass
    except Exception as e:
        print(f"  ~ bulk download unavailable ({e}); falling back per ticker")

    # Pass 2 — per ticker for anything still missing.
    missing = [t for t in tickers if t not in out]
    for t in missing:
        got = False
        for attempt in range(2):
            try:
                hist = yf.Ticker(t).history(period="7d")
                closes = hist["Close"].dropna()
                if len(closes):
                    out[t] = float(closes.iloc[-1])
                    got = True
                    break
            except Exception as e:
                err = e
        if not got:
            print(f"  ! Yahoo fetch failed for {t} — will reuse previous value")

    print(f"  got {len(out)}/{len(tickers)} equity prices")
    return out


def fetch_mf_nav(query, label):
    """Latest Direct-Growth NAV via mfapi.in. Returns (nav, scheme_name) or None."""
    import requests
    if label in SCHEME_OVERRIDES:
        code = SCHEME_OVERRIDES[label]
        r = requests.get(f"https://api.mfapi.in/mf/{code}/latest", timeout=20)
        j = r.json()
        return float(j["data"][0]["nav"]), j["meta"]["scheme_name"]
    r = requests.get("https://api.mfapi.in/mf/search", params={"q": query}, timeout=20)
    cands = [c for c in r.json()
             if "direct" in c["schemeName"].lower()
             and "growth" in c["schemeName"].lower()
             and "idcw" not in c["schemeName"].lower()]
    if not cands:
        print(f"  ! No Direct-Growth match for '{query}' — pin it in SCHEME_OVERRIDES")
        return None
    # Shortest matching name is almost always the plain Growth plan
    best = min(cands, key=lambda c: len(c["schemeName"]))
    code = best["schemeCode"]
    r = requests.get(f"https://api.mfapi.in/mf/{code}/latest", timeout=20)
    nav = float(r.json()["data"][0]["nav"])
    return nav, best["schemeName"]


# ------------------------------------------------------------
# Core
# ------------------------------------------------------------

def get_prices(offline):
    prices = {}
    if offline:
        print("OFFLINE MODE — using baked screenshot closes")
        return dict(BAKED)

    yf_tickers = []
    for book in CONFIG.values():
        for h in book["holdings"]:
            if h.get("yf"):
                yf_tickers.append(h["yf"])
    print(f"Fetching {len(yf_tickers)} equities from Yahoo Finance...")
    prices.update(fetch_yahoo(yf_tickers))

    print("Fetching mutual fund NAVs from mfapi.in...")
    for h in CONFIG["inmf"]["holdings"]:
        res = fetch_mf_nav(h["mf_q"], h["t"])
        if res:
            nav, name = res
            prices[f"MF:{h['t']}"] = nav
            print(f"  {h['t']}: NAV {nav} ({name})")
    return prices


def previous_price(old_json, book_key, label, avg):
    """Reconstruct last known price from the existing page JSON (avg*(1+p))."""
    try:
        for h in old_json["books"][book_key]["holdings"]:
            if h["t"] == label:
                return avg * (1 + h["p"] / 100.0)
    except Exception:
        pass
    return None


def build_json(prices, old_json):
    books_out = {}
    for key, book in CONFIG.items():
        rows, tot_val, tot_inv = [], 0.0, 0.0
        for h in book["holdings"]:
            if h.get("static_price") is not None:
                px = h["static_price"]
            else:
                pkey = h["yf"] if h.get("yf") else f"MF:{h['t']}"
                px = prices.get(pkey)
                if px is None:
                    px = previous_price(old_json, key, h["t"], h["avg"])
                    if px is None:
                        print(f"  !! No price for {h['t']} and no fallback — skipping run")
                        sys.exit(1)
                    print(f"  ~ {h['t']}: using previous value (fetch failed)")
            val = h["qty"] * px
            inv = h["qty"] * h["avg"]
            rows.append({"t": h["t"], "_val": val,
                         "p": round((px / h["avg"] - 1) * 100, 2), "th": h["th"]})
            tot_val += val
            tot_inv += inv
        rows.sort(key=lambda r: -r["_val"])
        holdings = [{"t": r["t"], "w": round(r["_val"] / tot_val * 100, 2),
                     "p": r["p"], "th": r["th"]} for r in rows]
        books_out[key] = {
            "name": book["name"],
            "count": len(holdings),
            "overall": round((tot_val - tot_inv) / tot_inv * 100, 2),
            "holdings": holdings,
        }
    asof = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    return {"asof": asof, "books": books_out}


def inject(html_path, payload):
    html = open(html_path, encoding="utf-8").read()
    old = None
    m = re.search(r'<script type="application/json" id="pf-data">(.*?)</script>',
                  html, re.DOTALL)
    if m:
        try:
            old = json.loads(m.group(1))
        except Exception:
            old = None
    block = ('<!--PF_DATA_START-->\n'
             '<script type="application/json" id="pf-data">'
             + json.dumps(payload, ensure_ascii=False)
             + '</script>\n<!--PF_DATA_END-->')
    new_html, n = MARKER_RE.subn(block, html)
    if n != 1:
        print("!! PF_DATA markers not found exactly once — aborting")
        sys.exit(1)
    open(html_path, "w", encoding="utf-8").write(new_html)
    return old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--file", default="index.html")
    args = ap.parse_args()

    # read existing JSON first for fallbacks
    html = open(args.file, encoding="utf-8").read()
    old_json = None
    m = re.search(r'<script type="application/json" id="pf-data">(.*?)</script>',
                  html, re.DOTALL)
    if m:
        try:
            old_json = json.loads(m.group(1))
        except Exception:
            old_json = None

    prices = get_prices(args.offline)
    payload = build_json(prices, old_json)
    inject(args.file, payload)

    print(f"\nUpdated {args.file} — as of {payload['asof']}")
    for k, b in payload["books"].items():
        print(f"  {b['name']}: {b['count']} holdings, overall {b['overall']:+.2f}%")


if __name__ == "__main__":
    main()
