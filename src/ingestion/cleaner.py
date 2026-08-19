import re


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()