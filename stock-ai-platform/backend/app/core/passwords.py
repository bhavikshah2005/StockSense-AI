def validate_password_strength(password: str) -> None:
    """Reject passwords that are too short, too long, or missing a letter and a digit."""
    if len(password) < 10 or len(password) > 128:
        raise ValueError("Password must be 10 to 128 characters")
    if not any(character.isalpha() for character in password) or not any(
        character.isdigit() for character in password
    ):
        raise ValueError("Password must include a letter and a number")
