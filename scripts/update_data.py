#!/usr/bin/env python3
"""
Weekly CSAT data updater.

This script scrapes the HEX CS Agents Performance report and updates data.json.
It uses Playwright to automate the browser interaction with the HEX app.

Usage:
  pip install playwright
  playwright install chromium
  python scripts/update_data.py

Environment variables:
  HEX_EMAIL    - Your HEX login email
  HEX_PASSWORD - Your HEX login password
  (If not set, assumes you're already logged in via cookies)
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

HEX_URL = (
    "https://app.hex.tech/122d0b88-6d5d-4970-baf8-9903b675dbd7/"
    "app/CS-Agents-Performance-0319cw9cr1Oeq7k7Bz5KP1/latest"
    "?tab=weekly-agents-performance"
)

BY_AGENT_URL = (
    "https://app.hex.tech/122d0b88-6d5d-4970-baf8-9903b675dbd7/"
    "app/CS-Agents-Performance-0319cw9cr1Oeq7k7Bz5KP1/latest"
    "?tab=by-agent"
)

TARGET_AGENTS = [
    "Damian Doubrava", "Enrico Davis", "Rachel Dunlap", "Samantha Decastro",
    "Bo Repko", "Rosa Nuno", "Jessie Gregory", "Cristie Avant",
    "Blanca Berumen", "Sarah Hajiali", "Taylor Amos", "Andre Cordero",
    "Ariashe Lowery", "Preston Panetti", "Bicky Purewal", "Asia Campbell",
    "Bianca Young", "Sarah Al-Obaidi", "Unaisa Aslam", "Chassidy Williams",
    "Morgan Lankford", "Chisa Ordu", "Michael Scott Chavez", "Eri Dotson",
    "Michael Nguyen", "Amber Bailey", "Ramila Chaulagain", "Jeremy Carrillo",
]

DATA_FILE = Path(__file__).parent.parent / "data.json"


def parse_pct(val):
    """Parse a percentage string like '92%' to an int, or return None."""
    if not val or val in ("null", "nan", "No value", "undefined", "-"):
        return None
    try:
        return round(float(val.replace("%", "")))
    except (ValueError, TypeError):
        return None


def wait_for_data_loaded(page, timeout=30):
    """Wait until HEX finishes loading data (no 'Still loading' text)."""
    start = time.time()
    while time.time() - start < timeout:
        loading = page.evaluate("document.body.innerText.includes('Still loading')")
        if not loading:
            return True
        time.sleep(1)
    return False


def get_available_weeks(page):
    """Open the week dropdown and return list of week strings like ['202611', ...]."""
    # Click the week selector button
    page.evaluate("""
        const span = Array.from(document.querySelectorAll('span'))
            .find(s => /^2026\\d{2}$/.test(s.textContent.trim()));
        if (span) span.closest('button')?.click();
    """)
    time.sleep(1)

    weeks = page.evaluate("""
        Array.from(document.querySelectorAll('label.bp5-control.bp5-radio'))
            .map(l => l.textContent.trim())
            .filter(t => /^2026\\d{2}$/.test(t))
    """)
    return sorted(weeks)


def select_week(page, week_num):
    """Select a specific week in the dropdown."""
    # Open dropdown
    page.evaluate("""
        const span = Array.from(document.querySelectorAll('span'))
            .find(s => /^2026\\d{2}$/.test(s.textContent.trim()));
        if (span) span.closest('button')?.click();
    """)
    time.sleep(0.5)

    # Click the radio for the target week
    page.evaluate(f"""
        const labels = document.querySelectorAll('label.bp5-control.bp5-radio');
        const target = Array.from(labels).find(l => l.textContent.trim() === '{week_num}');
        if (target) target.querySelector('input')?.click();
    """)
    time.sleep(2)
    wait_for_data_loaded(page)
    time.sleep(1)


def scrape_supervisor_data(page):
    """Extract supervisor CSAT data from the current page view."""
    return page.evaluate("""
        (() => {
            const grids = document.querySelectorAll('[role="treegrid"]');
            for (const grid of grids) {
                const headers = Array.from(grid.querySelectorAll('[role="columnheader"]'))
                    .map(h => h.textContent.trim());
                if (!headers.includes('supervisor')) continue;
                const rows = grid.querySelectorAll('[role="row"]');
                const data = [];
                rows.forEach(row => {
                    const cells = row.querySelectorAll('[role="gridcell"]');
                    if (cells.length >= 5) {
                        const name = cells[1]?.textContent.trim();
                        const zd = cells[3]?.textContent.trim();
                        const tidio = cells[4]?.textContent.trim();
                        if (name) data.push({name, zd, tidio});
                    }
                });
                return data;
            }
            return [];
        })()
    """)


def scrape_agent_data(page):
    """Extract agent CSAT data from the current page view."""
    return page.evaluate("""
        (() => {
            const grids = document.querySelectorAll('[role="treegrid"]');
            for (const grid of grids) {
                const headers = Array.from(grid.querySelectorAll('[role="columnheader"]'))
                    .map(h => h.textContent.trim());
                if (!headers.includes('agent')) continue;
                const rows = grid.querySelectorAll('[role="row"]');
                const data = [];
                rows.forEach(row => {
                    const cells = row.querySelectorAll('[role="gridcell"]');
                    if (cells.length >= 5) {
                        const name = cells[1]?.textContent.trim();
                        const zd = cells[3]?.textContent.trim();
                        const tidio = cells[4]?.textContent.trim();
                        if (name) data.push({name, zd, tidio});
                    }
                });
                return data;
            }
            return [];
        })()
    """)


def get_week_dates(page):
    """Get the week start/end dates from the current page."""
    return page.evaluate("""
        (() => {
            const text = document.body.innerText;
            const starts = text.match(/2026-\\d{2}-\\d{2}\\nWeek since/);
            const ends = text.match(/2026-\\d{2}-\\d{2}\\nWeek until/);
            const startDate = starts ? starts[0].split('\\n')[0] : null;
            const endDate = ends ? ends[0].split('\\n')[0] : null;
            return {start: startDate, end: endDate};
        })()
    """)


def main():
    print("Starting CSAT data update...")

    # Load existing data
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            data = json.load(f)
    else:
        data = {"last_updated": "", "weeks": [], "agents": {}, "supervisors": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # If HEX credentials are provided, handle login
        hex_email = os.environ.get("HEX_EMAIL")
        hex_password = os.environ.get("HEX_PASSWORD")

        page = context.new_page()
        page.goto(HEX_URL, wait_until="networkidle", timeout=60000)
        time.sleep(5)

        # Handle login if needed
        if hex_email and hex_password:
            try:
                email_input = page.query_selector('input[type="email"]')
                if email_input:
                    print("Logging in to HEX...")
                    email_input.fill(hex_email)
                    page.click('button:has-text("Continue")')
                    time.sleep(2)
                    pwd_input = page.query_selector('input[type="password"]')
                    if pwd_input:
                        pwd_input.fill(hex_password)
                        page.click('button:has-text("Sign in")')
                        time.sleep(5)
            except Exception as e:
                print(f"Login attempt: {e}")

        wait_for_data_loaded(page, timeout=30)
        print("Page loaded.")

        # Get available weeks
        weeks = get_available_weeks(page)
        print(f"Available weeks: {weeks}")

        # Scrape supervisor data for each week
        print("\n--- Scraping supervisor data ---")
        for week in weeks:
            print(f"  Week {week}...", end=" ", flush=True)
            select_week(page, week)
            dates = get_week_dates(page)
            sup_rows = scrape_supervisor_data(page)

            # Update weeks list
            existing_weeks = {w["week"]: w for w in data["weeks"]}
            if week not in existing_weeks:
                data["weeks"].append({
                    "week": week,
                    "start": dates.get("start", ""),
                    "end": dates.get("end", "")
                })
            data["weeks"] = sorted(data["weeks"], key=lambda w: w["week"])

            # Update supervisor data
            for row in sup_rows:
                name = row["name"]
                if name not in data["supervisors"]:
                    data["supervisors"][name] = {}
                data["supervisors"][name][week] = {
                    "zd": parse_pct(row["zd"]),
                    "tidio": parse_pct(row["tidio"]),
                }
            print(f"{len(sup_rows)} supervisors")

        # Now scrape agent data from the by-agent tab
        print("\n--- Scraping agent data ---")
        page.goto(BY_AGENT_URL, wait_until="networkidle", timeout=60000)
        time.sleep(5)
        wait_for_data_loaded(page)

        # The by-agent tab may have a different selector mechanism
        # We iterate weeks there too
        for week in weeks:
            print(f"  Week {week}...", end=" ", flush=True)
            select_week(page, week)
            agent_rows = scrape_agent_data(page)

            for row in agent_rows:
                name = row["name"]
                if name not in TARGET_AGENTS:
                    continue
                if name not in data["agents"]:
                    data["agents"][name] = {}
                data["agents"][name][week] = {
                    "zd": parse_pct(row["zd"]),
                    "tidio": parse_pct(row["tidio"]),
                }
            print(f"{len(agent_rows)} agents (filtered to target list)")

        browser.close()

    # Update timestamp
    data["last_updated"] = date.today().isoformat()

    # Save
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved to {DATA_FILE}")
    print("Done!")


if __name__ == "__main__":
    main()
