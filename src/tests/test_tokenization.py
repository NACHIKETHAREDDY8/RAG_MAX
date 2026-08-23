from src.tokenization.tokenizer import (
    count_tokens,
    encode_text,
    validate_chunk_tokens,
)


def main():
    text = "Artificial intelligence is changing software development."

    character_count = len(text)
    word_count = len(text.split())
    token_count = count_tokens(text)

    print("=" * 60)
    print("TOKENIZATION COMPARISON")
    print("=" * 60)

    print("\nText:")
    print(text)

    print("\nCharacter count:")
    print(character_count)

    print("\nWord count:")
    print(word_count)

    print("\nToken count:")
    print(token_count)

    print("\nToken IDs:")
    print(encode_text(text))

    print("\nToken validation:")
    print(validate_chunk_tokens(text, 500))


if __name__ == "__main__":
    main()