import time
import random
import pandas as pd
import sqlalchemy as db
from sqlalchemy import text
from bs4 import BeautifulSoup

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ── Config ─────────────────────────────────────────────────────────────────────

# Set to True to run Chrome in the background (no visible window)
HEADLESS = True


# ── Helpers ────────────────────────────────────────────────────────────────────

def human_delay(min_s=1.2, max_s=3.5):
    """Random pause to simulate human behaviour."""
    time.sleep(random.uniform(min_s, max_s))


def human_type(actions, text):
    """Type a string character by character with random inter-key delays."""
    for char in text:
        actions.send_keys(char)
        actions.perform()
        time.sleep(random.uniform(0.05, 0.18))


def wait_for(driver, by, selector, timeout=15):
    """Explicit wait until an element is clickable."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )


# ── Scraper functions ──────────────────────────────────────────────────────────

def select_event(event, driver):
    """Navigate to a specific event page on ForexFactory."""
    actions = ActionChains(driver)

    # Click the category filter (Events tab)
    wait_for(driver, By.XPATH,
             '//*[@id="content"]/section[2]/div[3]/div/div/div/div/div[1]/ul/li[7]/a').click()
    human_delay(1.5, 3.0)

    # Click the search input
    search_input = wait_for(driver, By.XPATH, '//*[@id="calendar-search-input"]')
    search_input.click()
    human_delay(0.5, 1.2)

    # Type the event name in a human-like way
    human_type(actions, event)
    human_delay(1.0, 2.0)

    # Click the exact result link
    wait_for(driver, By.LINK_TEXT, event).click()
    human_delay(2.0, 3.5)

    return driver


def load_all_history(driver):
    """
    Scroll down repeatedly to load all historical data.
    Stops when the footer gains the 'hidden' class, meaning everything is loaded.
    """
    actions = ActionChains(driver)

    while True:
        try:
            driver.find_element(By.CSS_SELECTOR, ".foot.hidden")
            # Footer is hidden → all data has been loaded
            human_delay(0.8, 1.5)
            actions.send_keys(Keys.HOME).perform()
            human_delay(0.5, 1.0)
            break

        except NoSuchElementException:
            # More data available → click the "more" button
            try:
                more_btn = driver.find_element(By.CLASS_NAME, "more")
                more_btn.click()
                human_delay(0.8, 1.8)
            except NoSuchElementException:
                # Neither hidden footer nor "more" button found → exit
                break

    return driver


def parse_upcoming_date(driver):
    """
    Extract the next scheduled (upcoming) release date from the event page.

    ForexFactory marks the upcoming release with:
      <a class="calendar-event__release calendar-event__release--upcoming">
        ...
        <span class="darktext">Mar 19<span class="visible-tv visible-dv"> 2026</span>, 1:30pm</span>
        ...
      </a>

    The inner <span> tags (year, visibility helpers) are included in .get_text(),
    so we grab the full text and let pandas parse it.
    Returns a normalised Timestamp, or None if not found.
    """
    soup = BeautifulSoup(driver.page_source, "lxml")

    upcoming_block = soup.find("a", class_="calendar-event__release--upcoming")
    if upcoming_block is None:
        return None

    date_span = upcoming_block.find("span", class_="darktext")
    if date_span is None:
        return None

    try:
        # get_text() merges all inner spans → "Mar 19 2026, 1:30pm"
        raw = date_span.get_text(" ", strip=True)
        return pd.to_datetime(raw).normalize()
    except Exception:
        return None


def parse_events(driver):
    """
    Extract dates, current values and previous values from the page HTML.
    Returns a dict { datetime: (current, previous) }
    """
    soup = BeautifulSoup(driver.page_source, "lxml")

    dates      = soup.find_all(class_="calendarhistory__row nowrap calendarhistory__row--history")
    currents   = soup.find_all(class_="calendarhistory__row calendarhistory__row--actual")
    previouses = soup.find_all(class_="calendarhistory__row calendarhistory__row--previous nowrap")

    data = {}
    for i in range(len(dates)):
        try:
            date = pd.to_datetime(dates[i].text.strip())
        except Exception:
            continue

        current  = currents[i].text.strip()   if i < len(currents)   else None
        previous = previouses[i].text.strip() if i < len(previouses) else None

        data[date] = (current, previous)

    print(f"{len(data)} records found")
    return data


# ── Main function ──────────────────────────────────────────────────────────────

def search_event(engine):
    events = [
        # Monetary policy
        "US Federal Funds Rate",
        "US FOMC Statement",
        "US FOMC Press Conference",
        "US FOMC Economic Projections",

        # Inflation
        "US Core CPI m/m",
        "US CPI m/m",
        "US CPI y/y",
        "US PPI m/m",
        "US Core PCE Price Index m/m",

        # Labour market
        "US Non-Farm Employment Change",
        "US Unemployment Rate",
        "US Average Hourly Earnings m/m",

        # Growth
        "US Advance GDP q/q",
        "US Prelim GDP q/q",
        "US Final GDP q/q",

        # Spending
        "US Retail Sales m/m",
        "US Core Retail Sales m/m",
        "US Personal Spending m/m",
        "US Personal Income m/m",

        # Economic sentiment
        "US ISM Manufacturing PMI",
        "US ISM Services PMI",

        # Housing
        "US Building Permits",
        "US Housing Starts",
        "US Existing Home Sales",
        "US New Home Sales",
    ]

    # ── Database setup ─────────────────────────────────────────────────────────
    #engine = db.create_engine("sqlite:///../data/raw/data.db")

    # Create tables if they do not exist yet
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Events (
                date     TEXT,
                event    TEXT,
                current  TEXT,
                previous TEXT,
                PRIMARY KEY (date, event)
            )
        """))
        # Schedule table: stores the next known release date for each event
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Schedule (
                event         TEXT PRIMARY KEY,
                upcoming_date TEXT
            )
        """))
        conn.commit()

    # ── Chrome driver setup ────────────────────────────────────────────────────
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # headless=True hides the browser window; set HEADLESS = False at the top to watch it run
    driver = uc.Chrome(options=options, headless=HEADLESS, version_main=145)

    # Remove any remaining webdriver traces
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    try:
        driver.get("https://www.forexfactory.com/calendar")
        human_delay(3.0, 5.0)

        today = pd.Timestamp.now().normalize()

        for event in events:
            print(f"\n[+] {event}")

            # ── Check the stored upcoming date ─────────────────────────────────
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT upcoming_date FROM Schedule WHERE event = :e"),
                    {"e": event}
                ).fetchone()
                stored_upcoming = pd.to_datetime(row[0]).normalize() if row and row[0] else None

            if stored_upcoming is not None and stored_upcoming > today:
                print(f"Skipped — next release on {stored_upcoming.date()} (not yet passed)")
                continue

            # ── Fetch the most recent saved date for this event ────────────────
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT MAX(date) FROM Events WHERE event = :e"),
                    {"e": event}
                )
                last_date = result.scalar()
                last_date = pd.to_datetime(last_date).normalize() if last_date else None

            # ── Navigate and scrape ────────────────────────────────────────────
            try:
                driver = select_event(event, driver)
                driver = load_all_history(driver)

                upcoming_date = parse_upcoming_date(driver)
                data          = parse_events(driver)
            except (TimeoutException, NoSuchElementException) as e:
                print(f"Error processing '{event}': {e}")
                driver.get("https://www.forexfactory.com/calendar")
                human_delay(3.0, 5.0)
                continue

            # ── Save new event records ─────────────────────────────────────────
            saved = 0
            with engine.connect() as conn:
                for date, (current, previous) in data.items():
                    if last_date is None or date > last_date:
                        conn.execute(
                            text("INSERT OR IGNORE INTO Events VALUES (:d, :e, :c, :p)"),
                            {"d": str(date), "e": event, "c": current, "p": previous}
                        )
                        saved += 1
                conn.commit()

            print(f"{saved} new records saved")

            # ── Update the upcoming date in Schedule ───────────────────────────
            if upcoming_date is not None:
                with engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO Schedule VALUES (:e, :u)
                        """),
                        {"e": event, "u": str(upcoming_date)}
                    )
                    conn.commit()
                print(f"Next release stored: {upcoming_date.date()}")

            # ── Return to the calendar before the next event ───────────────────
            driver.get("https://www.forexfactory.com/calendar")
            human_delay(2.5, 4.5)

    finally:
        driver.quit()
        print("\nAll events up to date. Driver closed.")


if __name__ == "__main__":
    search_event()