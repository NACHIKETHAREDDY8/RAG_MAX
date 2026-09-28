import re


def clean_text(text: str) -> str:
    # Windows (\r\n) and old Mac (\r) line endings become \n.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    text = text.replace("\xa0", " ")

    # Private Use Area glyphs (e.g. Word's bullet) carry no meaning
    # outside their original font, so drop them before embedding.
    text = re.sub(r"[-]", "", text)

    # Control characters other than tab and newline (form feeds, NULs from
    # broken extractions) are invisible noise.
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r" +\n", "\n", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
