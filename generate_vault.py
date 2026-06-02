#!/usr/bin/env python3
"""Generate Obsidian vault documents from list_deceased.csv"""

import csv
import os
import re
import sys
from pathlib import Path

VAULT_DIR = Path(__file__).parent
CSV_PATH = VAULT_DIR / "list_deceased.csv"

MEMORIAL_RE = re.compile(r"/memorial/(\d+)/")


def parse_age(death_str: str) -> int | None:
    if not death_str or death_str == "unknown":
        return None
    m = re.search(r"aged\s+(\d+)", death_str)
    if m:
        return int(m.group(1))
    # handle "5 months" or "6 months"
    m = re.search(r"(\d+)\s+months?", death_str)
    if m:
        return 0
    return None


def age_tag(age: int) -> str:
    lo = (age // 10) * 10
    hi = lo + 10
    return f"age-{lo}-{hi}"


def extract_memorial_id(url: str) -> str | None:
    m = MEMORIAL_RE.search(url)
    return m.group(1) if m else None


def main():
    rows = []

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    def link_name(raw: str) -> str:
        return raw.strip().replace(" ", "_").title()

    def display_name(raw: str) -> str:
        return raw.strip().replace("_", " ").title()

    def filename_for_row(r: dict) -> str:
        name = r["Name"].strip()
        link = r["Link"].strip()
        mid = extract_memorial_id(link)
        base = link_name(name)
        return f"{base}_{mid}" if mid else base

    # Build filename mappings for wiki link resolution
    id_to_filename: dict[str, str] = {}
    url_to_filename: dict[str, str] = {}
    for r in rows:
        mid = extract_memorial_id(r["Link"])
        fname = filename_for_row(r)
        if mid:
            id_to_filename[mid] = fname
        url_to_filename[r["Link"].strip()] = fname

    def resolve_all_names(url_str: str) -> list[str]:
        """Resolve all names from a URL column value."""
        if not url_str:
            return []
        names = []
        for part in url_str.split(","):
            part = part.strip().rstrip(".")
            if not part:
                continue
            if part in url_to_filename:
                names.append(url_to_filename[part])
            else:
                mid = extract_memorial_id(part)
                if mid and mid in id_to_filename:
                    names.append(id_to_filename[mid])
                else:
                    # try to extract name from findagrave URL slug
                    slug_match = re.search(
                        r"/memorial/\d+/([^/]+)", part
                    )
                    if slug_match:
                        slug_name = (
                            slug_match.group(1)
                            .replace("-", "_")
                            .title()
                        )
                        slug_name = slug_name.rstrip(".")
                        names.append(slug_name)
        return names

    # Collect all unique people to write, keyed by memorial ID (not name)
    all_people: dict[str, dict] = {}
    for row in rows:
        mid = extract_memorial_id(row["Link"])
        key = mid or row["Name"].strip().upper()
        all_people[key] = row

    written = 0
    for key, row in all_people.items():
        name = row["Name"].strip()
        burial = row["Burial"].strip() if row["Burial"] else ""
        link = row["Link"].strip()
        death_str = row["Death"].strip() if row["Death"] else ""

        age = parse_age(death_str)

        tags = []
        if burial:
            ctag = burial.replace(" ", "_").replace("-", "_").lower()
            tags.append(f"cemetery/{ctag}")
        if age is not None:
            tags.append(age_tag(age))

        # resolve connections
        parent_names = resolve_all_names(row.get("Parents", ""))
        sibling_names = resolve_all_names(row.get("Siblings", ""))
        spouse_names = resolve_all_names(row.get("Spouse", ""))
        child_names = resolve_all_names(row.get("Children", ""))

        disp_name = display_name(name)
        file_name = filename_for_row(row)

        # Build the document
        lines = []
        lines.append("---")
        if tags:
            lines.append(f"tags: [{', '.join(tags)}]")
        if parent_names:
            lines.append(f"parents: [{', '.join(parent_names)}]")
        if sibling_names:
            lines.append(f"siblings: [{', '.join(sibling_names)}]")
        if spouse_names:
            lines.append(f"spouse: [{', '.join(spouse_names)}]")
        if child_names:
            lines.append(f"children: [{', '.join(child_names)}]")
        lines.append("---")
        lines.append("")

        # Title
        lines.append(f"# {disp_name}")
        lines.append("")

        # External link
        lines.append(f"[FindAGrave]({link})")
        lines.append("")

        # Connections as human-readable lists
        if parent_names:
            lines.append("## Parents")
            for p in parent_names:
                lines.append(f"- [[{p}]]")
        if sibling_names:
            lines.append("## Siblings")
            for s in sibling_names:
                lines.append(f"- [[{s}]]")
        if spouse_names:
            lines.append("## Spouse")
            for s in spouse_names:
                lines.append(f"- [[{s}]]")
        if child_names:
            lines.append("## Children")
            for c in child_names:
                lines.append(f"- [[{c}]]")

        content = "\n".join(lines)

        fname = re.sub(r"[^\w\-]", "", file_name) + ".md"
        fpath = VAULT_DIR / fname
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        written += 1

    print(f"Done. Generated {written} markdown files in {VAULT_DIR}")


if __name__ == "__main__":
    main()
