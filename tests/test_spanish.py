"""Tests for Spanish flashcard helper functions."""

import pytest
from anki_mcp.spanish import (
    format_vocab_card,
    format_verb_card,
    format_sentence_cloze,
    suggest_tags,
    get_verb_type,
    is_reflexive_verb,
)


class TestFormatVocabCard:
    def test_basic_vocab_card(self):
        result = format_vocab_card("madrugada", "dawn/early morning")
        assert result["front"] == "madrugada"
        assert result["back"] == "dawn/early morning"

    def test_vocab_card_with_example(self):
        result = format_vocab_card(
            "madrugada",
            "dawn/early morning",
            example="Me levanté de madrugada"
        )
        assert "dawn/early morning" in result["back"]
        assert "Example: Me levanté de madrugada" in result["back"]

    def test_vocab_card_with_masculine_gender(self):
        result = format_vocab_card("gato", "cat", gender="m")
        assert "el - masculine" in result["back"]

    def test_vocab_card_with_feminine_gender(self):
        result = format_vocab_card("casa", "house", gender="la")
        assert "la - feminine" in result["back"]


class TestFormatVerbCard:
    def test_basic_verb_card(self):
        result = format_verb_card("hablar", "to speak")
        assert result["front"] == "hablar"
        assert "to speak" in result["back"]
        assert "[AR verb]" in result["back"]

    def test_verb_card_with_conjugation_notes(self):
        result = format_verb_card(
            "poder",
            "to be able to",
            conjugation_notes="stem-changing o→ue"
        )
        assert "stem-changing o→ue" in result["back"]
        assert "[ER verb]" in result["back"]

    def test_verb_card_with_example(self):
        result = format_verb_card(
            "comer",
            "to eat",
            example="Como una manzana"
        )
        assert "Example: Como una manzana" in result["back"]
        assert "[ER verb]" in result["back"]

    def test_ir_verb_identification(self):
        result = format_verb_card("vivir", "to live")
        assert "[IR verb]" in result["back"]


class TestFormatSentenceCloze:
    def test_basic_cloze(self):
        result = format_sentence_cloze(
            "Tengo que ir al supermercado",
            "Tengo que"
        )
        assert result == "{{c1::Tengo que}} ir al supermercado"

    def test_cloze_with_single_word(self):
        result = format_sentence_cloze(
            "Voy a la tienda",
            "tienda"
        )
        assert result == "Voy a la {{c1::tienda}}"

    def test_cloze_first_occurrence_only(self):
        result = format_sentence_cloze(
            "La casa es una casa grande",
            "casa"
        )
        assert result == "La {{c1::casa}} es una casa grande"


class TestSuggestTags:
    def test_verb_tags(self):
        tags = suggest_tags("hablar", pos="verb")
        assert "verb" in tags
        assert "verb-ar" in tags

    def test_er_verb_tags(self):
        tags = suggest_tags("comer", pos="verb")
        assert "verb" in tags
        assert "verb-er" in tags

    def test_ir_verb_tags(self):
        tags = suggest_tags("vivir", pos="verb")
        assert "verb" in tags
        assert "verb-ir" in tags

    def test_reflexive_verb_tags(self):
        tags = suggest_tags("levantarse", pos="verb")
        assert "verb" in tags
        assert "reflexive" in tags

    def test_noun_tags(self):
        tags = suggest_tags("casa", pos="noun")
        assert "noun" in tags

    def test_additional_tags(self):
        tags = suggest_tags(
            "hablar",
            pos="verb",
            additional_tags=["freq-high", "source-podcast"]
        )
        assert "verb" in tags
        assert "freq-high" in tags
        assert "source-podcast" in tags


class TestGetVerbType:
    def test_ar_verb(self):
        assert get_verb_type("hablar") == "ar"

    def test_er_verb(self):
        assert get_verb_type("comer") == "er"

    def test_ir_verb(self):
        assert get_verb_type("vivir") == "ir"

    def test_reflexive_ar_verb(self):
        assert get_verb_type("levantarse") == "ar"

    def test_reflexive_er_verb(self):
        assert get_verb_type("ponerse") == "er"

    def test_reflexive_ir_verb(self):
        assert get_verb_type("vestirse") == "ir"

    def test_non_verb(self):
        assert get_verb_type("casa") is None


class TestIsReflexiveVerb:
    def test_reflexive_verb(self):
        assert is_reflexive_verb("levantarse") is True
        assert is_reflexive_verb("ponerse") is True
        assert is_reflexive_verb("vestirse") is True

    def test_non_reflexive_verb(self):
        assert is_reflexive_verb("hablar") is False
        assert is_reflexive_verb("comer") is False
        assert is_reflexive_verb("vivir") is False

    def test_case_insensitive(self):
        assert is_reflexive_verb("Levantarse") is True
        assert is_reflexive_verb("PONERSE") is True
