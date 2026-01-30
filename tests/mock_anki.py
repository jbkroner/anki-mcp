"""Mock AnkiConnect server for testing without a real Anki instance."""

import json
from dataclasses import dataclass, field
from typing import Any
import asyncio
from aiohttp import web


@dataclass
class MockNote:
    """Represents a note in the mock Anki collection."""
    note_id: int
    deck_name: str
    model_name: str
    fields: dict[str, str]
    tags: list[str]


@dataclass
class MockCard:
    """Represents a card in the mock Anki collection."""
    card_id: int
    note_id: int
    deck_name: str
    question: str
    answer: str
    factor: int = 2500  # Ease factor in permille (2500 = 250%)
    interval: int = 0
    lapses: int = 0
    queue: int = 0  # 0=new, 1=learning, 2=review
    type: int = 0
    due: int = 0
    suspended: bool = False
    buried: bool = False


@dataclass
class MockAnkiState:
    """In-memory state for mock Anki."""
    decks: dict[str, int] = field(default_factory=lambda: {"Default": 1})
    models: dict[str, list[str]] = field(default_factory=lambda: {
        "Basic": ["Front", "Back"],
        "Cloze": ["Text", "Extra"],
        "Basic (and reversed card)": ["Front", "Back"],
    })
    notes: dict[int, MockNote] = field(default_factory=dict)
    cards: dict[int, MockCard] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    next_note_id: int = 1000000000
    next_card_id: int = 1000000000
    next_deck_id: int = 100
    reviews_today: int = 5
    reviews_by_day: list[list[int]] = field(default_factory=lambda: [
        [0, 10], [1, 15], [2, 8], [3, 12], [4, 20], [5, 5], [6, 18]
    ])


