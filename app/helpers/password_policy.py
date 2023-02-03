PASSWORD_POLICY_MIN_LENGTH = 9


def is_valid_password(password):
    if len(password) < PASSWORD_POLICY_MIN_LENGTH:
        return False
    if not any(char.isdigit() for char in password):
        return False
    if password.isalnum():
        return False
    return True
