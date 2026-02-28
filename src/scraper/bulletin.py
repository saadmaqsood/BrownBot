"""
Module: src/scraper/bulletin.py
Purpose: Scrape course listings from Brown University Bulletin
with dynamic department discovery.
"""

import requests
from bs4 import BeautifulSoup
import re
from src.scraper.schema import empty_course, normalize_course_code

BASE_URL = "https://bulletin.brown.edu"
DEPARTMENTS_INDEX = f"{BASE_URL}/departments-centers-programs-institutes/"

DEPT_START = "Africana Studies"
DEPT_END = "Visual Art"


def get_department_urls():
    """Scrape the departments index page to get all valid department URLs."""
    try:
        resp = requests.get(DEPARTMENTS_INDEX, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch departments index: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    department_urls = []

    start_collecting = False
    for a in soup.find_all("a", href=True):
        name = a.get_text(strip=True)
        href = a["href"]

        if name == DEPT_START:
            start_collecting = True

        if start_collecting and href.startswith("/") and not href.startswith("#"):
            full_url = BASE_URL + href
            department_urls.append(full_url)

        if name == DEPT_END:
            break

    return list(sorted(set(department_urls)))


def fetch_courses_bulletin(department_urls=None):
    """Scrape course code, title, description, and prerequisites from Bulletin.

    Args:
        department_urls: list of department URLs; if None, auto-fetch all

    Returns:
        List[dict]: courses in unified schema
    """
    if department_urls is None:
        department_urls = get_department_urls()
        print(f"Discovered {len(department_urls)} department URLs.")

    courses = []

    for url in department_urls:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed to fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        course_blocks = soup.find_all("div", class_="courseblock")
        for block in course_blocks:
            course = empty_course()

            title_tag = block.find("p", class_="courseblocktitle")
            if not title_tag:
                continue
            raw_code = title_tag.get("data-code", "").strip()
            course_code = normalize_course_code(raw_code)
            title_text = title_tag.get_text(" ", strip=True).replace(raw_code, "").strip(". ")
            course["course_code"] = course_code
            course["title"] = title_text

            desc_tag = block.find("p", class_="courseblockdesc")
            if desc_tag:
                full_description = desc_tag.get_text(" ", strip=True)
                course["description"] = full_description

                prereqs = []
                if "Prerequisite:" in full_description:
                    prereq_text = full_description.split("Prerequisite:")[1]
                    prereqs = [
                        normalize_course_code(c)
                        for c in re.findall(r"[A-Z]{2,6}\s?\d{4}", prereq_text)
                    ]

                linked_courses = [
                    normalize_course_code(a.get("data-code"))
                    for a in desc_tag.find_all("a", attrs={"data-code": True})
                ]
                if not prereqs:
                    prereqs = linked_courses

                course["prerequisites"] = ", ".join(prereqs)

            course["department"] = course_code.split()[0] if course_code else ""
            course["source"] = "Bulletin"

            courses.append(course)

        print(f"Parsed {len(course_blocks)} courses from {url}")

    print(f"Total Bulletin courses scraped: {len(courses)}")
    return courses


if __name__ == "__main__":
    bulletin_courses = fetch_courses_bulletin()
    for c in bulletin_courses[:10]:
        print(c)
