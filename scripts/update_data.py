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
    page.evaluate("""
        const span = Array.from(document.querySelectorAll('span'))
            .find(s => /^2026\\d{2}$/.test(s.textContent.trim()));
        if (span) span.closest('button')?.click();
    """)
    time.sleep(0.5)

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


def scrape_agent_names(page):
    """Extract just agent names from the agent grid on the current page view."""
    return page.evaluate("""
        (() => {
            const grids = document.querySelectorAll('[role="treegrid"]');
            for (const grid of grids) {
                const headers = Array.from(grid.querySelectorAll('[role="columnheader"]'))
                    .map(h => h.textContent.trim());
                if (!headers.includes('agent')) continue;
                const rows = grid.querySelectorAll('[role="row"]');
                const names = [];
                rows.forEach(row => {
                    const cells = row.querySelectorAll('[role="gridcell"]');
                    if (cells.length >= 3) {
                        const name = cells[1]?.textContent.trim();
                        if (name) names.push(name);
                    }
                });
                return names;
            }
            return [];
        })()
    """)


def scrape_agent_data(page):
    """Extract agent CSAT data from the agent grid on the current page view."""
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


def clear_supervisor_filter(page):
    """Clear the Supervisors filter back to 'All'."""
    # Remove any individual supervisor tags, then re-add "All"
    page.evaluate("""
        (() => {
            // Find the Supervisors parameter section
            const labels = Array.from(document.querySelectorAll('span'));
            const supLabel = labels.find(s => s.textContent.trim() === 'Supervisors');
            if (!supLabel) return;
            const container = supLabel.closest('[class*="AppCell"]');
            if (!container) return;
            // Click all remove (x) buttons on tags to clear selections
            const removeButtons = container.querySelectorAll('[class*="bp5-tag-remove"], button[class*="remove"]');
            removeButtons.forEach(btn => btn.click());
        })()
    """)
    time.sleep(0.5)

    # Now type "All" and select it
    page.evaluate("""
        (() => {
            const labels = Array.from(document.querySelectorAll('span'));
            const supLabel = labels.find(s => s.textContent.trim() === 'Supervisors');
            if (!supLabel) return;
            const container = supLabel.closest('[class*="AppCell"]');
            if (!container) return;
            const input = container.querySelector('input');
            if (input) {
                input.focus();
                input.value = '';
                input.dispatchEvent(new Event('input', {bubbles: true}));
            }
        })()
    """)
    time.sleep(0.5)

    # Click "All" option in the dropdown
    page.evaluate("""
        (() => {
            const menuItems = document.querySelectorAll('[class*="bp5-menu-item"], [role="option"]');
            const allItem = Array.from(menuItems).find(m => m.textContent.trim() === 'All');
            if (allItem) allItem.click();
        })()
    """)
    time.sleep(2)
    wait_for_data_loaded(page)


def select_supervisor_filter(page, supervisor_name):
    """Select a single supervisor in the Supervisors filter dropdown."""
    # First clear any existing selection
    page.evaluate("""
        (() => {
            const labels = Array.from(document.querySelectorAll('span'));
            const supLabel = labels.find(s => s.textContent.trim() === 'Supervisors');
            if (!supLabel) return;
            const container = supLabel.closest('[class*="AppCell"]');
            if (!container) return;
            // Click all remove (x) buttons on tags
            const removeButtons = container.querySelectorAll('[class*="bp5-tag-remove"], button[class*="remove"]');
            removeButtons.forEach(btn => btn.click());
        })()
    """)
    time.sleep(0.5)

    # Click on the input and type the supervisor name
    page.evaluate("""
        (() => {
            const labels = Array.from(document.querySelectorAll('span'));
            const supLabel = labels.find(s => s.textContent.trim() === 'Supervisors');
            if (!supLabel) return;
            const container = supLabel.closest('[class*="AppCell"]');
            if (!container) return;
            const input = container.querySelector('input');
            if (input) {
                input.focus();
                input.click();
            }
        })()
    """)
    time.sleep(0.3)

    # Type the supervisor name to filter
    page.evaluate(f"""
        (() => {{
            const labels = Array.from(document.querySelectorAll('span'));
            const supLabel = labels.find(s => s.textContent.trim() === 'Supervisors');
            if (!supLabel) return;
            const container = supLabel.closest('[class*="AppCell"]');
            if (!container) return;
            const input = container.querySelector('input');
            if (input) {{
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                nativeInputValueSetter.call(input, '{supervisor_name}');
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }})()
    """)
    time.sleep(1)

    # Click the matching option in the dropdown
    page.evaluate(f"""
        (() => {{
            const menuItems = document.querySelectorAll(
                '[class*="bp5-menu-item"], [role="option"], [class*="menu"] li'
            );
            const match = Array.from(menuItems).find(
                m => m.textContent.trim() === '{supervisor_name}'
            );
            if (match) match.click();
        }})()
    """)
    time.sleep(2)
    wait_for_data_loaded(page)
    time.sleep(1)


def scrape_supervisor_agent_mapping(page, supervisor_names):
    """
    For each supervisor, apply the filter and read which agents appear.
    Returns dict: { supervisor_name: [agent_name, ...] }
    """
    mapping = {}
    for sup_name in supervisor_names:
        print(f"    Filtering for {sup_name}...", end=" ", flush=True)
        select_supervisor_filter(page, sup_name)
        agents = scrape_agent_names(page)
        # Filter to target agents only
        agents = [a for a in agents if a in TARGET_AGENTS]
        mapping[sup_name] = agents
        print(f"{len(agents)} agents")

    # Reset filter to All
    clear_supervisor_filter(page)
    time.sleep(1)

    return mapping


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

        # Scrape data for each week from the weekly-agents-performance tab
        for week in weeks:
            print(f"\n=== Week {week} ===")
            select_week(page, week)
            dates = get_week_dates(page)

            # Update weeks list
            existing_weeks = {w["week"]: w for w in data["weeks"]}
            if week not in existing_weeks:
                data["weeks"].append({
                    "week": week,
                    "start": dates.get("start", ""),
                    "end": dates.get("end", "")
                })
            data["weeks"] = sorted(data["weeks"], key=lambda w: w["week"])

            # 1. Scrape supervisor CSAT data
            sup_rows = scrape_supervisor_data(page)
            supervisor_names = []
            for row in sup_rows:
                name = row["name"]
                supervisor_names.append(name)
                if name not in data["supervisors"]:
                    data["supervisors"][name] = {}
                data["supervisors"][name][week] = {
                    "zd": parse_pct(row["zd"]),
                    "tidio": parse_pct(row["tidio"]),
                }
            print(f"  Supervisors: {len(sup_rows)}")

            # 2. Scrape agent CSAT data (with filter set to All)
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
            print(f"  Agents: {len(agent_rows)}")

            # 3. Scrape supervisor-agent mapping by filtering each supervisor
            print("  Mapping supervisors to agents...")
            mapping = scrape_supervisor_agent_mapping(page, supervisor_names)
            for sup_name, agent_list in mapping.items():
                for agent_name in agent_list:
                    if agent_name in data["agents"] and week in data["agents"][agent_name]:
                        data["agents"][agent_name][week]["supervisor"] = sup_name

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
