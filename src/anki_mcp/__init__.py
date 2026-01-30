"""Anki MCP Server - Connect Claude Desktop to Anki via AnkiConnect."""

__version__ = "0.1.0"

from .anki_client import AnkiClient, AnkiConnectError
from .spanish import (
    format_vocab_card,
    format_verb_card,
    format_sentence_cloze,
    suggest_tags,
    get_verb_type,
    is_reflexive_verb,
)

__all__ = [
    "AnkiClient",
    "AnkiConnectError",
    "format_vocab_card",
    "format_verb_card",
    "format_sentence_cloze",
    "suggest_tags",
    "get_verb_type",
    "is_reflexive_verb",
]
