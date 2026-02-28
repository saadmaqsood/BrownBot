"""
Module: src/scraper/courses.py
Purpose: Scrape course data from Courses @ Brown (CAB) using Playwright.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from src.scraper.schema import empty_course, normalize_course_code
from src.config import CAB_MAX_SCROLLS, CAB_SCROLL_PAUSE_MS

CAB_URL = "https://cab.brown.edu/"

# Chromium flags needed for running in containers (Docker/CI)
BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]


def _scroll_to_bottom(page, max_scrolls=CAB_MAX_SCROLLS, pause=CAB_SCROLL_PAUSE_MS):
    """Scroll to bottom of CAB results to load all courses via infinite scroll.

    Uses Playwright's built-in wait instead of time.sleep so the browser
    event-loop keeps running and network requests can complete.
    """
    for _ in range(max_scrolls):
        prev_count = page.locator("div.result.result--group-start").count()
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        # Give the page time to fire XHR and render new results
        page.wait_for_timeout(pause)
        new_count = page.locator("div.result.result--group-start").count()
        if new_count == prev_count:
            break


def _parse_courses_from_html(html):
    """Parse course data from CAB HTML."""
    soup = BeautifulSoup(html, "html.parser")
    course_items = soup.select("div.result.result--group-start")
    courses = []

    for item in course_items:
        course = empty_course()
        raw_code = (
            item.select_one("span.result__code").get_text(strip=True)
            if item.select_one("span.result__code")
            else ""
        )
        course["course_code"] = normalize_course_code(raw_code)
        course["title"] = (
            item.select_one("span.result__title").get_text(strip=True)
            if item.select_one("span.result__title")
            else ""
        )
        course["department"] = (
            course["course_code"].split()[0] if course["course_code"] else ""
        )
        course["source"] = "CAB"

        for span in item.find_all("span", class_="sr-only"):
            label = span.get_text(strip=True)
            sibling_text = span.find_next_sibling(string=True)
            if not sibling_text:
                continue
            value = sibling_text.strip()
            if label.startswith("Meets:"):
                course["meeting_times"] = value
            elif label.startswith("Instructor:"):
                course["instructor"] = value

        courses.append(course)

    return courses


def fetch_courses_cab():
    """Fetch all course listings from CAB by clicking search and scrolling.

    Returns:
        List[dict]: list of course dictionaries following the unified schema
    """
    courses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=BROWSER_ARGS)
        page = browser.new_page()
        page.goto(CAB_URL, wait_until="networkidle")

        # Click the search button to load all results
        page.click("#search-button")

        # Wait for first batch of results to appear
        page.wait_for_selector("div.result.result--group-start", timeout=30000)

        # Let the initial result set finish rendering
        page.wait_for_load_state("networkidle")

        # Scroll to load all results
        _scroll_to_bottom(page)

        html = page.content()
        courses = _parse_courses_from_html(html)

        browser.close()

    print(f"Fetched {len(courses)} CAB courses")
    return courses


if __name__ == "__main__":
    test_courses = fetch_courses_cab()
    for c in test_courses[:5]:
        print(c)
