"""
Module: src/scraper/merged.py
Purpose: Merge CAB and Bulletin courses into a unified JSON with true field-level merge.
"""

import json
from src.scraper.schema import empty_course, normalize_course_code
from src.scraper.courses import fetch_courses_cab
from src.scraper.bulletin import fetch_courses_bulletin

OUTPUT_FILE = "data/courses.json"


def merge_courses(cab_courses=None, bulletin_courses=None):
    """Merge CAB and Bulletin course lists with field-level merge.

    When the same course_code exists in both sources:
    - CAB provides: instructor, meeting_times
    - Bulletin provides: description, prerequisites
    - Shared fields (title, department) prefer non-empty values
    - source is set to "Both"

    Courses unique to either source are included with their original source tag.

    Args:
        cab_courses: courses from CAB
        bulletin_courses: courses from Bulletin

    Returns:
        List[dict]: merged courses from both sources
    """
    if cab_courses is None:
        cab_courses = fetch_courses_cab()
    if bulletin_courses is None:
        bulletin_courses = fetch_courses_bulletin()

    # Index by normalized course_code
    cab_index = {}
    for c in cab_courses:
        code = normalize_course_code(c.get("course_code", ""))
        if code:
            cab_index[code] = c

    bulletin_index = {}
    for c in bulletin_courses:
        code = normalize_course_code(c.get("course_code", ""))
        if code:
            bulletin_index[code] = c

    merged = []
    all_codes = set(cab_index.keys()) | set(bulletin_index.keys())

    for code in sorted(all_codes):
        cab = cab_index.get(code)
        bul = bulletin_index.get(code)

        if cab and bul:
            course = empty_course()
            course["course_code"] = code
            course["title"] = cab.get("title") or bul.get("title") or ""
            course["department"] = cab.get("department") or bul.get("department") or ""
            course["instructor"] = cab.get("instructor") or bul.get("instructor") or ""
            course["meeting_times"] = cab.get("meeting_times") or bul.get("meeting_times") or ""
            course["description"] = bul.get("description") or cab.get("description") or ""
            course["prerequisites"] = bul.get("prerequisites") or cab.get("prerequisites") or ""
            course["source"] = "Both"
            merged.append(course)
        elif cab:
            cab["course_code"] = code
            merged.append(cab)
        else:
            bul["course_code"] = code
            merged.append(bul)

    both = sum(1 for c in merged if c["source"] == "Both")
    cab_only = sum(1 for c in merged if c["source"] == "CAB")
    bul_only = sum(1 for c in merged if c["source"] == "Bulletin")
    print(f"Merged: {len(merged)} total (Both: {both}, CAB-only: {cab_only}, Bulletin-only: {bul_only})")
    return merged


def save_courses_json(courses, filename=OUTPUT_FILE):
    """Save merged courses to JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(courses)} courses to {filename}")


if __name__ == "__main__":
    merged_courses = merge_courses()
    save_courses_json(merged_courses)
    for c in merged_courses[:5]:
        print(c)
