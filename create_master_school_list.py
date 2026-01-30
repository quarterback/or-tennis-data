#!/usr/bin/env python3
"""
Create master_school_list.csv by mapping schools to their Classification and League/District.
"""

import csv

CLASSIFICATION_MAP = {
    "6A": {
        "PIL (6A-1)": ["Lincoln", "Grant", "Franklin", "Cleveland", "Wells", "Roosevelt", "McDaniel", "Benson", "Jefferson"],
        "Metro (6A-2)": ["Jesuit", "Sunset", "Westview", "Mountainside", "Beaverton", "Southridge", "Aloha"],
        "Pacific (6A-3)": ["Century", "Forest Grove", "Glencoe", "Liberty", "McMinnville", "Newberg", "Sherwood"],
        "Mt. Hood (6A-4)": ["Barlow", "Central Catholic", "Clackamas", "David Douglas", "Gresham", "Nelson", "Reynolds", "Sandy"],
        "Three Rivers (6A-5)": ["Lake Oswego", "Lakeridge", "Tigard", "Tualatin", "West Linn", "Oregon City", "St. Mary's Academy"],
        "Central Valley (6A-6)": ["McNary", "North Salem", "South Salem", "Sprague", "West Salem"],
        "Southwest (6A-7)": ["Grants Pass", "North Medford", "South Medford", "Roseburg", "Sheldon", "South Eugene", "Willamette"],
    },
    "5A": {
        "NW Oregon (5A-1)": ["Canby", "Centennial", "Hillsboro", "Hood River Valley", "La Salle Prep", "Milwaukie", "Parkrose", "Putnam", "Wilsonville"],
        "Midwestern (5A-2)": ["Ashland", "Churchill", "North Eugene", "Springfield", "Thurston"],
        "Mid-Willamette (5A-3)": ["Central", "Corvallis", "Crescent Valley", "Dallas", "Lebanon", "McKay", "Silverton", "South Albany", "West Albany", "Woodburn"],
        "Intermountain (5A-4)": ["Bend", "Caldera", "Mountain View", "Redmond", "Ridgeview", "Summit", "Crook County"],
    },
    "4A/3A/2A": {
        "Special District 1": ["Blanchet", "Catlin Gabel", "OES", "Riverdale", "Scappoose", "St. Helens", "Tillamook", "Valley Catholic", "Westside Christian"],
        "Special District 2": ["Cascade", "Estacada", "Junction City", "Marist Catholic", "Molalla", "North Marion", "Philomath", "Stayton"],
        "Special District 3": ["Cascade Christian", "Henley", "Hidden Valley", "Klamath Union", "Marshfield", "Mazama", "North Bend", "Phoenix", "St. Mary's (Medford)"],
        "Special District 4": ["Madras", "Sisters", "The Dalles", "Riverside", "Umatilla", "Arlington", "Condon", "Ione"],
        "Special District 5": ["Baker", "La Grande", "McLoughlin", "Nyssa", "Ontario", "Pendleton", "Vale"],
    }
}


def normalize_name(name):
    """Normalize school name for matching."""
    name = name.strip().lower()
    name = name.replace(" high school", "")
    name = name.replace(" senior high", "")
    name = name.replace(" high", "")
    name = name.replace(" school", "")
    name = name.replace(".", "")
    name = name.replace("'", "")
    return name.strip()


def find_classification_and_league(school_name):
    """
    Find the classification and league for a school using partial matching.
    Returns (classification, league) or ("Other", "Other") if not found.
    """
    # Special case: "Riverside (West Linn - Wilsonville)" is not in the classification list
    if "west linn" in school_name.lower() and "wilsonville" in school_name.lower() and "riverside" in school_name.lower():
        return "Other", "Other"

    normalized_school = normalize_name(school_name)

    # Build a list of all possible matches with their classifications
    # Sort by specificity (longer matches first) to avoid false positives
    matches = []

    for classification, leagues in CLASSIFICATION_MAP.items():
        for league, schools in leagues.items():
            for key_school in schools:
                normalized_key = normalize_name(key_school)
                matches.append((normalized_key, classification, league, len(normalized_key)))

    # Sort by length descending to match longer/more specific names first
    matches.sort(key=lambda x: x[3], reverse=True)

    for normalized_key, classification, league, _ in matches:
        # Exact match
        if normalized_school == normalized_key:
            return classification, league

        # Multi-word exact matches (e.g., "valley catholic", "la grande")
        # But make sure the school name starts with the key or the key is the main part
        if " " in normalized_key and normalized_key in normalized_school:
            # Don't match "West Linn" to "Riverside (West Linn - Wilsonville)"
            # Only match if it's the primary school name, not just mentioned in parentheses
            if normalized_school.startswith(normalized_key) or "(" not in school_name:
                return classification, league

        # Handle specific school name patterns

        # "Sam Barlow" should match "Barlow"
        if normalized_key == "barlow" and "barlow" in normalized_school:
            return classification, league

        # "Ida B. Wells-Barnett" should match "Wells"
        if normalized_key == "wells" and "wells" in normalized_school and "barnett" in normalized_school:
            return classification, league

        # "Oregon Episcopal School" should match "OES"
        if normalized_key == "oes" and ("oregon episcopal" in normalized_school or normalized_school == "oes"):
            return classification, league

        # "Central (Independence)" should match "Central" only in Mid-Willamette context
        if normalized_key == "central" and "independence" in school_name.lower():
            return classification, league

        # "Ione-Heppner" should match "Ione"
        if normalized_key == "ione" and "ione" in normalized_school and "heppner" in normalized_school:
            return classification, league

        # "St Mary's of Medford" should match "St. Mary's (Medford)"
        if "st mary" in normalized_key and "medford" in normalized_key and "st mary" in normalized_school and "medford" in normalized_school:
            return classification, league

        # "Riverside (Boardman)" should match "Riverside" in Special District 4
        if normalized_key == "riverside" and "boardman" in normalized_school:
            return classification, league

        # Single-word matches (but avoid false positives like "Bend" matching "North Bend")
        if " " not in normalized_key:
            # Avoid matching "Bend" to "North Bend", "Central" to "Central Catholic", etc.
            words = normalized_school.split()
            if normalized_key in words:
                return classification, league

            # Also check if it's the main part of the school name
            # For schools like "Creswell High School" should match "Creswell"
            if normalized_school.startswith(normalized_key + " ") or normalized_school == normalized_key:
                return classification, league

    return "Other", "Other"


def create_master_school_list(input_file, output_file):
    """Create master school list with classification and league mappings."""
    schools = []
    unmatched = []

    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            school_id = row["id"]
            school_name = row["name"]

            classification, league = find_classification_and_league(school_name)

            schools.append({
                "School_ID": school_id,
                "School_Name": school_name,
                "Classification": classification,
                "League_District": league
            })

            if classification == "Other":
                unmatched.append(school_name)

    # Write output
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["School_ID", "School_Name", "Classification", "League_District"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(schools)

    print(f"Created {output_file}")
    print(f"Total schools: {len(schools)}")
    print(f"Matched: {len(schools) - len(unmatched)}")
    print(f"Unmatched: {len(unmatched)}")

    if unmatched:
        print("\nUnmatched schools (labeled as 'Other'):")
        for school in unmatched:
            print(f"  - {school}")


if __name__ == "__main__":
    create_master_school_list("oregon_schools.csv", "master_school_list.csv")
