"""Tests for the mock AnkiConnect server itself.

These tests verify the mock server's behavior independently of the AnkiClient,
ensuring it correctly simulates the AnkiConnect API.
"""

import pytest
import aiohttp
import json
from mock_anki import MockAnkiConnect, MockAnkiState, MockNote, MockCard


pytestmark = pytest.mark.asyncio


class TestMockServerStartStop:
    """Test server lifecycle."""

    async def test_start_and_stop(self):
        """Test that server starts and stops cleanly."""
        server = MockAnkiConnect()
        port = await server.start()

        assert port > 0
        assert server.port == port

        await server.stop()

    async def test_random_port_assignment(self):
        """Test that port 0 assigns a random available port."""
        server = MockAnkiConnect()
        port = await server.start(port=0)

        assert port > 1024  # Should be an unprivileged port

        await server.stop()


class TestMockServerHTTP:
    """Test HTTP request handling."""

    async def test_version_endpoint(self, mock_anki_server):
        """Test version action returns correct response."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{mock_anki_server.port}/",
                json={"action": "version", "version": 6}
            ) as resp:
                data = await resp.json()

        assert data["result"] == 6
        assert data["error"] is None

    async def test_unknown_action(self, mock_anki_server):
        """Test unknown action returns error."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{mock_anki_server.port}/",
                json={"action": "unknownAction", "version": 6}
            ) as resp:
                data = await resp.json()

        assert data["result"] is None
        assert "Unknown action" in data["error"]

    async def test_malformed_request(self, mock_anki_server):
        """Test malformed request handling."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{mock_anki_server.port}/",
                data="not json"
            ) as resp:
                data = await resp.json()

        assert data["error"] is not None


class TestMockStateManagement:
    """Test in-memory state management."""

    async def test_initial_state(self):
        """Test initial state has expected defaults."""
        state = MockAnkiState()

        assert "Default" in state.decks
        assert "Basic" in state.models
        assert "Cloze" in state.models
        assert len(state.notes) == 0
        assert len(state.cards) == 0

    async def test_create_deck(self, mock_anki_server):
        """Test deck creation adds to state."""
        initial_count = len(mock_anki_server.state.decks)

        mock_anki_server._create_deck({"deck": "TestDeck"})

        assert "TestDeck" in mock_anki_server.state.decks
        assert len(mock_anki_server.state.decks) == initial_count + 1

    async def test_create_deck_idempotent(self, mock_anki_server):
        """Test creating same deck twice doesn't duplicate."""
        mock_anki_server._create_deck({"deck": "TestDeck"})
        deck_id_1 = mock_anki_server.state.decks["TestDeck"]

        mock_anki_server._create_deck({"deck": "TestDeck"})
        deck_id_2 = mock_anki_server.state.decks["TestDeck"]

        assert deck_id_1 == deck_id_2


class TestMockNoteOperations:
    """Test note-related operations."""

    async def test_add_note_creates_card(self, mock_anki_server):
        """Test adding a note also creates a card."""
        note_id = mock_anki_server._add_note({
            "note": {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "Q", "Back": "A"},
                "tags": []
            }
        })

        assert note_id is not None
        assert note_id in mock_anki_server.state.notes

        # Find associated card
        cards = [c for c in mock_anki_server.state.cards.values()
                 if c.note_id == note_id]
        assert len(cards) == 1
        assert cards[0].question == "Q"
        assert cards[0].answer == "A"

    async def test_add_duplicate_note_returns_none(self, mock_anki_server):
        """Test adding duplicate note returns None."""
        note_data = {
            "note": {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "Duplicate", "Back": "A"},
                "tags": []
            }
        }

        note_id_1 = mock_anki_server._add_note(note_data)
        note_id_2 = mock_anki_server._add_note(note_data)

        assert note_id_1 is not None
        assert note_id_2 is None

    async def test_delete_note_removes_cards(self, mock_anki_server):
        """Test deleting a note also removes its cards."""
        note_id = mock_anki_server._add_note({
            "note": {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "ToDelete", "Back": "A"},
                "tags": []
            }
        })

        # Verify card exists
        cards_before = [c for c in mock_anki_server.state.cards.values()
                        if c.note_id == note_id]
        assert len(cards_before) == 1

        # Delete note
        mock_anki_server._delete_notes({"notes": [note_id]})

        # Verify both note and card are gone
        assert note_id not in mock_anki_server.state.notes
        cards_after = [c for c in mock_anki_server.state.cards.values()
                       if c.note_id == note_id]
        assert len(cards_after) == 0


