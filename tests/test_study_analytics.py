"""Tests for Tier 3: Study analytics and retention tracking."""

import pytest
from anki_mcp.anki_client import AnkiClient


pytestmark = pytest.mark.asyncio


class TestReviewHistory:
    """Test review history retrieval."""

    async def test_get_card_reviews(self, anki_client, mock_anki_server):
        """Test getting card reviews for a deck."""
        # Add review data
        mock_anki_server.add_review_data("Default", [3, 3, 4, 1, 3, 2, 3, 3, 4, 3])

        reviews = await anki_client.get_card_reviews("Default")

        assert len(reviews) == 10
        # Check structure
        assert "id" in reviews[0]
        assert "ease" in reviews[0]
        assert "ivl" in reviews[0]
        assert "time" in reviews[0]

    async def test_get_card_reviews_empty_deck(self, anki_client, mock_anki_server):
        """Test getting reviews for a deck with no reviews."""
        mock_anki_server._create_deck({"deck": "Empty"})
        mock_anki_server.state.reviews["Empty"] = []

        reviews = await anki_client.get_card_reviews("Empty")

        assert len(reviews) == 0

    async def test_get_latest_review_id(self, anki_client, mock_anki_server):
        """Test getting the latest review ID."""
        mock_anki_server.add_review_data("Default", [3, 3, 3])

        latest_id = await anki_client.get_latest_review_id("Default")

        assert latest_id > 0


class TestRetentionStats:
    """Test retention statistics calculation."""

    async def test_retention_with_mature_cards(self, anki_client, mock_anki_server):
        """Test retention stats include mature card counts."""
        # Add some mature cards
        mock_anki_server.add_mature_card("Default", interval=30, lapses=0)
        mock_anki_server.add_mature_card("Default", interval=45, lapses=1)
        mock_anki_server.add_mature_card("Default", interval=60, lapses=2)

        # Get stats by finding cards (simulating what retention stats tool does)
        mature_query = "prop:ivl>=21"
        card_ids = await anki_client.find_cards(mature_query)

        assert len(card_ids) == 3

    async def test_retention_with_lapsed_cards(self, anki_client, mock_anki_server):
        """Test retention stats track lapsed cards."""
        # Add cards with lapses
        mock_anki_server.add_mature_card("Default", interval=30, lapses=1)
        mock_anki_server.add_mature_card("Default", interval=30, lapses=3)
        mock_anki_server.add_mature_card("Default", interval=30, lapses=0)

        lapse_query = "prop:lapses>=1"
        card_ids = await anki_client.find_cards(lapse_query)

        assert len(card_ids) == 2


class TestStudyStreak:
    """Test study streak calculation."""

    async def test_streak_with_consecutive_days(self, anki_client, mock_anki_server):
        """Test streak calculation with consecutive study days."""
        # Default mock has 7 days of data: [10, 15, 8, 12, 20, 5, 18]
        # All have reviews, so streak should be 7
        review_history = await anki_client.get_num_cards_reviewed_by_day()

        # Calculate streak
        current_streak = 0
        for day_data in review_history:
            if day_data[1] > 0:
                current_streak += 1
            else:
                break

        assert current_streak == 7

    async def test_streak_with_gap(self, anki_client, mock_anki_server):
        """Test streak calculation with a gap in study days."""
        # Modify review data to have a gap
        mock_anki_server.state.reviews_by_day = [
            [0, 10], [1, 0], [2, 8], [3, 12]  # Day 1 has 0 reviews
        ]

        review_history = await anki_client.get_num_cards_reviewed_by_day()

        current_streak = 0
        for day_data in review_history:
            if day_data[1] > 0:
                current_streak += 1
            else:
                break

        assert current_streak == 1  # Only day 0 counted


class TestLearningCurve:
    """Test learning curve analysis."""

    async def test_learning_curve_data_available(self, anki_client, mock_anki_server):
        """Test that learning curve can get review data."""
        review_history = await anki_client.get_num_cards_reviewed_by_day()

        assert len(review_history) > 0
        # Each entry should be [days_ago, count]
        assert len(review_history[0]) == 2

    async def test_learning_curve_trend_calculation(self, anki_client, mock_anki_server):
        """Test trend calculation (comparing halves)."""
        # Set up data where second half has more reviews
        mock_anki_server.state.reviews_by_day = [
            [0, 20], [1, 25], [2, 22], [3, 24],  # Recent (higher)
            [4, 10], [5, 12], [6, 11], [7, 10],  # Older (lower)
        ]

        review_history = await anki_client.get_num_cards_reviewed_by_day()

        # Calculate halves
        half = len(review_history) // 2
        first_half = sum(d[1] for d in review_history[:half])
        second_half = sum(d[1] for d in review_history[half:])

        # Second half (older data) should have fewer reviews
        assert first_half > second_half


class TestMockReviewData:
    """Test mock review data generation."""

    async def test_generate_mock_reviews(self, mock_anki_server):
        """Test that mock reviews are generated correctly."""
        mock_anki_server._generate_mock_reviews("TestDeck")

        reviews = mock_anki_server.state.reviews.get("TestDeck", [])
        assert len(reviews) == 50

        # Check structure
        review = reviews[0]
        assert review.review_id > 0
        assert review.ease in [1, 2, 3, 4]
        assert review.ivl > 0
        assert review.time > 0

    async def test_add_review_data_custom(self, mock_anki_server):
        """Test adding custom review data."""
        outcomes = [1, 1, 3, 4]  # 2 again, 1 good, 1 easy
        mock_anki_server.add_review_data("CustomDeck", outcomes)

        reviews = mock_anki_server.state.reviews.get("CustomDeck", [])
        assert len(reviews) == 4

        eases = [r.ease for r in reviews]
        assert eases == [1, 1, 3, 4]


class TestAnalyticsIntegration:
    """Integration tests for analytics features."""

    async def test_full_analytics_workflow(self, anki_client, mock_anki_server):
        """Test complete analytics workflow."""
        # Set up deck with various card types
        mock_anki_server.add_mature_card("Analytics", interval=30, lapses=0)
        mock_anki_server.add_mature_card("Analytics", interval=45, lapses=2)
        mock_anki_server.add_problem_card("Analytics", low_ease=True)
        mock_anki_server.add_due_card("Analytics")
        mock_anki_server.add_review_data("Analytics", [3, 3, 4, 1, 3])

        # Get deck stats
        stats = await anki_client.get_deck_stats(["Analytics"])
        assert len(stats) > 0

        # Get review history
        reviews = await anki_client.get_card_reviews("Analytics")
        assert len(reviews) == 5

        # Get review counts
        review_history = await anki_client.get_num_cards_reviewed_by_day()
        assert len(review_history) > 0

    async def test_analytics_with_empty_collection(self, anki_client, mock_anki_server):
        """Test analytics work with minimal data."""
        # Empty deck
        mock_anki_server._create_deck({"deck": "Empty"})

        stats = await anki_client.get_deck_stats(["Empty"])

        # Should return stats with zero counts
        deck_stats = list(stats.values())[0]
        assert deck_stats["new_count"] == 0
        assert deck_stats["learn_count"] == 0
        assert deck_stats["review_count"] == 0
