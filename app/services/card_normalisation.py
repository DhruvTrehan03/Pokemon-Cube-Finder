import re
import unicodedata


_SPACE_RE = re.compile(r"\s+")
_SET_PREFIX_RE = re.compile(r"^\s*([A-Za-z0-9]+)\s*:")
_PRINTING_SUFFIX_RE = re.compile(
    r"\s+-\s+(?:reverse holofoil|holofoil|normal|foil|near mint|lightly played|"
    r"moderately played|heavily played|damaged)\s*$",
    re.IGNORECASE,
)
_COLLECTOR_SUFFIX_RE = re.compile(r"\s+-\s+#?\s*[A-Za-z0-9]+(?:/[A-Za-z0-9]+)?\s*$")
_CUBEKOga_ID_RE = re.compile(r"^\s*(?P<set>[A-Za-z]{1,8}\d{0,4})-(?P<number>[A-Za-z0-9]+)\s*$")
_PUNCT_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


def normalise_text(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", value).translate(_PUNCT_TRANSLATION)
    text = _SPACE_RE.sub(" ", text.strip())
    return text.casefold()


def normalise_card_name(value: str | None) -> str:
    return normalise_text(clean_display_card_name(value))


def normalise_set_name(value: str | None) -> str | None:
    normalised = normalise_text(value)
    return normalised or None


def normalise_set_code(value: str | None) -> str | None:
    if value is None:
        return None
    text = _SPACE_RE.sub("", unicodedata.normalize("NFKC", value).strip())
    return text.upper() or None


def normalise_collector_number(value: str | None) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", value).translate(_PUNCT_TRANSLATION)
    text = _SPACE_RE.sub("", text.strip())
    text = text.lstrip("#")
    return text.upper() or None


def collector_number_key(value: str | None) -> str | None:
    normalised = normalise_collector_number(value)
    if not normalised:
        return None
    return normalised.split("/", 1)[0]


def collector_set_total(value: str | None) -> str | None:
    normalised = normalise_collector_number(value)
    if not normalised or "/" not in normalised:
        return None
    total = normalised.split("/", 1)[1]
    return total or None


def collector_numbers_match(left: str | None, right: str | None) -> bool:
    left_key = collector_number_key(left)
    right_key = collector_number_key(right)
    return bool(left_key and right_key and left_key == right_key)


def collector_number_and_total_match(
    owned_collector_number: str | None,
    cube_collector_number: str | None,
    cube_set_total: str | None = None,
) -> bool:
    if not collector_numbers_match(owned_collector_number, cube_collector_number):
        return False
    if not cube_set_total:
        return True
    return collector_set_total(owned_collector_number) == normalise_collector_number(cube_set_total)


def derive_set_code(value: str | None) -> str | None:
    if not value:
        return None
    match = _SET_PREFIX_RE.match(value)
    if match:
        return normalise_set_code(match.group(1))
    return None


def clean_display_card_name(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", value).translate(_PUNCT_TRANSLATION)
    text = _SPACE_RE.sub(" ", text.strip())
    text = _PRINTING_SUFFIX_RE.sub("", text)
    text = _COLLECTOR_SUFFIX_RE.sub("", text)
    return text.strip()


def parse_card_identifier(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    match = _CUBEKOga_ID_RE.match(value)
    if not match:
        return None, None
    return normalise_set_code(match.group("set")), normalise_collector_number(match.group("number"))


def card_signature(
    name: str, set_code: str | None = None, collector_number: str | None = None
) -> str:
    return "|".join(
        [
            normalise_card_name(name),
            normalise_set_code(set_code) or "",
            normalise_collector_number(collector_number) or "",
        ]
    )
