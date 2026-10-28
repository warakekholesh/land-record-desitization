"""
Algorithm 3: Rule-Based Anomaly Detection Engine
Evaluates extracted land records for consistency, formatting integrity,
and cross-record conflicts in the database.

Rules:
1. Mandatory fields presence check (Owner, Survey No, Area, Village)
2. Area positivity constraint (Area > 0)
3. Survey/Gat number syntax validation (e.g. '101/1', '125/2')
4. String similarity comparison for OCR typos (Levenshtein distance)
5. Cross-record collision & duplicate detection:
   - Same Survey Number with different owners
   - Same Survey Number with mismatched area measurements
6. Severity classification:
   - 🟢 Consistent (passes all checks)
   - 🟡 Requires Verification (missing secondary fields / spelling review)
   - 🔴 Anomaly Detected (structural contradiction, conflict, or illegal value)
"""

import re
import json


def levenshtein_similarity(s1, s2):
    """
    Computes normalized Levenshtein similarity between two strings (0.0 to 1.0).
    Pure Python implementation - no external C dependencies required.
    """
    if not s1 or not s2:
        return 0.0
    s1 = s1.lower().strip()
    s2 = s2.lower().strip()
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    # Initialize DP matrix
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost  # substitution
            )

    distance = dp[len1][len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len)


def is_valid_survey_number(survey_no):
    """
    Validates format: numbers or numbers with sub-divisions (e.g. 101, 101/1, 125/2, 45-B).
    """
    if not survey_no or not isinstance(survey_no, str):
        return False
    clean = survey_no.strip()
    # Typical Indian land survey formats: e.g. 101, 101/1, 125/2A, 54-1
    return bool(re.match(r'^[0-9]{1,6}(?:[/\-][0-9A-Za-z]+)?$', clean))


def validate_land_record(record_data, existing_records=None):
    """
    Validates a land record dictionary or model instance against rules and existing database records.

    record_data: dict with keys (survey_number, owner_name, area, village, taluka, district)
    existing_records: iterable of existing LandRecord instances to check conflicts against

    Returns:
      status: 'consistent' | 'warning' | 'anomaly'
      reasons: list of explanation strings
      conflicts: list of conflicting record IDs/summaries
    """
    anomalies = []
    warnings = []
    conflicts = []

    survey_no = str(record_data.get('survey_number') or '').strip()
    owner_name = str(record_data.get('owner_name') or '').strip()
    area = record_data.get('area')
    village = str(record_data.get('village') or '').strip()
    record_id = record_data.get('id')

    # 1. Mandatory Field Checks
    missing_fields = []
    if not survey_no:
        missing_fields.append("Survey/Gat Number")
    if not owner_name:
        missing_fields.append("Owner Name")
    if area is None:
        missing_fields.append("Land Area")
    if not village:
        missing_fields.append("Village")

    if missing_fields:
        anomalies.append(f"Missing mandatory land record information: {', '.join(missing_fields)}.")

    # 2. Area Validity Check
    if area is not None:
        try:
            area_float = float(area)
            if area_float <= 0:
                anomalies.append(f"Invalid Area ({area_float}): Area must be strictly greater than 0.")
            elif area_float > 5000:
                warnings.append(f"Unusually large parcel area ({area_float} ha) requires manual verification.")
        except (ValueError, TypeError):
            anomalies.append(f"Invalid area value format: '{area}'.")

    # 3. Survey Number Format Validation
    if survey_no and not is_valid_survey_number(survey_no):
        anomalies.append(f"Invalid Survey Number format '{survey_no}'. Expected standard format like '101/1' or '125/2'.")

    # 4. Database Conflict and Duplicate Detection
    if survey_no and existing_records:
        for other in existing_records:
            # Skip checking against itself
            if record_id and other.id == record_id:
                continue

            other_survey = str(other.survey_number or '').strip()
            if not other_survey or other_survey.lower() != survey_no.lower():
                continue

            # Optional village match check (if village specified in both)
            other_village = str(other.village or '').strip()
            if village and other_village and village.lower() != other_village.lower():
                # Different village, might be different jurisdiction
                continue

            other_owner = str(other.owner_name or '').strip()
            other_area = other.area

            # Compare owners with Levenshtein string similarity
            has_owner_conflict = False
            has_area_conflict = False

            if owner_name and other_owner:
                sim = levenshtein_similarity(owner_name, other_owner)
                if sim < 0.75:
                    # Clear conflict: completely different owners on the same survey number
                    has_owner_conflict = True
                    conflicts.append({
                        'record_id': other.id,
                        'survey_number': other_survey,
                        'other_owner': other_owner,
                        'current_owner': owner_name,
                        'type': 'owner_mismatch'
                    })
                elif sim < 1.0:
                    # Minor OCR / spelling variation
                    warnings.append(
                        f"Potential OCR spelling variation on Survey {survey_no}: "
                        f"'{owner_name}' vs existing record #{other.id} '{other_owner}' (Similarity: {int(sim*100)}%)."
                    )

            # Compare area values
            if area is not None and other_area is not None:
                diff = abs(float(area) - float(other_area))
                if diff > 0.05:  # Tolerance threshold for rounding
                    has_area_conflict = True
                    conflicts.append({
                        'record_id': other.id,
                        'survey_number': other_survey,
                        'other_area': other_area,
                        'current_area': area,
                        'type': 'area_mismatch'
                    })

            # Formulate clear, explicit anomaly statements
            if has_owner_conflict and has_area_conflict:
                anomalies.append(
                    f"Same Survey Number ({survey_no}) has conflicting owner ('{other_owner}' vs '{owner_name}') "
                    f"and conflicting area ({other_area} ha vs {area} ha) with Record #{other.id}."
                )
            elif has_owner_conflict:
                anomalies.append(
                    f"Same Survey Number ({survey_no}) is associated with conflicting owner: "
                    f"Existing Record #{other.id} belongs to '{other_owner}', while this record lists '{owner_name}'."
                )
            elif has_area_conflict:
                anomalies.append(
                    f"Area mismatch on Survey Number {survey_no}: "
                    f"Existing Record #{other.id} has {other_area} ha, while this record lists {area} ha."
                )
            elif not has_owner_conflict and not has_area_conflict:
                warnings.append(
                    f"Duplicate entry detected: Survey {survey_no} with identical owner and area is already registered as Record #{other.id}."
                )

    # 5. Determine Overall Status
    if anomalies:
        status = 'anomaly'
        all_reasons = anomalies + warnings
    elif warnings:
        status = 'warning'
        all_reasons = warnings
    else:
        status = 'consistent'
        all_reasons = ["Record passed all structural, mathematical, and database consistency validations."]

    return status, all_reasons, conflicts
