"""Playwright-based tee time scraper and booker for Milwaukee County WebTrac."""

import logging
import re
from datetime import date, datetime
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import config
import db

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
PAGE_TIMEOUT_MS = 30_000
RESULTS_WAIT_MS = 15_000


def _build_search_url(course_code: str, target_date: date) -> str:
    """Build the WebTrac search URL with pre-filled parameters."""
    date_str = target_date.strftime("%m/%d/%Y")
    params = (
        f"?module=GR"
        f"&display=detail"
        f"&secondarycode={course_code}"
        f"&begindate={date_str}"
        f"&numberofplayers={config.PREFERRED_PLAYERS}"
        f"&numberofholes={config.PREFERRED_HOLES}"
    )
    return config.WEBTRAC_BASE_URL + params


def scrape_course(
    page, course_name: str, course_code: str, target_date: date
) -> list[dict]:
    """Scrape available tee times for a single course.

    Returns list of dicts with keys: course_name, course_code, tee_time,
    holes, price_display, spots, source_url.
    """
    url = _build_search_url(course_code, target_date)
    results = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Scraping {course_name} (code={course_code}), "
                f"attempt {attempt}/{MAX_RETRIES}"
            )
            page.goto(url, timeout=PAGE_TIMEOUT_MS)

            # Wait for the results table or a "no results" message
            try:
                page.wait_for_selector(
                    ".result-content, .filter-your-search",
                    timeout=RESULTS_WAIT_MS,
                )
            except PlaywrightTimeout:
                content = page.content()
                if "no results" in content.lower() or "did not return" in content.lower():
                    logger.info(f"No tee times found for {course_name} on {target_date}")
                    return []
                logger.warning(
                    f"Timeout waiting for results on {course_name}, attempt {attempt}"
                )
                if attempt < MAX_RETRIES:
                    continue
                return []

            # Check for "no results" message
            no_results = page.query_selector(".filter-your-search")
            if no_results and "did not return" in (no_results.inner_text() or "").lower():
                logger.info(f"No tee times for {course_name} on {target_date}")
                return []

            # Parse the results table — WebTrac renders tee times as table rows
            # Columns: Book | Time | Date | Holes | Course | Open Slots | More
            rows = page.query_selector_all(".result-content tbody tr")

            if not rows:
                logger.info(f"No result rows found for {course_name}")
                return []

            for row in rows:
                try:
                    cells = row.query_selector_all("td")
                    if len(cells) < 6:
                        continue

                    time_str = (cells[1].inner_text() or "").strip()
                    date_str = (cells[2].inner_text() or "").strip()
                    holes_str = (cells[3].inner_text() or "").strip()
                    course_str = (cells[4].inner_text() or "").strip()
                    slots_str = (cells[5].inner_text() or "").strip()

                    if not time_str or not date_str:
                        continue

                    # Parse datetime
                    try:
                        tee_datetime = datetime.strptime(
                            f"{date_str} {time_str}", "%m/%d/%Y %I:%M %p"
                        )
                    except ValueError:
                        logger.debug(f"Failed to parse time: {date_str} {time_str}")
                        continue

                    # Filter to morning only
                    if not _is_morning(tee_datetime):
                        continue

                    # Parse holes (e.g. "18 (Front)" -> 18)
                    holes_match = re.match(r"(\d+)", holes_str)
                    holes = int(holes_match.group(1)) if holes_match else config.PREFERRED_HOLES

                    # Parse open slots
                    try:
                        spots = int(slots_str)
                    except ValueError:
                        spots = 4

                    results.append({
                        "course_name": course_str or course_name,
                        "course_code": course_code,
                        "tee_time": tee_datetime,
                        "holes": holes,
                        "price_display": "",  # fees paid at check-in
                        "spots": spots,
                        "source_url": url,
                    })

                except Exception as e:
                    logger.debug(f"Failed to parse row for {course_name}: {e}")

            logger.info(f"Found {len(results)} morning tee times for {course_name}")
            return results

        except PlaywrightTimeout:
            logger.warning(f"Page load timeout for {course_name}, attempt {attempt}")
            if attempt == MAX_RETRIES:
                logger.error(f"Failed to scrape {course_name} after {MAX_RETRIES} attempts")
        except Exception as e:
            logger.error(f"Error scraping {course_name}: {e}")
            if attempt == MAX_RETRIES:
                raise

    return results


def _is_morning(dt: datetime) -> bool:
    """Check if a datetime is before the morning cutoff."""
    cutoff_hour, cutoff_min = (
        int(x) for x in config.SCRAPE_MORNING_CUTOFF.split(":")
    )
    return dt.hour < cutoff_hour or (dt.hour == cutoff_hour and dt.minute <= cutoff_min)


def _launch_browser(p):
    """Launch Chromium with settings that bypass Cloudflare bot detection."""
    browser = p.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    return browser, context


