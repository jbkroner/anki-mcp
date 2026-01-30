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
