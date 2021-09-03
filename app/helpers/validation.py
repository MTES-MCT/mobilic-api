import re

VALID_EMAIL_RE = re.compile(r"^[a-z0-9._+-]+[@][a-z0-9-]+(\.[a-z0-9-]+)+$")


def validate_clean_email_string(string):
    return VALID_EMAIL_RE.match(string) is not None


def clean_email_string(string):
    return string.lower().strip()


# For DB models
def validate_email_field_in_db(self, key, value):
    clean_value = clean_email_string(value)
    if not validate_clean_email_string(clean_value):
        raise AssertionError("Invalid email address")
    return clean_value
