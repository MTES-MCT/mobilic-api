import re

from app import db
from app.models import NafCode

SECTION_RE = re.compile(r"SECTION (.+)")

LEVELS_RE = [
    re.compile(r"^SECTION (.+)$"),
    re.compile(r"^(\d\d)$"),
    re.compile(r"^(\d\d\.\d)$"),
    re.compile(r"^(\d\d\.\d\d)$"),
    re.compile(r"^(\d\d\.\d\d[A-Z])$"),
]


def import_naf_codes(file_path="data/naf_rev2_codes.tsv"):
    with open(file_path, "r") as f:
        line_tuples = [l.split("\t") for l in f.readlines()[1:]]

    naf_codes = []

    # Naf codes are structured in 5 levels, from the coarsest (section) to the finest (a NAF code)
    # This structure is flattened in a depth-first fashion in the file
    current_level_values = [None] * len(
        LEVELS_RE
    )  # Holds the information of where we're at in the structure
    current_level = None

    for line in line_tuples:
        code = line[1]
        label = line[2]
        if not code:  # Empty line
            continue

        # We expect the line to be one level below the level of the previous line (one depth further in the tree), unless if we are already at the bottom level in which the case the line could be of any level
        expected_levels = range(0, len(LEVELS_RE))
        if current_level is None:
            expected_levels = [0]
        elif current_level < len(LEVELS_RE) - 1:
            expected_levels = [current_level + 1]

        line_is_of_expected_level = False
        for level in expected_levels:
            match = LEVELS_RE[level].match(code)
            if match:
                actual_code = match.groups()[0]
                line_is_of_expected_level = True
                current_level = level
                current_level_values[level] = {
                    "code": actual_code,
                    "label": label,
                }
                if level == len(LEVELS_RE) - 1:
                    naf_codes.append(
                        NafCode(
                            section_code=current_level_values[0]["code"],
                            section_label=current_level_values[0]["label"],
                            level1_code=current_level_values[1]["code"],
                            level1_label=current_level_values[1]["label"],
                            level2_code=current_level_values[2]["code"],
                            level2_label=current_level_values[2]["label"],
                            level3_code=current_level_values[3]["code"],
                            level3_label=current_level_values[3]["label"],
                            code=current_level_values[4]["code"],
                            label=current_level_values[4]["label"],
                        )
                    )
                break

        if not line_is_of_expected_level:
            raise ValueError(
                f"Expected a code corresponding to levels {expected_levels}, got instead {code}"
            )

    NafCode.query.delete()
    db.session.bulk_save_objects(naf_codes)
    db.session.commit()


if __name__ == "__main__":
    import_naf_codes()