class MockAnkiConnect:
    """Mock AnkiConnect server that simulates the AnkiConnect API."""

    def __init__(self):
        self.state = MockAnkiState()
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self.port: int = 0

    async def start(self, port: int = 0) -> int:
        """Start the mock server on the given port (0 for random available port)."""
        self._app = web.Application()
        self._app.router.add_post("/", self._handle_request)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, "127.0.0.1", port)
        await self._site.start()

        # Get the actual port if we requested port 0
        self.port = self._site._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self):
        """Stop the mock server."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

    async def _handle_request(self, request: web.Request) -> web.Response:
        """Handle incoming AnkiConnect requests."""
        try:
            data = await request.json()
            action = data.get("action")
            params = data.get("params", {})
            version = data.get("version", 6)

            result, error = self._dispatch(action, params)

            response = {"result": result, "error": error}
            return web.json_response(response)

        except Exception as e:
            return web.json_response({"result": None, "error": str(e)})

    def _dispatch(self, action: str, params: dict) -> tuple[Any, str | None]:
        """Dispatch an action to the appropriate handler."""
        handlers = {
            "version": self._version,
            "deckNames": self._deck_names,
            "createDeck": self._create_deck,
            "modelNames": self._model_names,
            "modelFieldNames": self._model_field_names,
            "getTags": self._get_tags,
            "addNote": self._add_note,
            "addNotes": self._add_notes,
            "canAddNotes": self._can_add_notes,
            "findNotes": self._find_notes,
            "notesInfo": self._notes_info,
            "addTags": self._add_tags,
            "sync": self._sync,
            "guiAddCards": self._gui_add_cards,
            # Statistics methods
            "getDeckStats": self._get_deck_stats,
            "getNumCardsReviewedToday": self._get_num_cards_reviewed_today,
            "getNumCardsReviewedByDay": self._get_num_cards_reviewed_by_day,
            "getCollectionStatsHTML": self._get_collection_stats_html,
            "findCards": self._find_cards,
            "cardsInfo": self._cards_info,
            "getIntervals": self._get_intervals,
            # Phase 2: Card state management
            "suspend": self._suspend,
            "unsuspend": self._unsuspend,
            "areSuspended": self._are_suspended,
            "areBuried": self._are_buried,
            # Phase 3: Content management
            "updateNoteFields": self._update_note_fields,
            "deleteNotes": self._delete_notes,
            "changeDeck": self._change_deck,
            "removeTags": self._remove_tags,
            # Phase 4: Scheduling
            "forgetCards": self._forget_cards,
            "setEaseFactors": self._set_ease_factors,
            "getEaseFactors": self._get_ease_factors,
        }

        handler = handlers.get(action)
        if handler is None:
            return None, f"Unknown action: {action}"

        try:
            result = handler(params)
            return result, None
        except Exception as e:
            return None, str(e)

    def _version(self, params: dict) -> int:
        return 6

    def _deck_names(self, params: dict) -> list[str]:
        return list(self.state.decks.keys())

    def _create_deck(self, params: dict) -> int:
        deck_name = params["deck"]
        if deck_name not in self.state.decks:
            self.state.decks[deck_name] = self.state.next_deck_id
            self.state.next_deck_id += 1
        return self.state.decks[deck_name]

    def _model_names(self, params: dict) -> list[str]:
        return list(self.state.models.keys())

    def _model_field_names(self, params: dict) -> list[str]:
        model_name = params["modelName"]
        if model_name not in self.state.models:
            raise ValueError(f"Model not found: {model_name}")
        return self.state.models[model_name]

    def _get_tags(self, params: dict) -> list[str]:
        return list(self.state.tags)

    def _add_note(self, params: dict) -> int | None:
        note_data = params["note"]
        deck_name = note_data["deckName"]
        model_name = note_data["modelName"]
        fields = note_data["fields"]
        tags = note_data.get("tags", [])

        # Check for duplicates (based on first field)
        first_field_value = list(fields.values())[0] if fields else ""
        for existing_note in self.state.notes.values():
            existing_first = list(existing_note.fields.values())[0] if existing_note.fields else ""
            if existing_first == first_field_value and existing_note.deck_name == deck_name:
                return None  # Duplicate

        # Create the note
        note_id = self.state.next_note_id
        self.state.next_note_id += 1

        note = MockNote(
            note_id=note_id,
            deck_name=deck_name,
            model_name=model_name,
            fields=fields,
            tags=tags
        )
        self.state.notes[note_id] = note

        # Add tags to global tags
        self.state.tags.update(tags)

        # Create a card for the note
        card_id = self.state.next_card_id
        self.state.next_card_id += 1

        # Get question/answer from fields
        field_names = self.state.models.get(model_name, ["Front", "Back"])
        question = fields.get(field_names[0], "") if field_names else ""
        answer = fields.get(field_names[1], "") if len(field_names) > 1 else ""

        card = MockCard(
            card_id=card_id,
            note_id=note_id,
            deck_name=deck_name,
            question=question,
            answer=answer
        )
        self.state.cards[card_id] = card

        # Ensure deck exists
        if deck_name not in self.state.decks:
            self._create_deck({"deck": deck_name})

        return note_id

    def _add_notes(self, params: dict) -> list[int | None]:
        notes = params["notes"]
        results = []
        for note_data in notes:
            result = self._add_note({"note": note_data})
            results.append(result)
        return results

    def _can_add_notes(self, params: dict) -> list[bool]:
        notes = params["notes"]
        results = []
        for note_data in notes:
            # Check if note would be a duplicate
            fields = note_data["fields"]
            deck_name = note_data["deckName"]
            first_field_value = list(fields.values())[0] if fields else ""

            is_duplicate = False
            for existing_note in self.state.notes.values():
                existing_first = list(existing_note.fields.values())[0] if existing_note.fields else ""
                if existing_first == first_field_value and existing_note.deck_name == deck_name:
                    is_duplicate = True
                    break

            results.append(not is_duplicate)
        return results

    def _find_notes(self, params: dict) -> list[int]:
        query = params["query"]
        results = []

        for note_id, note in self.state.notes.items():
            if self._note_matches_query(note, query):
                results.append(note_id)

        return results

    def _note_matches_query(self, note: MockNote, query: str) -> bool:
        """Simple query matching for testing."""
        query = query.lower()

        # Handle deck: queries
        if "deck:" in query:
            # Extract deck name, handling quotes
            import re
            deck_match = re.search(r'deck:"([^"]+)"|deck:(\S+)', query)
            if deck_match:
                deck_name = deck_match.group(1) or deck_match.group(2)
                if note.deck_name.lower() != deck_name.lower():
                    return False

        # Handle tag: queries
        if "tag:" in query:
            import re
            tag_match = re.search(r'tag:(\S+)', query)
            if tag_match:
                tag = tag_match.group(1)
                if tag.lower() not in [t.lower() for t in note.tags]:
                    return False

        return True

    def _notes_info(self, params: dict) -> list[dict]:
        note_ids = params["notes"]
        results = []

        for note_id in note_ids:
            note = self.state.notes.get(note_id)
            if note:
                results.append({
                    "noteId": note.note_id,
                    "modelName": note.model_name,
                    "tags": note.tags,
                    "fields": {k: {"value": v, "order": i} for i, (k, v) in enumerate(note.fields.items())},
                })

        return results

    def _add_tags(self, params: dict) -> None:
        note_ids = params["notes"]
        tags_str = params["tags"]
        new_tags = tags_str.split()

        for note_id in note_ids:
            if note_id in self.state.notes:
                self.state.notes[note_id].tags.extend(new_tags)
                self.state.tags.update(new_tags)

    def _sync(self, params: dict) -> None:
        pass  # No-op for mock

    def _gui_add_cards(self, params: dict) -> None:
        pass  # No-op for mock

    # Statistics methods

    def _get_deck_stats(self, params: dict) -> dict:
        deck_names = params["decks"]
        results = {}

        for deck_name in deck_names:
            if deck_name in self.state.decks:
                deck_id = self.state.decks[deck_name]
                # Count cards in this deck
                deck_cards = [c for c in self.state.cards.values() if c.deck_name == deck_name]
                new_count = sum(1 for c in deck_cards if c.queue == 0)
                learn_count = sum(1 for c in deck_cards if c.queue == 1)
                review_count = sum(1 for c in deck_cards if c.queue == 2)

                results[str(deck_id)] = {
                    "deck_id": deck_id,
                    "name": deck_name,
                    "new_count": new_count,
                    "learn_count": learn_count,
                    "review_count": review_count,
                    "total_in_deck": len(deck_cards)
                }

        return results

    def _get_num_cards_reviewed_today(self, params: dict) -> int:
        return self.state.reviews_today

    def _get_num_cards_reviewed_by_day(self, params: dict) -> list[list[int]]:
        return self.state.reviews_by_day

    def _get_collection_stats_html(self, params: dict) -> str:
        return "<html><body>Mock stats</body></html>"

    def _find_cards(self, params: dict) -> list[int]:
        query = params["query"]
        results = []

        for card_id, card in self.state.cards.items():
            if self._card_matches_query(card, query):
                results.append(card_id)

        return results

    def _card_matches_query(self, card: MockCard, query: str) -> bool:
        """Simple query matching for cards."""
        query_lower = query.lower()

        # Handle deck: queries
        if "deck:" in query_lower:
            import re
            deck_match = re.search(r'deck:"([^"]+)"|deck:(\S+)', query, re.IGNORECASE)
            if deck_match:
                deck_name = deck_match.group(1) or deck_match.group(2)
                if card.deck_name.lower() != deck_name.lower():
                    return False

        # Handle tag: queries (need to look up the note)
        if "tag:" in query_lower:
            import re
            tag_match = re.search(r'tag:(\S+)', query, re.IGNORECASE)
            if tag_match:
                tag = tag_match.group(1)
                note = self.state.notes.get(card.note_id)
                if note and tag.lower() not in [t.lower() for t in note.tags]:
                    return False

        # Handle prop:ease queries
        if "prop:ease<" in query_lower:
            import re
            ease_match = re.search(r'prop:ease<(\d+\.?\d*)', query_lower)
            if ease_match:
                threshold = float(ease_match.group(1))
                ease = card.factor / 1000  # Convert from permille
                if ease >= threshold:
                    return False

        # Handle prop:lapses queries
        if "prop:lapses>=" in query_lower:
            import re
            lapses_match = re.search(r'prop:lapses>=(\d+)', query_lower)
            if lapses_match:
                threshold = int(lapses_match.group(1))
                if card.lapses < threshold:
                    return False

        # Handle is:suspended
        if "is:suspended" in query_lower:
            if not card.suspended:
                return False

        # Handle is:buried
        if "is:buried" in query_lower:
            if not card.buried:
                return False

        # Handle is:due (cards in review queue with due <= 0)
        if "is:due" in query_lower:
            if card.queue != 2 or card.due > 0:
                return False

        return True

    def _cards_info(self, params: dict) -> list[dict]:
        card_ids = params["cards"]
        results = []

        for card_id in card_ids:
            card = self.state.cards.get(card_id)
            if card:
                note = self.state.notes.get(card.note_id)
                results.append({
                    "cardId": card.card_id,
                    "note": card.note_id,
                    "deckName": card.deck_name,
                    "question": card.question,
                    "answer": card.answer,
                    "factor": card.factor,
                    "interval": card.interval,
                    "lapses": card.lapses,
                    "queue": card.queue,
                    "type": card.type,
                    "due": card.due,
                    "modelName": note.model_name if note else "Basic",
                })

        return results

    def _get_intervals(self, params: dict) -> list[int]:
        card_ids = params["cards"]
        complete = params.get("complete", False)

        results = []
        for card_id in card_ids:
            card = self.state.cards.get(card_id)
            if card:
                if complete:
                    results.append([card.interval])  # Return as list for complete mode
                else:
                    results.append(card.interval)
            else:
                results.append(0 if not complete else [0])

        return results

    # Phase 2: Card state management methods

    def _suspend(self, params: dict) -> bool:
        card_ids = params["cards"]
        for card_id in card_ids:
            if card_id in self.state.cards:
                self.state.cards[card_id].suspended = True
        return True

    def _unsuspend(self, params: dict) -> bool:
        card_ids = params["cards"]
        for card_id in card_ids:
            if card_id in self.state.cards:
                self.state.cards[card_id].suspended = False
        return True

    def _are_suspended(self, params: dict) -> list[bool]:
        card_ids = params["cards"]
        return [
            self.state.cards[cid].suspended if cid in self.state.cards else False
            for cid in card_ids
        ]

    def _are_buried(self, params: dict) -> list[bool]:
        card_ids = params["cards"]
        return [
            self.state.cards[cid].buried if cid in self.state.cards else False
            for cid in card_ids
        ]

    # Phase 3: Content management methods

    def _update_note_fields(self, params: dict) -> None:
        note_data = params["note"]
        note_id = note_data["id"]
        fields = note_data["fields"]

        if note_id in self.state.notes:
            self.state.notes[note_id].fields.update(fields)
            # Update card question/answer if Front/Back changed
            for card in self.state.cards.values():
                if card.note_id == note_id:
                    if "Front" in fields:
                        card.question = fields["Front"]
                    if "Back" in fields:
                        card.answer = fields["Back"]

    def _delete_notes(self, params: dict) -> None:
        note_ids = params["notes"]
        for note_id in note_ids:
            if note_id in self.state.notes:
                del self.state.notes[note_id]
            # Also delete associated cards
            cards_to_delete = [
                cid for cid, card in self.state.cards.items()
                if card.note_id == note_id
            ]
            for card_id in cards_to_delete:
                del self.state.cards[card_id]

    def _change_deck(self, params: dict) -> None:
        card_ids = params["cards"]
        deck_name = params["deck"]

        # Ensure deck exists
        if deck_name not in self.state.decks:
            self._create_deck({"deck": deck_name})

        for card_id in card_ids:
            if card_id in self.state.cards:
                self.state.cards[card_id].deck_name = deck_name

    def _remove_tags(self, params: dict) -> None:
        note_ids = params["notes"]
        tags_str = params["tags"]
        tags_to_remove = set(tags_str.split())

        for note_id in note_ids:
            if note_id in self.state.notes:
                self.state.notes[note_id].tags = [
                    t for t in self.state.notes[note_id].tags
                    if t not in tags_to_remove
                ]

    # Phase 4: Scheduling methods

    def _forget_cards(self, params: dict) -> None:
        card_ids = params["cards"]
        for card_id in card_ids:
            if card_id in self.state.cards:
                card = self.state.cards[card_id]
                card.queue = 0  # New
                card.type = 0
                card.interval = 0
                card.factor = 2500  # Reset to default ease
                card.lapses = 0
                card.due = 0

    def _set_ease_factors(self, params: dict) -> list[bool]:
        card_ids = params["cards"]
        ease_factors = params["easeFactors"]
        results = []

        for card_id, ease in zip(card_ids, ease_factors):
            if card_id in self.state.cards:
                self.state.cards[card_id].factor = ease
                results.append(True)
            else:
                results.append(False)

        return results

    def _get_ease_factors(self, params: dict) -> list[int]:
        card_ids = params["cards"]
        return [
            self.state.cards[cid].factor if cid in self.state.cards else 0
            for cid in card_ids
        ]

    # Helper methods for test setup

    def add_problem_card(self, deck_name: str, low_ease: bool = False, high_lapses: bool = False):
        """Add a card with problem characteristics for testing."""
        # Ensure deck exists
        self._create_deck({"deck": deck_name})

        note_id = self.state.next_note_id
        self.state.next_note_id += 1

        note = MockNote(
            note_id=note_id,
            deck_name=deck_name,
            model_name="Basic",
            fields={"Front": f"Problem Q {note_id}", "Back": f"Problem A {note_id}"},
            tags=["problem-card"]
        )
        self.state.notes[note_id] = note

        card_id = self.state.next_card_id
        self.state.next_card_id += 1

        card = MockCard(
            card_id=card_id,
            note_id=note_id,
            deck_name=deck_name,
            question=f"Problem Q {note_id}",
            answer=f"Problem A {note_id}",
            factor=1500 if low_ease else 2500,  # Low ease = 150%, normal = 250%
            lapses=5 if high_lapses else 0,
            interval=10,
            queue=2  # Review queue
        )
        self.state.cards[card_id] = card

        return card_id

    def add_due_card(self, deck_name: str) -> int:
        """Add a card that is due for review."""
        self._create_deck({"deck": deck_name})

        note_id = self.state.next_note_id
        self.state.next_note_id += 1

        note = MockNote(
            note_id=note_id,
            deck_name=deck_name,
            model_name="Basic",
            fields={"Front": f"Due Q {note_id}", "Back": f"Due A {note_id}"},
            tags=["due-card"]
        )
        self.state.notes[note_id] = note

        card_id = self.state.next_card_id
        self.state.next_card_id += 1

        card = MockCard(
            card_id=card_id,
            note_id=note_id,
            deck_name=deck_name,
            question=f"Due Q {note_id}",
            answer=f"Due A {note_id}",
            factor=2500,
            lapses=0,
            interval=10,
            queue=2,  # Review queue
            due=0  # Due now (0 or negative means due)
        )
        self.state.cards[card_id] = card

        return card_id

    def add_suspended_card(self, deck_name: str) -> int:
        """Add a suspended card for testing."""
        self._create_deck({"deck": deck_name})

        note_id = self.state.next_note_id
        self.state.next_note_id += 1

        note = MockNote(
            note_id=note_id,
            deck_name=deck_name,
            model_name="Basic",
            fields={"Front": f"Suspended Q {note_id}", "Back": f"Suspended A {note_id}"},
            tags=["suspended-card"]
        )
        self.state.notes[note_id] = note

        card_id = self.state.next_card_id
        self.state.next_card_id += 1

        card = MockCard(
            card_id=card_id,
            note_id=note_id,
            deck_name=deck_name,
            question=f"Suspended Q {note_id}",
            answer=f"Suspended A {note_id}",
            suspended=True
        )
        self.state.cards[card_id] = card

        return card_id