class TestMockQueryParsing:
    """Test query parsing for findCards/findNotes."""

    async def test_deck_query_with_quotes(self, mock_anki_server):
        """Test deck query with quoted name."""
        mock_anki_server._create_deck({"deck": "Test Deck"})
        mock_anki_server._add_note({
            "note": {
                "deckName": "Test Deck",
                "modelName": "Basic",
                "fields": {"Front": "Q1", "Back": "A1"},
                "tags": []
            }
        })

        results = mock_anki_server._find_cards({"query": 'deck:"Test Deck"'})
        assert len(results) == 1

    async def test_tag_query(self, mock_anki_server):
        """Test tag query matching."""
        mock_anki_server._add_note({
            "note": {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "Tagged", "Back": "A"},
                "tags": ["test-tag"]
            }
        })

        results = mock_anki_server._find_notes({"query": "tag:test-tag"})
        assert len(results) == 1

    async def test_prop_ease_query(self, mock_anki_server):
        """Test prop:ease query."""
        card_id = mock_anki_server.add_problem_card("Default", low_ease=True)

        results = mock_anki_server._find_cards({"query": "prop:ease<2"})
        assert card_id in results

    async def test_prop_lapses_query(self, mock_anki_server):
        """Test prop:lapses query."""
        card_id = mock_anki_server.add_problem_card("Default", high_lapses=True)

        results = mock_anki_server._find_cards({"query": "prop:lapses>=4"})
        assert card_id in results

    async def test_is_suspended_query(self, mock_anki_server):
        """Test is:suspended query."""
        card_id = mock_anki_server.add_suspended_card("Default")

        results = mock_anki_server._find_cards({"query": "is:suspended"})
        assert card_id in results

    async def test_is_due_query(self, mock_anki_server):
        """Test is:due query."""
        card_id = mock_anki_server.add_due_card("Default")

        results = mock_anki_server._find_cards({"query": "is:due"})
        assert card_id in results

    async def test_combined_query(self, mock_anki_server):
        """Test combined deck and tag query."""
        mock_anki_server._create_deck({"deck": "TestDeck"})
        mock_anki_server._add_note({
            "note": {
                "deckName": "TestDeck",
                "modelName": "Basic",
                "fields": {"Front": "Combined", "Back": "A"},
                "tags": ["special"]
            }
        })

        results = mock_anki_server._find_cards({"query": 'deck:"TestDeck" tag:special'})
        assert len(results) == 1


class TestMockCardStateOperations:
    """Test card state operations (suspend, unsuspend, etc.)."""

    async def test_suspend_unsuspend(self, mock_anki_server):
        """Test suspend and unsuspend operations."""
        note_id = mock_anki_server._add_note({
            "note": {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": "Suspend Test", "Back": "A"},
                "tags": []
            }
        })

        card = [c for c in mock_anki_server.state.cards.values()
                if c.note_id == note_id][0]

        # Initially not suspended
        assert card.suspended is False

        # Suspend
        mock_anki_server._suspend({"cards": [card.card_id]})
        assert card.suspended is True

        # Unsuspend
        mock_anki_server._unsuspend({"cards": [card.card_id]})
        assert card.suspended is False

    async def test_are_suspended(self, mock_anki_server):
        """Test checking suspension status."""
        card_id = mock_anki_server.add_suspended_card("Default")

        results = mock_anki_server._are_suspended({"cards": [card_id, 99999]})

        assert results[0] is True  # Suspended card
        assert results[1] is False  # Non-existent card


class TestMockSchedulingOperations:
    """Test scheduling operations."""

    async def test_forget_cards(self, mock_anki_server):
        """Test resetting card progress."""
        card_id = mock_anki_server.add_problem_card("Default", low_ease=True, high_lapses=True)
        card = mock_anki_server.state.cards[card_id]

        # Verify initial state
        assert card.interval > 0
        assert card.lapses > 0

        # Reset
        mock_anki_server._forget_cards({"cards": [card_id]})

        # Verify reset state
        assert card.interval == 0
        assert card.lapses == 0
        assert card.queue == 0
        assert card.factor == 2500

    async def test_set_ease_factors(self, mock_anki_server):
        """Test setting ease factors."""
        card_id = mock_anki_server.add_problem_card("Default")

        results = mock_anki_server._set_ease_factors({
            "cards": [card_id],
            "easeFactors": [3000]
        })

        assert results[0] is True
        assert mock_anki_server.state.cards[card_id].factor == 3000

    async def test_get_ease_factors(self, mock_anki_server):
        """Test getting ease factors."""
        card_id = mock_anki_server.add_problem_card("Default", low_ease=True)

        results = mock_anki_server._get_ease_factors({"cards": [card_id]})

        assert results[0] == 1500  # Low ease value


class TestMockHelperMethods:
    """Test helper methods for test setup."""

    async def test_add_problem_card(self, mock_anki_server):
        """Test add_problem_card helper."""
        card_id = mock_anki_server.add_problem_card(
            "TestDeck",
            low_ease=True,
            high_lapses=True
        )

        card = mock_anki_server.state.cards[card_id]
        assert card.factor == 1500
        assert card.lapses == 5
        assert card.deck_name == "TestDeck"

    async def test_add_due_card(self, mock_anki_server):
        """Test add_due_card helper."""
        card_id = mock_anki_server.add_due_card("TestDeck")

        card = mock_anki_server.state.cards[card_id]
        assert card.queue == 2
        assert card.due == 0

    async def test_add_suspended_card(self, mock_anki_server):
        """Test add_suspended_card helper."""
        card_id = mock_anki_server.add_suspended_card("TestDeck")

        card = mock_anki_server.state.cards[card_id]
        assert card.suspended is True
