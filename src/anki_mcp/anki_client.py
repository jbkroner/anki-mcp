"""AnkiConnect API client wrapper."""

import httpx
from typing import Any


class AnkiConnectError(Exception):
    """Exception raised when AnkiConnect returns an error."""
    pass


class AnkiClient:
    """Client for communicating with AnkiConnect."""

    def __init__(self, url: str = "http://localhost:8765"):
        """
        Initialize the AnkiConnect client.

        Args:
            url: AnkiConnect server URL (default: http://localhost:8765)
        """
        self.url = url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _invoke(self, action: str, **params) -> Any:
        """
        Invoke an AnkiConnect action.

        Args:
            action: AnkiConnect action name
            **params: Action parameters

        Returns:
            Response result

        Raises:
            AnkiConnectError: If AnkiConnect returns an error
            httpx.HTTPError: If the request fails
        """
        payload = {
            "action": action,
            "version": 6,
            "params": params
        }

        response = await self.client.post(self.url, json=payload)
        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            raise AnkiConnectError(f"AnkiConnect error: {data['error']}")

        return data.get("result")

    # Health and info methods

    async def version(self) -> int:
        """Get AnkiConnect version."""
        return await self._invoke("version")

    async def deck_names(self) -> list[str]:
        """Get all deck names."""
        return await self._invoke("deckNames")

    async def model_names(self) -> list[str]:
        """Get all note type (model) names."""
        return await self._invoke("modelNames")

    async def model_field_names(self, model_name: str) -> list[str]:
        """
        Get field names for a specific note type.

        Args:
            model_name: Name of the note type

        Returns:
            List of field names
        """
        return await self._invoke("modelFieldNames", modelName=model_name)

    async def get_tags(self) -> list[str]:
        """Get all tags used in the collection."""
        return await self._invoke("getTags")

    # Deck operations

    async def create_deck(self, deck_name: str) -> int:
        """
        Create a new deck.

        Args:
            deck_name: Name of the deck to create

        Returns:
            Deck ID
        """
        return await self._invoke("createDeck", deck=deck_name)

    # Note operations

    async def add_note(
        self,
        deck_name: str,
        model_name: str,
        fields: dict[str, str],
        tags: list[str] | None = None
    ) -> int | None:
        """
        Add a single note to Anki.

        Args:
            deck_name: Target deck name
            model_name: Note type name (e.g., "Basic", "Cloze")
            fields: Dictionary of field names to values
            tags: Optional list of tags

        Returns:
            Note ID if successful, None if duplicate
        """
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            "tags": tags or []
        }

        return await self._invoke("addNote", note=note)

    async def add_notes(self, notes: list[dict]) -> list[int | None]:
        """
        Add multiple notes to Anki.

        Args:
            notes: List of note dictionaries (each with deckName, modelName, fields, tags)

        Returns:
            List of note IDs (None for duplicates/failures)
        """
        return await self._invoke("addNotes", notes=notes)

    async def can_add_notes(self, notes: list[dict]) -> list[bool]:
        """
        Check if notes can be added (duplicate detection).

        Args:
            notes: List of note dictionaries

        Returns:
            List of booleans indicating if each note can be added
        """
        return await self._invoke("canAddNotes", notes=notes)

    async def find_notes(self, query: str) -> list[int]:
        """
        Search for notes using Anki search syntax.

        Args:
            query: Anki search query (e.g., "deck:Spanish tag:verb")

        Returns:
            List of note IDs matching the query
        """
        return await self._invoke("findNotes", query=query)

    async def notes_info(self, note_ids: list[int]) -> list[dict]:
        """
        Get detailed information about specific notes.

        Args:
            note_ids: List of note IDs

        Returns:
            List of note information dictionaries
        """
        return await self._invoke("notesInfo", notes=note_ids)

    async def add_tags(self, note_ids: list[int], tags: str) -> None:
        """
        Add tags to existing notes.

        Args:
            note_ids: List of note IDs
            tags: Space-separated tag string
        """
        await self._invoke("addTags", notes=note_ids, tags=tags)

    # Sync operations

    async def sync(self) -> None:
        """Synchronize the collection with AnkiWeb."""
        await self._invoke("sync")

    # GUI operations

    async def gui_add_cards(self) -> None:
        """Open the Add Cards dialog in Anki."""
        await self._invoke("guiAddCards")

    # Statistics and card info methods

    async def get_deck_stats(self, deck_names: list[str]) -> dict:
        """
        Get statistics for specified decks.

        Args:
            deck_names: List of deck names to get stats for

        Returns:
            Dictionary with deck IDs as keys and stats as values.
            Each stats dict contains: new_count, learn_count, review_count, total_in_deck
        """
        return await self._invoke("getDeckStats", decks=deck_names)

    async def get_num_cards_reviewed_today(self) -> int:
        """Get the number of cards reviewed today."""
        return await self._invoke("getNumCardsReviewedToday")

    async def get_num_cards_reviewed_by_day(self) -> list[list]:
        """
        Get review counts by day.

        Returns:
            List of [days_ago, review_count] pairs
        """
        return await self._invoke("getNumCardsReviewedByDay")

    async def get_collection_stats_html(self, whole_collection: bool = True) -> str:
        """
        Get collection statistics as HTML.

        Args:
            whole_collection: If True, get stats for whole collection; otherwise current deck

        Returns:
            HTML string with statistics
        """
        return await self._invoke("getCollectionStatsHTML", wholeCollection=whole_collection)

    async def find_cards(self, query: str) -> list[int]:
        """
        Search for cards using Anki search syntax.

        Args:
            query: Anki search query (e.g., "deck:Spanish is:due")

        Returns:
            List of card IDs matching the query
        """
        return await self._invoke("findCards", query=query)

    async def cards_info(self, card_ids: list[int]) -> list[dict]:
        """
        Get detailed information about specific cards.

        Args:
            card_ids: List of card IDs

        Returns:
            List of card information dictionaries containing fields like:
            cardId, deckName, due, factor, interval, lapses, queue, type, etc.
        """
        return await self._invoke("cardsInfo", cards=card_ids)

    async def get_intervals(self, card_ids: list[int], complete: bool = False) -> list:
        """
        Get intervals for cards.

        Args:
            card_ids: List of card IDs
            complete: If True, return all historical intervals; if False, just current

        Returns:
            List of intervals (or list of interval lists if complete=True)
        """
        return await self._invoke("getIntervals", cards=card_ids, complete=complete)

    # Phase 2: Card state management methods

    async def suspend(self, card_ids: list[int]) -> bool:
        """
        Suspend cards by ID.

        Args:
            card_ids: List of card IDs to suspend

        Returns:
            True if successful
        """
        return await self._invoke("suspend", cards=card_ids)

    async def unsuspend(self, card_ids: list[int]) -> bool:
        """
        Unsuspend cards by ID.

        Args:
            card_ids: List of card IDs to unsuspend

        Returns:
            True if successful
        """
        return await self._invoke("unsuspend", cards=card_ids)

    async def are_suspended(self, card_ids: list[int]) -> list[bool]:
        """
        Check if cards are suspended.

        Args:
            card_ids: List of card IDs to check

        Returns:
            List of booleans indicating suspension status
        """
        return await self._invoke("areSuspended", cards=card_ids)

    async def are_buried(self, card_ids: list[int]) -> list[bool]:
        """
        Check if cards are buried.

        Args:
            card_ids: List of card IDs to check

        Returns:
            List of booleans indicating burial status
        """
        return await self._invoke("areBuried", cards=card_ids)

    # Phase 3: Content management methods

    async def update_note_fields(self, note_id: int, fields: dict[str, str]) -> None:
        """
        Update fields on an existing note.

        Args:
            note_id: ID of the note to update
            fields: Dictionary of field names to new values
        """
        await self._invoke("updateNoteFields", note={"id": note_id, "fields": fields})

    async def delete_notes(self, note_ids: list[int]) -> None:
        """
        Delete notes by ID. Also deletes associated cards.

        Args:
            note_ids: List of note IDs to delete
        """
        await self._invoke("deleteNotes", notes=note_ids)

    async def change_deck(self, card_ids: list[int], deck_name: str) -> None:
        """
        Move cards to a different deck.

        Args:
            card_ids: List of card IDs to move
            deck_name: Target deck name
        """
        await self._invoke("changeDeck", cards=card_ids, deck=deck_name)

    async def remove_tags(self, note_ids: list[int], tags: str) -> None:
        """
        Remove tags from notes.

        Args:
            note_ids: List of note IDs
            tags: Space-separated tag string to remove
        """
        await self._invoke("removeTags", notes=note_ids, tags=tags)

    # Phase 4: Scheduling methods

    async def forget_cards(self, card_ids: list[int]) -> None:
        """
        Reset cards to new state, removing all review history.

        Args:
            card_ids: List of card IDs to reset
        """
        await self._invoke("forgetCards", cards=card_ids)

    async def set_ease_factors(self, card_ids: list[int], ease_factors: list[int]) -> list[bool]:
        """
        Set ease factors for cards.

        Args:
            card_ids: List of card IDs
            ease_factors: List of ease factors in permille (e.g., 2500 = 250%)

        Returns:
            List of booleans indicating success for each card
        """
        return await self._invoke("setEaseFactors", cards=card_ids, easeFactors=ease_factors)

    async def get_ease_factors(self, card_ids: list[int]) -> list[int]:
        """
        Get ease factors for cards.

        Args:
            card_ids: List of card IDs

        Returns:
            List of ease factors in permille
        """
        return await self._invoke("getEaseFactors", cards=card_ids)

    # Tier 3: Study analytics methods

    async def get_card_reviews(self, deck_name: str, start_id: int = 0) -> list[dict]:
        """
        Get review history for cards in a deck.

        Args:
            deck_name: Name of the deck
            start_id: Starting review ID (0 for all reviews)

        Returns:
            List of review records with id, usn, ease, ivl, lastIvl, factor, time, type
        """
        return await self._invoke("cardReviews", deck=deck_name, startID=start_id)

    async def get_latest_review_id(self, deck_name: str) -> int:
        """
        Get the latest review ID for a deck.

        Args:
            deck_name: Name of the deck

        Returns:
            The latest review ID
        """
        return await self._invoke("getLatestReviewID", deck=deck_name)
