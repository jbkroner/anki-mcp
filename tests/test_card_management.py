"""Tests for card management functionality (Phases 2-4).

These tests use a mock AnkiConnect server and can run in CI without Anki.
"""

import pytest
from anki_mcp.anki_client import AnkiClient, AnkiConnectError


# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


# Fixtures are provided by conftest.py


class TestSuspendUnsuspend:
    """Phase 2: Card state management tests."""

    async def test_suspend_cards(self, anki_client, mock_anki_server, test_deck_name):
        """Test suspending cards."""
        # Add a card
        await anki_client.create_deck(test_deck_name)
        fields = {"Front": "Suspend Test", "Back": "Answer"}
        note_id = await anki_client.add_note(test_deck_name, "Basic", fields)

        # Find the card
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}"')
        assert len(card_ids) >= 1

        # Suspend it
        result = await anki_client.suspend(card_ids)
        assert result is True

        # Verify it's suspended
        suspended = await anki_client.are_suspended(card_ids)
        assert suspended[0] is True

    async def test_unsuspend_cards(self, anki_client, mock_anki_server, test_deck_name):
        """Test unsuspending cards."""
        # Add a suspended card
        card_id = mock_anki_server.add_suspended_card(test_deck_name)

        # Verify it's suspended
        suspended = await anki_client.are_suspended([card_id])
        assert suspended[0] is True

        # Unsuspend it
        await anki_client.unsuspend([card_id])

        # Verify it's no longer suspended
        suspended = await anki_client.are_suspended([card_id])
        assert suspended[0] is False

    async def test_find_suspended_cards(self, anki_client, mock_anki_server, test_deck_name):
        """Test finding suspended cards."""
        # Add a suspended card
        card_id = mock_anki_server.add_suspended_card(test_deck_name)

        # Find suspended cards
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}" is:suspended')
        assert card_id in card_ids

    async def test_are_buried(self, anki_client, mock_anki_server, test_deck_name):
        """Test checking burial status."""
        await anki_client.create_deck(test_deck_name)
        fields = {"Front": "Bury Test", "Back": "Answer"}
        await anki_client.add_note(test_deck_name, "Basic", fields)

        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}"')
        buried = await anki_client.are_buried(card_ids)

        # Should not be buried by default
        assert buried[0] is False


class TestContentManagement:
    """Phase 3: Content management tests."""

    async def test_update_note_fields(self, anki_client, test_deck_name):
        """Test updating note fields."""
        await anki_client.create_deck(test_deck_name)
        fields = {"Front": "Original Question", "Back": "Original Answer"}
        note_id = await anki_client.add_note(test_deck_name, "Basic", fields)

        # Update the note
        new_fields = {"Front": "Updated Question", "Back": "Updated Answer"}
        await anki_client.update_note_fields(note_id, new_fields)

        # Verify the update
        notes = await anki_client.notes_info([note_id])
        assert notes[0]["fields"]["Front"]["value"] == "Updated Question"
        assert notes[0]["fields"]["Back"]["value"] == "Updated Answer"

    async def test_delete_notes(self, anki_client, test_deck_name):
        """Test deleting notes."""
        await anki_client.create_deck(test_deck_name)
        fields = {"Front": "Delete Test", "Back": "Answer"}
        note_id = await anki_client.add_note(test_deck_name, "Basic", fields, tags=["delete-test"])

        # Verify note exists
        note_ids = await anki_client.find_notes("tag:delete-test")
        assert note_id in note_ids

        # Delete the note
        await anki_client.delete_notes([note_id])

        # Verify note is gone
        note_ids = await anki_client.find_notes("tag:delete-test")
        assert note_id not in note_ids

    async def test_change_deck(self, anki_client, test_deck_name):
        """Test moving cards to a different deck."""
        source_deck = test_deck_name
        target_deck = f"{test_deck_name}::Target"

        await anki_client.create_deck(source_deck)
        await anki_client.create_deck(target_deck)

        fields = {"Front": "Move Test", "Back": "Answer"}
        await anki_client.add_note(source_deck, "Basic", fields, tags=["move-test"])

        # Find the card in source deck
        card_ids = await anki_client.find_cards(f'deck:"{source_deck}" tag:move-test')
        assert len(card_ids) >= 1

        # Move to target deck
        await anki_client.change_deck(card_ids, target_deck)

        # Verify card is now in target deck
        cards = await anki_client.cards_info(card_ids)
        assert cards[0]["deckName"] == target_deck

    async def test_remove_tags(self, anki_client, test_deck_name):
        """Test removing tags from notes."""
        await anki_client.create_deck(test_deck_name)
        fields = {"Front": "Tag Test", "Back": "Answer"}
        note_id = await anki_client.add_note(
            test_deck_name, "Basic", fields,
            tags=["tag1", "tag2", "tag3"]
        )

        # Remove some tags
        await anki_client.remove_tags([note_id], "tag1 tag2")

        # Verify tags were removed
        notes = await anki_client.notes_info([note_id])
        assert "tag1" not in notes[0]["tags"]
        assert "tag2" not in notes[0]["tags"]
        assert "tag3" in notes[0]["tags"]