def scrape_tee_times(
    target_date: Optional[date] = None,
    courses: Optional[dict[str, str]] = None,
) -> list[dict]:
    """Scrape tee times for all configured courses on a given date."""
    if target_date is None:
        from scheduler import _next_friday
        target_date = _next_friday()

    if courses is None:
        courses = config.COURSES

    all_results = []

    with sync_playwright() as p:
        browser, context = _launch_browser(p)
        page = context.new_page()

        for course_name, course_code in courses.items():
            try:
                results = scrape_course(page, course_name, course_code, target_date)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Failed to scrape {course_name}: {e}")

        browser.close()

    logger.info(f"Total scraped: {len(all_results)} tee times across {len(courses)} courses")
    return all_results


def scrape_and_save(
    target_date: Optional[date] = None,
    courses: Optional[dict[str, str]] = None,
) -> int:
    """Scrape tee times and save them to the database.

    Returns the number of tee times saved.
    """
    if target_date is None:
        from scheduler import _next_friday
        target_date = _next_friday()

    # Ensure the week exists
    week = db.create_week(target_date)

    # Clear previous scraped times for this week
    cleared = db.clear_scraped_tee_times(week.id)
    if cleared:
        logger.info(f"Cleared {cleared} previously scraped tee times for {target_date}")

    # Scrape
    results = scrape_tee_times(target_date, courses)

    # Save to DB
    saved = 0
    now = datetime.now()
    for r in results:
        try:
            db.add_tee_time(
                week_id=week.id,
                course_name=r["course_name"],
                tee_time=r["tee_time"],
                holes=r["holes"],
                price_display=r["price_display"],
                spots=r["spots"],
                course_code=r["course_code"],
                source_url=r["source_url"],
                scraped_at=now,
            )
            saved += 1
        except Exception as e:
            logger.error(f"Failed to save tee time: {e}")

    logger.info(f"Saved {saved} tee times for {target_date}")
    return saved


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------

def _login(page) -> bool:
    """Log into WebTrac. Returns True on success."""
    login_url = "https://wimilwaukeectyweb.myvscloud.com/webtrac/web/login.html"
    page.goto(login_url, timeout=PAGE_TIMEOUT_MS)
    page.wait_for_selector("input[name='weblogin_username']", timeout=RESULTS_WAIT_MS)

    page.fill("input[name='weblogin_username']", config.WEBTRAC_USERNAME)
    page.fill("input[name='weblogin_password']", config.WEBTRAC_PASSWORD)
    page.click("button[type='submit'], input[type='submit'], .login-button, button:has-text('Login')")

    # Wait for redirect away from login page
    try:
        page.wait_for_url("**/web/**", timeout=10_000)
    except PlaywrightTimeout:
        pass

    # Check if login succeeded — if we're still on login page, it failed
    if "login" in page.url.lower():
        logger.error("WebTrac login failed — check credentials")
        return False

    logger.info("Logged into WebTrac successfully")
    return True


def book_tee_time(
    course_code: str,
    target_date: date,
    target_time: str,
    num_players: int = 4,
    num_holes: int = 18,
) -> bool:
    """Book a specific tee time on WebTrac.

    Args:
        course_code: WebTrac secondarycode for the course.
        target_date: Date of the tee time.
        target_time: Time string to match (e.g. "8:00 am").
        num_players: Number of players (default 4).
        num_holes: Number of holes (default 18).

    Returns:
        True if the tee time was added to cart and checkout initiated.
    """
    date_str = target_date.strftime("%m/%d/%Y")
    search_url = (
        f"{config.WEBTRAC_BASE_URL}"
        f"?module=GR&display=detail"
        f"&secondarycode={course_code}"
        f"&begindate={date_str}"
        f"&numberofplayers={num_players}"
        f"&numberofholes={num_holes}"
    )

    with sync_playwright() as p:
        browser, context = _launch_browser(p)
        page = context.new_page()

        # Login first
        if not _login(page):
            browser.close()
            return False

        # Navigate to search results
        logger.info(f"Searching for tee time: {target_time} on {target_date}")
        page.goto(search_url, timeout=PAGE_TIMEOUT_MS)

        try:
            page.wait_for_selector(".result-content", timeout=RESULTS_WAIT_MS)
        except PlaywrightTimeout:
            logger.error("No results found for booking search")
            browser.close()
            return False

        # Find the matching tee time row and click Add To Cart
        rows = page.query_selector_all(".result-content tbody tr")
        target_normalized = target_time.strip().lower()

        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) < 6:
                continue
            row_time = (cells[1].inner_text() or "").strip().lower()
            if row_time == target_normalized:
                cart_btn = row.query_selector(".cart-button")
                if cart_btn:
                    cart_btn.click()
                    logger.info(f"Added tee time {target_time} to cart")

                    # Wait for cart/checkout page to load
                    page.wait_for_timeout(3000)

                    # At this point the browser is open for the user to
                    # complete checkout (confirm players, payment, etc.)
                    logger.info(
                        "Tee time added to cart. Complete checkout in the browser window."
                    )
                    # Keep browser open for user to finish
                    input("Press Enter after you've completed checkout...")
                    browser.close()
                    return True

        logger.error(f"Could not find tee time {target_time} in results")
        browser.close()
        return False
