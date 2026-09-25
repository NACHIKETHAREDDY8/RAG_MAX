from src.tokenization.tokenizer import (
    count_tokens,
    encode_text,
    validate_chunk_tokens,
)


TEXT = "Artificial intelligence is changing software development."


def test_count_tokens_matches_encoding():
    assert count_tokens(TEXT) == len(encode_text(TEXT)) > 0


def test_validate_chunk_tokens():
    token_count = count_tokens(TEXT)

    assert validate_chunk_tokens(TEXT, token_count)["valid"] is True
    assert validate_chunk_tokens(TEXT, token_count - 1)["valid"] is False