class TestScheduling:
    """Phase 4: Scheduling tests."""

    async def test_find_due_cards(self, anki_client, mock_anki_server, test_deck_name):
        """Test finding due cards."""
        # Add a due card
        card_id = mock_anki_server.add_due_card(test_deck_name)

        # Find due cards
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}" is:due')
        assert card_id in card_ids

    async def test_forget_cards(self, anki_client, mock_anki_server, test_deck_name):
        """Test resetting card progress."""
        # Add a reviewed card (with interval > 0)
        card_id = mock_anki_server.add_problem_card(test_deck_name, high_lapses=True)

        # Get initial state
        cards = await anki_client.cards_info([card_id])
        assert cards[0]["interval"] > 0

        # Reset the card
        await anki_client.forget_cards([card_id])

        # Verify it's reset
        cards = await anki_client.cards_info([card_id])
        assert cards[0]["interval"] == 0
        assert cards[0]["queue"] == 0  # New queue

    async def test_set_ease_factors(self, anki_client, mock_anki_server, test_deck_name):
        """Test setting ease factors."""
        # Add a card
        card_id = mock_anki_server.add_problem_card(test_deck_name)

        # Set ease factor
        new_ease = 2000  # 200%
        results = await anki_client.set_ease_factors([card_id], [new_ease])
        assert results[0] is True

        # Verify ease was set
        ease_factors = await anki_client.get_ease_factors([card_id])
        assert ease_factors[0] == new_ease

    async def test_get_ease_factors(self, anki_client, mock_anki_server, test_deck_name):
        """Test getting ease factors."""
        # Add a card with known ease
        card_id = mock_anki_server.add_problem_card(test_deck_name, low_ease=True)

        # Get ease factor
        ease_factors = await anki_client.get_ease_factors([card_id])
        assert ease_factors[0] == 1500  # Low ease is 1500 (150%)


class TestCardContentRetrieval:
    """Tests for issue #9: Ensure card functions return actual content, not CSS."""

    async def test_suspended_cards_returns_actual_content(self, anki_client, mock_anki_server, test_deck_name):
        """Test that get_suspended_cards returns actual card content, not CSS styling."""
        # Add a suspended card with known content
        card_id = mock_anki_server.add_suspended_card(test_deck_name)

        # Get the card info to verify the content exists
        cards = await anki_client.cards_info([card_id])
        assert len(cards) == 1

        # Get the note content
        note_id = cards[0].get('note')
        notes = await anki_client.notes_info([note_id])
        assert len(notes) == 1

        # Verify note has proper fields (not CSS)
        fields = notes[0].get('fields', {})
        assert 'Front' in fields
        assert 'Back' in fields

        front_value = fields['Front'].get('value', '')
        back_value = fields['Back'].get('value', '')

        # Content should NOT contain CSS styling
        assert '.card' not in front_value
        assert 'font-family' not in front_value
        assert '.card' not in back_value

        # Content SHOULD contain actual text
        assert 'Suspended Q' in front_value
        assert 'Suspended A' in back_value

    async def test_due_cards_returns_actual_content(self, anki_client, mock_anki_server, test_deck_name):
        """Test that get_due_cards returns actual card content, not CSS styling."""
        # Add a due card with known content
        card_id = mock_anki_server.add_due_card(test_deck_name)

        # Get the card info
        cards = await anki_client.cards_info([card_id])
        assert len(cards) == 1

        # Get the note content
        note_id = cards[0].get('note')
        notes = await anki_client.notes_info([note_id])
        assert len(notes) == 1

        # Verify note has proper fields (not CSS)
        fields = notes[0].get('fields', {})
        assert 'Front' in fields
        assert 'Back' in fields

        front_value = fields['Front'].get('value', '')
        back_value = fields['Back'].get('value', '')

        # Content should NOT contain CSS styling
        assert '.card' not in front_value
        assert 'font-family' not in front_value
        assert '.card' not in back_value

        # Content SHOULD contain actual text
        assert 'Due Q' in front_value
        assert 'Due A' in back_value

    async def test_notes_info_returns_field_values(self, anki_client, test_deck_name):
        """Test that notes_info returns actual field values."""
        await anki_client.create_deck(test_deck_name)

        # Add a note with specific content
        fields = {"Front": "Test Question Content", "Back": "Test Answer Content"}
        note_id = await anki_client.add_note(test_deck_name, "Basic", fields)

        # Get note info
        notes = await anki_client.notes_info([note_id])
        assert len(notes) == 1

        note_fields = notes[0].get('fields', {})

        # Verify exact content is returned
        assert note_fields['Front']['value'] == "Test Question Content"
        assert note_fields['Back']['value'] == "Test Answer Content"
