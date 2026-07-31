PROJECT_PASSWORD_MAX = 512
WEAK_PASSWORD_LENGTH = 12


def is_weak_project_password(password):
    return len(password or "") < WEAK_PASSWORD_LENGTH
