"""Tests for AnkiConnect client.

These tests use a mock AnkiConnect server and can run in CI without Anki.
"""

import pytest
from anki_mcp.anki_client import AnkiClient, AnkiConnectError


# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


# Fixtures are provided by conftest.py:
# - anki_client: AnkiClient connected to mock server
# - test_deck_name: consistent test deck name
# - mock_anki_server: the mock server instance
# - mock_state: direct access to mock state


class TestHealthCheck:
    async def test_version(self, anki_client):
        """Test that we can get the AnkiConnect version."""
        version = await anki_client.version()
        assert isinstance(version, int)
        assert version >= 6


class TestDeckOperations:
    async def test_deck_names(self, anki_client):
        """Test listing deck names."""
        decks = await anki_client.deck_names()
        assert isinstance(decks, list)
        assert "Default" in decks

    async def test_create_deck(self, anki_client, test_deck_name):
        """Test creating a new deck."""
        deck_id = await anki_client.create_deck(test_deck_name)
        assert isinstance(deck_id, int)

        # Verify the deck was created
        decks = await anki_client.deck_names()
        assert test_deck_name in decks


class TestModelOperations:
    async def test_model_names(self, anki_client):
        """Test listing model names."""
        models = await anki_client.model_names()
        assert isinstance(models, list)
        assert "Basic" in models
        assert "Cloze" in models

    async def test_model_field_names(self, anki_client):
        """Test getting field names for a model."""
        fields = await anki_client.model_field_names("Basic")
        assert isinstance(fields, list)
        assert "Front" in fields
        assert "Back" in fields


class TestNoteOperations:
    async def test_add_note(self, anki_client, test_deck_name):
        """Test adding a single note."""
        # Create test deck
        await anki_client.create_deck(test_deck_name)

        # Add a note
        fields = {"Front": "Test Question", "Back": "Test Answer"}
        note_id = await anki_client.add_note(
            test_deck_name,
            "Basic",
            fields,
            tags=["test"]
        )

        assert note_id is not None
        assert isinstance(note_id, int)

    async def test_add_duplicate_note(self, anki_client, test_deck_name):
        """Test that adding a duplicate note returns None."""
        await anki_client.create_deck(test_deck_name)

        # Add a note
        fields = {"Front": "Duplicate Test", "Back": "Answer"}
        note_id1 = await anki_client.add_note(test_deck_name, "Basic", fields)

        # Try to add the same note again
        note_id2 = await anki_client.add_note(test_deck_name, "Basic", fields)

        assert note_id1 is not None
        assert note_id2 is None

    async def test_add_notes_batch(self, anki_client, test_deck_name):
        """Test adding multiple notes at once."""
        await anki_client.create_deck(test_deck_name)

        notes = [
            {
                "deckName": test_deck_name,
                "modelName": "Basic",
                "fields": {"Front": f"Q{i}", "Back": f"A{i}"},
                "tags": ["batch-test"]
            }
            for i in range(3)
        ]

        note_ids = await anki_client.add_notes(notes)

        assert len(note_ids) == 3
        assert all(nid is not None for nid in note_ids)

    async def test_find_notes(self, anki_client, test_deck_name):
        """Test searching for notes."""
        await anki_client.create_deck(test_deck_name)

        # Add a note with a unique tag
        fields = {"Front": "Searchable", "Back": "Answer"}
        await anki_client.add_note(
            test_deck_name,
            "Basic",
            fields,
            tags=["unique-search-tag"]
        )

        # Search for the note
        note_ids = await anki_client.find_notes("tag:unique-search-tag")

        assert len(note_ids) > 0

    async def test_notes_info(self, anki_client, test_deck_name):
        """Test getting note information."""
        await anki_client.create_deck(test_deck_name)

        # Add a note
        fields = {"Front": "Info Test", "Back": "Info Answer"}
        note_id = await anki_client.add_note(
            test_deck_name,
            "Basic",
            fields,
            tags=["info-test"]
        )

        # Get note info
        notes_info = await anki_client.notes_info([note_id])

        assert len(notes_info) == 1
        note_info = notes_info[0]
        assert note_info["noteId"] == note_id
        assert "info-test" in note_info["tags"]


class TestClozeCards:
    async def test_add_cloze_note(self, anki_client, test_deck_name):
        """Test adding a cloze deletion note."""
        await anki_client.create_deck(test_deck_name)

        fields = {
            "Text": "The {{c1::capital}} of Spain is Madrid",
            "Extra": "Geography"
        }
        note_id = await anki_client.add_note(
            test_deck_name,
            "Cloze",
            fields,
            tags=["cloze-test"]
        )

        assert note_id is not None
        assert isinstance(note_id, int)
