import re


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")

    # Private Use Area glyphs (e.g. Word's bullet) carry no meaning
    # outside their original font, so drop them before embedding.
    text = re.sub(r"[-]", "", text)

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()