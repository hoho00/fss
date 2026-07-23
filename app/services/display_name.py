import re


TRAILING_PAREN_GROUPS_PATTERN = re.compile(
    r"(?:\s*[\(（][^\(\)（）]*[\)）])+\s*$"
)
# Backward-compatible import used by the existing Hold'em bot service.
COMPANY_SUFFIX_PATTERN = TRAILING_PAREN_GROUPS_PATTERN


def normalize_display_name(display_name: str | None) -> str:
    """Remove only consecutive parenthesized groups at the end of a name."""
    original_name = display_name or "알 수 없음"
    cleaned_name = TRAILING_PAREN_GROUPS_PATTERN.sub("", original_name).strip()
    cleaned_name = re.sub(r"\s+", " ", cleaned_name)
    return cleaned_name or original_name


def clean_display_name(display_name: str | None) -> str:
    """Apply the display-name cleanup historically used by Hold'em."""
    return normalize_display_name(display_name)
