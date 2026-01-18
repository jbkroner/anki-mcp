"""Spanish-specific flashcard generation helpers."""

import re
from typing import Optional


def format_vocab_card(
    spanish: str,
    english: str,
    example: Optional[str] = None,
    gender: Optional[str] = None
) -> dict:
    """
    Format a Spanish vocabulary card with consistent structure.

    Args:
        spanish: Spanish word/phrase
        english: English translation
        example: Optional example sentence in Spanish
        gender: Optional gender indicator ('m', 'f', 'el', 'la')

    Returns:
        Dictionary with 'front' and 'back' fields
    """
    front = spanish.strip()

    # Build the back of the card
    back_parts = [english.strip()]

    # Add gender indicator for nouns
    if gender:
        gender_lower = gender.lower()
        if gender_lower in ['m', 'el']:
            back_parts.append("(el - masculine)")
        elif gender_lower in ['f', 'la']:
            back_parts.append("(la - feminine)")

    # Add example sentence if provided
    if example:
        back_parts.append(f"\nExample: {example.strip()}")

    back = "\n".join(back_parts)

    return {
        "front": front,
        "back": back
    }


def format_verb_card(
    infinitive: str,
    english: str,
    conjugation_notes: Optional[str] = None,
    example: Optional[str] = None
) -> dict:
    """
    Format a Spanish verb card with conjugation hints.

    Args:
        infinitive: Spanish verb in infinitive form
        english: English translation
        conjugation_notes: Optional notes (e.g., "stem-changing o→ue", "irregular")
        example: Optional example sentence

    Returns:
        Dictionary with 'front' and 'back' fields
    """
    front = infinitive.strip()

    # Build the back of the card
    back_parts = [english.strip()]

    # Add conjugation notes
    if conjugation_notes:
        back_parts.append(f"({conjugation_notes.strip()})")

    # Determine verb type from ending
    if infinitive.endswith("ar"):
        back_parts.append("[AR verb]")
    elif infinitive.endswith("er"):
        back_parts.append("[ER verb]")
    elif infinitive.endswith("ir"):
        back_parts.append("[IR verb]")

    # Add example sentence if provided
    if example:
        back_parts.append(f"\nExample: {example.strip()}")

    back = "\n".join(back_parts)

    return {
        "front": front,
        "back": back
    }


def format_sentence_cloze(
    spanish: str,
    target_word: str,
    english: Optional[str] = None
) -> str:
    """
    Create a cloze deletion for a sentence.

    Args:
        spanish: Spanish sentence
        target_word: Word or phrase to turn into cloze deletion
        english: Optional English translation for the Extra field

    Returns:
        Text with {{c1::cloze}} markup

    Example:
        format_sentence_cloze(
            "Tengo que ir al supermercado",
            "Tengo que"
        )
        Returns: "{{c1::Tengo que}} ir al supermercado"
    """
    # Escape special regex characters in target_word
    pattern = re.escape(target_word.strip())

    # Replace the target word with cloze deletion (case-sensitive)
    cloze_text = re.sub(
        f"({pattern})",
        r"{{c1::\1}}",
        spanish.strip(),
        count=1
    )

    return cloze_text


def suggest_tags(
    word: str,
    pos: Optional[str] = None,
    additional_tags: Optional[list[str]] = None
) -> list[str]:
    """
    Suggest tags based on word characteristics.

    Args:
        word: The Spanish word
        pos: Part of speech ('verb', 'noun', 'adjective', 'adverb', 'phrase')
        additional_tags: Optional list of additional tags to include

    Returns:
        List of suggested tags

    Tag categories:
        - Part of speech: verb, noun, adjective, adverb, phrase, expression
        - Verb specifics: verb-ar, verb-er, verb-ir, irregular, reflexive
        - Noun specifics: masculine, feminine
        - Frequency: freq-high, freq-medium, freq-low
        - Source: source-podcast, source-book, source-conversation, source-lingoda
        - Topic: topic-food, topic-travel, topic-work, topic-daily
    """
    tags = []

    # Add part of speech tag if provided
    if pos:
        pos_lower = pos.lower()
        if pos_lower in ['verb', 'noun', 'adjective', 'adverb', 'phrase', 'expression']:
            tags.append(pos_lower)

            # Add verb-specific tags
            if pos_lower == 'verb':
                word_lower = word.lower()
                if word_lower.endswith("ar"):
                    tags.append("verb-ar")
                elif word_lower.endswith("er"):
                    tags.append("verb-er")
                elif word_lower.endswith("ir"):
                    tags.append("verb-ir")

                # Check for reflexive verbs
                if word_lower.endswith("se"):
                    tags.append("reflexive")

    # Add additional tags if provided
    if additional_tags:
        tags.extend(additional_tags)

    return tags


def get_verb_type(verb: str) -> str | None:
    """
    Determine the verb type from the infinitive.

    Args:
        verb: Spanish verb in infinitive form

    Returns:
        'ar', 'er', 'ir', or None if not a verb
    """
    verb_lower = verb.lower().strip()

    if verb_lower.endswith("arse") or verb_lower.endswith("ar"):
        return "ar"
    elif verb_lower.endswith("erse") or verb_lower.endswith("er"):
        return "er"
    elif verb_lower.endswith("irse") or verb_lower.endswith("ir"):
        return "ir"

    return None


def is_reflexive_verb(verb: str) -> bool:
    """
    Check if a verb is reflexive.

    Args:
        verb: Spanish verb

    Returns:
        True if reflexive, False otherwise
    """
    return verb.lower().strip().endswith("se")
