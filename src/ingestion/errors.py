"""Errors raised while turning a file into Documents.

Each one means "this file cannot be ingested", so callers can skip the file
and carry on. They subclass ValueError because they all describe bad input.
"""


class IngestionError(ValueError):
    """A file could not be ingested."""


class FileValidationError(IngestionError):
    """The file is missing, empty, too large, or its content does not match its type."""


class UnsupportedFileTypeError(IngestionError):
    """No parser handles this kind of file."""


class ParserError(IngestionError):
    """A parser failed to read a file of a supported type."""


class MetadataError(IngestionError):
    """The .meta.json file next to a document is invalid."""
