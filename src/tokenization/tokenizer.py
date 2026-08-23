import tiktoken


# Tokenizer configuration
TOKENIZER_NAME = "cl100k_base"


def get_tokenizer():
    """
    Return the tokenizer used by the application.

    cl100k_base is a commonly used tokenizer
    for OpenAI models and is suitable for
    learning tokenization concepts. 
    """
    return tiktoken.get_encoding(TOKENIZER_NAME)


def encode_text(text: str) -> list[int]:
    """
    Convert text into token IDs.

    Args:
        text: Input text.

    Returns:
        A list of integer token IDs.
    """
    tokenizer = get_tokenizer()
    return tokenizer.encode(text)


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in the given text.

    Args:
        text: Input text.

    Returns:
        Number of tokens.
    """
    return len(encode_text(text))


def validate_chunk_tokens(
    text: str,
    max_tokens: int,
) -> dict:
    """
    Validate whether a chunk is within the allowed
    token limit.

    Args:
        text: Chunk text.
        max_tokens: Maximum allowed token count.

    Returns:
        Dictionary containing token count,
        maximum allowed tokens, and validation result.
    """
    token_count = count_tokens(text)

    return {
        "token_count": token_count,
        "max_tokens": max_tokens,
        "valid": token_count <= max_tokens,
    }   