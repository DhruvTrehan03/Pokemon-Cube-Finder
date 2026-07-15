import re
import unicodedata


_SPACE_RE = re.compile(r"\s+")
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
    return normalise_text(value)


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
