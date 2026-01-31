"""Tests for card statistics functionality.

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


class TestDeckStats:
    async def test_get_deck_stats(self, anki_client, test_deck_name):
        """Test getting statistics for a deck."""
        # Create test deck
        await anki_client.create_deck(test_deck_name)

        # Get stats
        stats = await anki_client.get_deck_stats([test_deck_name])

        assert isinstance(stats, dict)
        # Stats are keyed by deck ID
        assert len(stats) >= 1

        # Check structure of stats
        for deck_id, deck_stats in stats.items():
            assert 'new_count' in deck_stats
            assert 'learn_count' in deck_stats
            assert 'review_count' in deck_stats

    async def test_get_deck_stats_multiple_decks(self, anki_client):
        """Test getting statistics for multiple decks."""
        # Use Default deck which always exists
        stats = await anki_client.get_deck_stats(["Default"])

        assert isinstance(stats, dict)
        assert len(stats) >= 1


class TestCollectionStats:
    async def test_get_num_cards_reviewed_today(self, anki_client):
        """Test getting number of cards reviewed today."""
        count = await anki_client.get_num_cards_reviewed_today()

        assert isinstance(count, int)
        assert count >= 0

    async def test_get_num_cards_reviewed_by_day(self, anki_client):
        """Test getting review history by day."""
        history = await anki_client.get_num_cards_reviewed_by_day()

        assert isinstance(history, list)
        # Each entry should be [days_ago, count]
        for entry in history:
            assert isinstance(entry, list)
            assert len(entry) == 2


class TestCardSearch:
    async def test_find_cards(self, anki_client, test_deck_name):
        """Test finding cards by query."""
        # Create deck and add a card
        await anki_client.create_deck(test_deck_name)

        fields = {"Front": "Stats Test Question", "Back": "Stats Test Answer"}
        await anki_client.add_note(
            test_deck_name,
            "Basic",
            fields,
            tags=["stats-test"]
        )

        # Find cards in the deck
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}"')

        assert isinstance(card_ids, list)
        # Should have at least our test card
        assert len(card_ids) >= 1

    async def test_find_cards_empty_result(self, anki_client):
        """Test finding cards with query that matches nothing."""
        card_ids = await anki_client.find_cards("deck:NonexistentDeck12345")

        assert isinstance(card_ids, list)
        assert len(card_ids) == 0


class TestCardsInfo:
    async def test_cards_info(self, anki_client, test_deck_name):
        """Test getting detailed card information."""
        # Create deck and add a card
        await anki_client.create_deck(test_deck_name)

        fields = {"Front": "Card Info Test", "Back": "Answer"}
        await anki_client.add_note(
            test_deck_name,
            "Basic",
            fields,
            tags=["cardinfo-test"]
        )

        # Find the card
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}" tag:cardinfo-test')

        assert len(card_ids) >= 1

        # Get card info
        cards = await anki_client.cards_info(card_ids)

        assert len(cards) >= 1
        card = cards[0]

        # Check expected fields
        assert 'cardId' in card
        assert 'deckName' in card
        assert 'factor' in card  # Ease factor
        assert 'lapses' in card
        assert 'interval' in card

    async def test_cards_info_empty_list(self, anki_client):
        """Test getting card info with empty list."""
        cards = await anki_client.cards_info([])

        assert isinstance(cards, list)
        assert len(cards) == 0


class TestIntervals:
    async def test_get_intervals(self, anki_client, test_deck_name):
        """Test getting card intervals."""
        # Create deck and add a card
        await anki_client.create_deck(test_deck_name)

        fields = {"Front": "Interval Test", "Back": "Answer"}
        await anki_client.add_note(
            test_deck_name,
            "Basic",
            fields,
            tags=["interval-test"]
        )

        # Find the card
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}" tag:interval-test')

        assert len(card_ids) >= 1

        # Get intervals
        intervals = await anki_client.get_intervals(card_ids)

        assert isinstance(intervals, list)
        assert len(intervals) == len(card_ids)


class TestProblemCards:
    async def test_find_low_ease_cards(self, anki_client, mock_anki_server, test_deck_name):
        """Test finding cards with low ease factor."""
        # Add a problem card with low ease
        mock_anki_server.add_problem_card(test_deck_name, low_ease=True)

        # Search for low ease cards
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}" prop:ease<2')

        assert isinstance(card_ids, list)
        assert len(card_ids) >= 1

    async def test_find_high_lapse_cards(self, anki_client, mock_anki_server, test_deck_name):
        """Test finding cards with high lapse count."""
        # Add a problem card with high lapses
        mock_anki_server.add_problem_card(test_deck_name, high_lapses=True)

        # Search for high lapse cards
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}" prop:lapses>=4')

        assert isinstance(card_ids, list)
        assert len(card_ids) >= 1

    async def test_problem_card_info(self, anki_client, mock_anki_server, test_deck_name):
        """Test getting info for problem cards."""
        # Add a problem card
        card_id = mock_anki_server.add_problem_card(test_deck_name, low_ease=True, high_lapses=True)

        # Get card info
        cards = await anki_client.cards_info([card_id])

        assert len(cards) == 1
        card = cards[0]
        assert card['factor'] == 1500  # Low ease
        assert card['lapses'] == 5  # High lapses


class TestGetCardStats:
    """Tests for the get_card_stats tool functionality."""

    async def test_get_card_stats_basic(self, anki_client, test_deck_name):
        """Test getting card stats for cards matching a query."""
        # Create deck and add cards
        await anki_client.create_deck(test_deck_name)

        fields1 = {"Front": "What is Python?", "Back": "A programming language"}
        fields2 = {"Front": "What is JavaScript?", "Back": "A web scripting language"}
        await anki_client.add_note(test_deck_name, "Basic", fields1, tags=["programming"])
        await anki_client.add_note(test_deck_name, "Basic", fields2, tags=["programming"])

        # Find cards
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}"')
        assert len(card_ids) >= 2

        # Get card info
        cards = await anki_client.cards_info(card_ids[:10])
        assert len(cards) >= 2

        # Check structure
        for card in cards:
            assert 'cardId' in card
            assert 'deckName' in card
            assert 'factor' in card
            assert 'interval' in card
            assert 'lapses' in card
            assert 'reps' in card
            assert 'queue' in card
            assert 'type' in card
            assert 'due' in card
            assert 'note' in card

    async def test_get_card_stats_with_limit(self, anki_client, test_deck_name):
        """Test that limit parameter works correctly."""
        # Create deck and add multiple cards
        await anki_client.create_deck(test_deck_name)

        for i in range(5):
            fields = {"Front": f"Question {i}", "Back": f"Answer {i}"}
            await anki_client.add_note(test_deck_name, "Basic", fields)

        # Find cards with limit
        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}"')
        assert len(card_ids) >= 5

        # Apply limit
        limited_ids = card_ids[:3]
        cards = await anki_client.cards_info(limited_ids)
        assert len(cards) == 3

    async def test_get_card_stats_empty_query(self, anki_client):
        """Test getting card stats with a query that matches nothing."""
        card_ids = await anki_client.find_cards("deck:NonexistentDeckXYZ123")
        assert len(card_ids) == 0

    async def test_get_card_stats_with_problem_card(self, anki_client, mock_anki_server, test_deck_name):
        """Test getting stats for problem cards with specific values."""
        # Add a problem card with known values
        card_id = mock_anki_server.add_problem_card(
            test_deck_name,
            low_ease=True,
            high_lapses=True
        )

        cards = await anki_client.cards_info([card_id])
        assert len(cards) == 1

        card = cards[0]
        # Verify problem card stats
        assert card['factor'] == 1500  # Low ease (1.5 or 150%)
        assert card['lapses'] == 5  # High lapses
        assert card['cardId'] == card_id
        assert card['deckName'] == test_deck_name

    async def test_get_card_stats_includes_reps(self, anki_client, test_deck_name):
        """Test that reps (total reviews) field is included."""
        await anki_client.create_deck(test_deck_name)

        fields = {"Front": "Reps Test", "Back": "Answer"}
        await anki_client.add_note(test_deck_name, "Basic", fields)

        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}"')
        cards = await anki_client.cards_info(card_ids)

        assert len(cards) >= 1
        assert 'reps' in cards[0]
        assert isinstance(cards[0]['reps'], int)

    async def test_get_card_stats_card_type_values(self, anki_client, test_deck_name):
        """Test that card type values are valid."""
        await anki_client.create_deck(test_deck_name)

        fields = {"Front": "Type Test", "Back": "Answer"}
        await anki_client.add_note(test_deck_name, "Basic", fields)

        card_ids = await anki_client.find_cards(f'deck:"{test_deck_name}"')
        cards = await anki_client.cards_info(card_ids)

        assert len(cards) >= 1
        card = cards[0]

        # Type should be 0 (new), 1 (learning), 2 (review), or 3 (relearning)
        assert card['type'] in [0, 1, 2, 3]
        # Queue should be valid value
        assert card['queue'] in [-3, -2, -1, 0, 1, 2, 3, 4]
