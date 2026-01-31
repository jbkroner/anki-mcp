"""MCP server for Anki integration."""

import asyncio
import re
from datetime import datetime
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .anki_client import AnkiClient, AnkiConnectError


# Initialize the MCP server
app = Server("anki-mcp")

# Global AnkiClient instance
anki = AnkiClient()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="anki_health_check",
            description="Check if Anki is running with AnkiConnect enabled. Returns the AnkiConnect version.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_decks",
            description="List all Anki deck names.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_note_types",
            description="List all note types (models) and their fields.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="add_flashcard",
            description="Add a single flashcard to Anki. Creates the deck if it doesn't exist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Target deck name (created if doesn't exist)"
                    },
                    "front": {
                        "type": "string",
                        "description": "Front of card (question/prompt)"
                    },
                    "back": {
                        "type": "string",
                        "description": "Back of card (answer)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of tags",
                        "default": []
                    },
                    "model": {
                        "type": "string",
                        "description": "Note type (default: Basic)",
                        "default": "Basic"
                    }
                },
                "required": ["deck", "front", "back"]
            }
        ),
        Tool(
            name="add_flashcards_batch",
            description="Add multiple flashcards in one operation. Much faster than adding one at a time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Target deck name"
                    },
                    "cards": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "front": {"type": "string"},
                                "back": {"type": "string"},
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "default": []
                                }
                            },
                            "required": ["front", "back"]
                        },
                        "description": "List of cards with front, back, and optional tags"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags applied to all cards",
                        "default": []
                    },
                    "model": {
                        "type": "string",
                        "description": "Note type (default: Basic)",
                        "default": "Basic"
                    }
                },
                "required": ["deck", "cards"]
            }
        ),
        Tool(
            name="search_notes",
            description="Search Anki notes using Anki's search syntax (e.g., 'deck:Spanish tag:verb').",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Anki search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="add_cloze_card",
            description="Add a cloze deletion card. Text should contain {{c1::deletions}} markup.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Target deck name"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text with {{c1::deletions}} marked"
                    },
                    "extra": {
                        "type": "string",
                        "description": "Additional context shown on back",
                        "default": ""
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags",
                        "default": []
                    }
                },
                "required": ["deck", "text"]
            }
        ),
        Tool(
            name="sync_anki",
            description="Synchronize the local Anki collection with AnkiWeb.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        # Statistics tools
        Tool(
            name="get_deck_stats",
            description="Get statistics for a deck including new, learning, and review card counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Deck name to get statistics for"
                    }
                },
                "required": ["deck"]
            }
        ),
        Tool(
            name="get_collection_stats",
            description="Get overall collection statistics including cards reviewed today and review history.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_problem_cards",
            description="Find cards that may need attention: low ease factor, high lapse count, or long intervals. Useful for identifying struggling cards.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Optional deck name to filter. Searches all decks if not specified."
                    },
                    "criteria": {
                        "type": "string",
                        "enum": ["low_ease", "high_lapses", "all"],
                        "description": "Type of problem cards to find. 'low_ease' finds cards with ease < 2.0, 'high_lapses' finds cards with 4+ lapses, 'all' finds both.",
                        "default": "all"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of cards to return (default: 20)",
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        # Phase 2: Card state management tools
        Tool(
            name="suspend_cards",
            description="Suspend cards to exclude them from reviews. Suspended cards won't appear in study sessions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "card_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of card IDs to suspend"
                    },
                    "query": {
                        "type": "string",
                        "description": "Anki search query to find cards to suspend (alternative to card_ids)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="unsuspend_cards",
            description="Unsuspend cards to include them in reviews again.",
            inputSchema={
                "type": "object",
                "properties": {
                    "card_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of card IDs to unsuspend"
                    },
                    "query": {
                        "type": "string",
                        "description": "Anki search query to find cards to unsuspend (alternative to card_ids)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_suspended_cards",
            description="List all suspended cards, optionally filtered by deck.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Optional deck name to filter results"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum cards to return (default: 50)",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        # Phase 3: Content management tools
        Tool(
            name="update_note",
            description="Update the content of an existing note's fields.",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "integer",
                        "description": "The note ID to update"
                    },
                    "fields": {
                        "type": "object",
                        "description": "Dictionary of field names to new values (e.g., {'Front': 'new question', 'Back': 'new answer'})"
                    }
                },
                "required": ["note_id", "fields"]
            }
        ),
        Tool(
            name="delete_notes",
            description="Permanently delete notes and all their associated cards. This action cannot be undone!",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of note IDs to delete"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to confirm deletion"
                    }
                },
                "required": ["note_ids", "confirm"]
            }
        ),
        Tool(
            name="move_cards",
            description="Move cards to a different deck.",
            inputSchema={
                "type": "object",
                "properties": {
                    "card_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of card IDs to move"
                    },
                    "query": {
                        "type": "string",
                        "description": "Anki search query to find cards to move (alternative to card_ids)"
                    },
                    "target_deck": {
                        "type": "string",
                        "description": "Destination deck name"
                    }
                },
                "required": ["target_deck"]
            }
        ),
        Tool(
            name="remove_tags",
            description="Remove tags from notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of note IDs"
                    },
                    "query": {
                        "type": "string",
                        "description": "Anki search query to find notes (alternative to note_ids)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags to remove"
                    }
                },
                "required": ["tags"]
            }
        ),
        # Phase 4: Scheduling and bulk operations
        Tool(
            name="get_due_cards",
            description="Find cards that are due for review.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Optional deck name to filter"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum cards to return (default: 50)",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="reset_card_progress",
            description="Reset cards to 'new' state, removing all review history. Useful for relearning material.",
            inputSchema={
                "type": "object",
                "properties": {
                    "card_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of card IDs to reset"
                    },
                    "query": {
                        "type": "string",
                        "description": "Anki search query to find cards to reset (alternative to card_ids)"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to confirm reset"
                    }
                },
                "required": ["confirm"]
            }
        ),
        Tool(
            name="set_ease_factor",
            description="Adjust the ease factor for cards. Higher ease = longer intervals between reviews.",
            inputSchema={
                "type": "object",
                "properties": {
                    "card_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of card IDs"
                    },
                    "ease": {
                        "type": "integer",
                        "description": "New ease factor in permille (e.g., 2500 = 250%). Range: 1300-5000 recommended."
                    }
                },
                "required": ["card_ids", "ease"]
            }
        ),
        # Tier 3: Study analytics tools
        Tool(
            name="get_review_history",
            description="Get review history for a deck showing recent reviews and their outcomes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Deck name to get review history for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of reviews to return (default: 100)",
                        "default": 100
                    }
                },
                "required": ["deck"]
            }
        ),
        Tool(
            name="get_retention_stats",
            description="Calculate retention metrics for a deck based on review history. Shows success rate and lapse patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck": {
                        "type": "string",
                        "description": "Optional deck name to filter. Analyzes all decks if not specified."
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 30)",
                        "default": 30
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_study_streak",
            description="Calculate your study streak - consecutive days with at least one review.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_learning_curve",
            description="Analyze learning progress over time showing review counts, retention, and workload trends.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 30)",
                        "default": 30
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_card_stats",
            description="Get detailed statistics for specific cards matching a search query. Returns comprehensive data including ease factor, interval, lapses, review count, and card content. Useful for debugging difficult cards or investigating specific vocabulary struggles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Anki search query to find cards (e.g., 'deck:Spanish', 'tag:verb', 'front:*hello*')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of cards to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "anki_health_check":
            version = await anki.version()
            return [TextContent(
                type="text",
                text=f"✓ Anki is running with AnkiConnect version {version}"
            )]

        elif name == "list_decks":
            decks = await anki.deck_names()
            deck_list = "\n".join(f"- {deck}" for deck in sorted(decks))
            return [TextContent(
                type="text",
                text=f"Found {len(decks)} decks:\n{deck_list}"
            )]

        elif name == "list_note_types":
            models = await anki.model_names()
            result_parts = [f"Found {len(models)} note types:\n"]

            for model in sorted(models):
                fields = await anki.model_field_names(model)
                fields_str = ", ".join(fields)
                result_parts.append(f"- {model}: [{fields_str}]")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "add_flashcard":
            deck = arguments["deck"]
            front = arguments["front"]
            back = arguments["back"]
            tags = arguments.get("tags", [])
            model = arguments.get("model", "Basic")

            # Ensure deck exists
            try:
                await anki.create_deck(deck)
            except AnkiConnectError:
                pass  # Deck already exists

            # Add the note
            fields = {"Front": front, "Back": back}
            note_id = await anki.add_note(deck, model, fields, tags)

            if note_id:
                tags_str = f" (tags: {', '.join(tags)})" if tags else ""
                return [TextContent(
                    type="text",
                    text=f"✓ Added flashcard to '{deck}'{tags_str}\nNote ID: {note_id}"
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"⚠ Duplicate card not added (already exists in '{deck}')"
                )]

        elif name == "add_flashcards_batch":
            deck = arguments["deck"]
            cards = arguments["cards"]
            global_tags = arguments.get("tags", [])
            model = arguments.get("model", "Basic")

            # Ensure deck exists
            try:
                await anki.create_deck(deck)
            except AnkiConnectError:
                pass  # Deck already exists

            # Build notes list
            notes = []
            for card in cards:
                card_tags = list(set(global_tags + card.get("tags", [])))
                note = {
                    "deckName": deck,
                    "modelName": model,
                    "fields": {
                        "Front": card["front"],
                        "Back": card["back"]
                    },
                    "tags": card_tags
                }
                notes.append(note)

            # Add all notes
            note_ids = await anki.add_notes(notes)

            # Count results
            added = sum(1 for nid in note_ids if nid is not None)
            duplicates = sum(1 for nid in note_ids if nid is None)

            result_parts = [
                f"✓ Batch add to '{deck}' complete:",
                f"  - Added: {added}",
                f"  - Duplicates skipped: {duplicates}",
                f"  - Total: {len(cards)}"
            ]

            if global_tags:
                result_parts.append(f"  - Tags: {', '.join(global_tags)}")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "search_notes":
            query = arguments["query"]
            limit = arguments.get("limit", 20)

            # Find notes
            note_ids = await anki.find_notes(query)

            if not note_ids:
                return [TextContent(
                    type="text",
                    text=f"No notes found matching: {query}"
                )]

            # Limit results
            note_ids = note_ids[:limit]

            # Get note details
            notes = await anki.notes_info(note_ids)

            # Format results
            result_parts = [f"Found {len(notes)} notes (showing up to {limit}):\n"]

            for note in notes:
                fields = note.get("fields", {})
                tags = note.get("tags", [])
                note_id = note.get("noteId")

                # Get field values
                field_values = [f"{k}: {v.get('value', '')[:50]}" for k, v in fields.items()]
                fields_str = " | ".join(field_values)

                tags_str = f" [{', '.join(tags)}]" if tags else ""
                result_parts.append(f"- ID {note_id}: {fields_str}{tags_str}")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "add_cloze_card":
            deck = arguments["deck"]
            text = arguments["text"]
            extra = arguments.get("extra", "")
            tags = arguments.get("tags", [])

            # Ensure deck exists
            try:
                await anki.create_deck(deck)
            except AnkiConnectError:
                pass  # Deck already exists

            # Add the cloze note
            fields = {"Text": text, "Extra": extra}
            note_id = await anki.add_note(deck, "Cloze", fields, tags)

            if note_id:
                tags_str = f" (tags: {', '.join(tags)})" if tags else ""
                return [TextContent(
                    type="text",
                    text=f"✓ Added cloze card to '{deck}'{tags_str}\nNote ID: {note_id}\nText: {text}"
                )]
            else:
                return [TextContent(
                    type="text",
                    text=f"⚠ Duplicate cloze card not added (already exists in '{deck}')"
                )]

        elif name == "sync_anki":
            await anki.sync()
            return [TextContent(
                type="text",
                text="✓ Anki collection synchronized with AnkiWeb"
            )]

        elif name == "get_deck_stats":
            deck = arguments["deck"]
            stats = await anki.get_deck_stats([deck])

            if not stats:
                return [TextContent(
                    type="text",
                    text=f"No statistics found for deck '{deck}'. Use list_decks to see available decks."
                )]

            # Stats are keyed by deck ID, get the first (and only) one
            deck_stats = list(stats.values())[0]

            result_parts = [
                f"Statistics for '{deck}':",
                f"  New cards: {deck_stats.get('new_count', 0)}",
                f"  Learning: {deck_stats.get('learn_count', 0)}",
                f"  Review: {deck_stats.get('review_count', 0)}",
                f"  Total in deck: {deck_stats.get('total_in_deck', 0)}"
            ]

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "get_collection_stats":
            # Get cards reviewed today
            reviewed_today = await anki.get_num_cards_reviewed_today()

            # Get review history (last 30 days)
            review_history = await anki.get_num_cards_reviewed_by_day()

            # Get all decks and their stats
            decks = await anki.deck_names()
            all_stats = await anki.get_deck_stats(decks)

            # Calculate totals
            total_new = 0
            total_learning = 0
            total_review = 0
            total_cards = 0

            for deck_stat in all_stats.values():
                total_new += deck_stat.get('new_count', 0)
                total_learning += deck_stat.get('learn_count', 0)
                total_review += deck_stat.get('review_count', 0)
                total_cards += deck_stat.get('total_in_deck', 0)

            # Calculate recent review stats
            recent_reviews = review_history[:7] if review_history else []
            week_total = sum(day[1] for day in recent_reviews) if recent_reviews else 0
            week_avg = week_total / 7 if recent_reviews else 0

            result_parts = [
                "Collection Statistics:",
                f"  Total cards: {total_cards}",
                f"  Due today: {total_review}",
                f"  New available: {total_new}",
                f"  Currently learning: {total_learning}",
                f"",
                f"Review Activity:",
                f"  Reviewed today: {reviewed_today}",
                f"  Last 7 days: {week_total}",
                f"  Daily average (7d): {week_avg:.1f}",
                f"  Total decks: {len(decks)}"
            ]

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "get_problem_cards":
            deck = arguments.get("deck")
            criteria = arguments.get("criteria", "all")
            limit = arguments.get("limit", 20)

            # Build search query
            base_query = f'deck:"{deck}"' if deck else ""

            problem_cards = []

            # Helper function to get note field content
            async def get_note_content(note_ids: list[int]) -> dict[int, str]:
                """Fetch note info and return a mapping of note_id to field content."""
                if not note_ids:
                    return {}
                notes = await anki.notes_info(note_ids)
                content_map = {}
                for note in notes:
                    note_id = note.get('noteId')
                    fields = note.get('fields', {})
                    # Get field values (typically Front/Back for Basic cards)
                    field_values = [f"{k}: {v.get('value', '')[:50]}" for k, v in fields.items()]
                    content_map[note_id] = " | ".join(field_values)
                return content_map

            # Find cards with low ease (factor < 2000 means ease < 200% or 2.0)
            if criteria in ("low_ease", "all"):
                query = f"{base_query} prop:ease<2".strip()
                low_ease_ids = await anki.find_cards(query)
                if low_ease_ids:
                    cards_info = await anki.cards_info(low_ease_ids[:limit])
                    # Get note content for these cards
                    note_ids = [card.get('note') for card in cards_info if card.get('note')]
                    note_content = await get_note_content(note_ids)

                    for card in cards_info:
                        ease = card.get('factor', 0) / 1000  # Convert from permille
                        note_id = card.get('note')
                        problem_cards.append({
                            'card_id': card.get('cardId'),
                            'note_id': note_id,
                            'deck': card.get('deckName'),
                            'issue': 'low_ease',
                            'ease': ease,
                            'lapses': card.get('lapses', 0),
                            'interval': card.get('interval', 0),
                            'content': note_content.get(note_id, 'Unknown')[:80]
                        })

            # Find cards with high lapses (4 or more)
            if criteria in ("high_lapses", "all"):
                query = f"{base_query} prop:lapses>=4".strip()
                high_lapse_ids = await anki.find_cards(query)
                if high_lapse_ids:
                    # Avoid duplicates if we already have low_ease cards
                    existing_ids = {c['card_id'] for c in problem_cards}
                    new_ids = [cid for cid in high_lapse_ids if cid not in existing_ids]

                    if new_ids:
                        cards_info = await anki.cards_info(new_ids[:limit])
                        # Get note content for these cards
                        note_ids = [card.get('note') for card in cards_info if card.get('note')]
                        note_content = await get_note_content(note_ids)

                        for card in cards_info:
                            ease = card.get('factor', 0) / 1000
                            note_id = card.get('note')
                            problem_cards.append({
                                'card_id': card.get('cardId'),
                                'note_id': note_id,
                                'deck': card.get('deckName'),
                                'issue': 'high_lapses',
                                'ease': ease,
                                'lapses': card.get('lapses', 0),
                                'interval': card.get('interval', 0),
                                'content': note_content.get(note_id, 'Unknown')[:80]
                            })

            # Limit total results
            problem_cards = problem_cards[:limit]

            if not problem_cards:
                deck_str = f" in '{deck}'" if deck else ""
                return [TextContent(
                    type="text",
                    text=f"No problem cards found{deck_str}. Your cards are doing well!"
                )]

            # Format results
            deck_str = f" in '{deck}'" if deck else ""
            result_parts = [f"Found {len(problem_cards)} problem cards{deck_str}:\n"]

            for card in problem_cards:
                # Clean HTML from content
                content = card['content'].replace('<br>', ' ').replace('<br/>', ' ')
                # Simple HTML tag removal
                content = re.sub(r'<[^>]+>', '', content)
                content = content[:60] + "..." if len(content) > 60 else content

                issue_str = "low ease" if card['issue'] == 'low_ease' else "high lapses"
                result_parts.append(
                    f"- [{issue_str}] ease={card['ease']:.2f}, lapses={card['lapses']}, "
                    f"interval={card['interval']}d"
                )
                result_parts.append(f"  {content}")
                result_parts.append(f"  Card ID: {card['card_id']} | Deck: {card['deck']}")
                result_parts.append("")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        # Phase 2: Card state management handlers
        elif name == "suspend_cards":
            card_ids = arguments.get("card_ids", [])
            query = arguments.get("query")

            if not card_ids and not query:
                return [TextContent(
                    type="text",
                    text="Error: Must provide either 'card_ids' or 'query' parameter"
                )]

            if query:
                card_ids = await anki.find_cards(query)
                if not card_ids:
                    return [TextContent(
                        type="text",
                        text=f"No cards found matching query: {query}"
                    )]

            await anki.suspend(card_ids)
            return [TextContent(
                type="text",
                text=f"✓ Suspended {len(card_ids)} card(s)"
            )]

        elif name == "unsuspend_cards":
            card_ids = arguments.get("card_ids", [])
            query = arguments.get("query")

            if not card_ids and not query:
                return [TextContent(
                    type="text",
                    text="Error: Must provide either 'card_ids' or 'query' parameter"
                )]

            if query:
                card_ids = await anki.find_cards(query)
                if not card_ids:
                    return [TextContent(
                        type="text",
                        text=f"No cards found matching query: {query}"
                    )]

            await anki.unsuspend(card_ids)
            return [TextContent(
                type="text",
                text=f"✓ Unsuspended {len(card_ids)} card(s)"
            )]

        elif name == "get_suspended_cards":
            deck = arguments.get("deck")
            limit = arguments.get("limit", 50)

            query = "is:suspended"
            if deck:
                query = f'deck:"{deck}" is:suspended'

            card_ids = await anki.find_cards(query)

            if not card_ids:
                deck_str = f" in '{deck}'" if deck else ""
                return [TextContent(
                    type="text",
                    text=f"No suspended cards found{deck_str}."
                )]

            card_ids = card_ids[:limit]
            cards = await anki.cards_info(card_ids)

            deck_str = f" in '{deck}'" if deck else ""
            result_parts = [f"Found {len(cards)} suspended cards{deck_str}:\n"]

            for card in cards:
                question = card.get('question', '')[:60]
                question = re.sub(r'<[^>]+>', '', question)
                result_parts.append(f"- Card ID {card.get('cardId')}: {question}")
                result_parts.append(f"  Deck: {card.get('deckName')}")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        # Phase 3: Content management handlers
        elif name == "update_note":
            note_id = arguments["note_id"]
            fields = arguments["fields"]

            await anki.update_note_fields(note_id, fields)

            field_names = ", ".join(fields.keys())
            return [TextContent(
                type="text",
                text=f"✓ Updated note {note_id} (fields: {field_names})"
            )]

        elif name == "delete_notes":
            note_ids = arguments["note_ids"]
            confirm = arguments.get("confirm", False)

            if not confirm:
                return [TextContent(
                    type="text",
                    text=f"⚠ Deletion cancelled. To delete {len(note_ids)} note(s), set confirm=true.\nThis action cannot be undone!"
                )]

            await anki.delete_notes(note_ids)
            return [TextContent(
                type="text",
                text=f"✓ Deleted {len(note_ids)} note(s) and their associated cards"
            )]

        elif name == "move_cards":
            card_ids = arguments.get("card_ids", [])
            query = arguments.get("query")
            target_deck = arguments["target_deck"]

            if not card_ids and not query:
                return [TextContent(
                    type="text",
                    text="Error: Must provide either 'card_ids' or 'query' parameter"
                )]

            if query:
                card_ids = await anki.find_cards(query)
                if not card_ids:
                    return [TextContent(
                        type="text",
                        text=f"No cards found matching query: {query}"
                    )]

            # Ensure target deck exists
            try:
                await anki.create_deck(target_deck)
            except AnkiConnectError:
                pass

            await anki.change_deck(card_ids, target_deck)
            return [TextContent(
                type="text",
                text=f"✓ Moved {len(card_ids)} card(s) to '{target_deck}'"
            )]

        elif name == "remove_tags":
            note_ids = arguments.get("note_ids", [])
            query = arguments.get("query")
            tags = arguments["tags"]

            if not note_ids and not query:
                return [TextContent(
                    type="text",
                    text="Error: Must provide either 'note_ids' or 'query' parameter"
                )]

            if query:
                note_ids = await anki.find_notes(query)
                if not note_ids:
                    return [TextContent(
                        type="text",
                        text=f"No notes found matching query: {query}"
                    )]

            tags_str = " ".join(tags)
            await anki.remove_tags(note_ids, tags_str)
            return [TextContent(
                type="text",
                text=f"✓ Removed tags [{', '.join(tags)}] from {len(note_ids)} note(s)"
            )]

        # Phase 4: Scheduling handlers
        elif name == "get_due_cards":
            deck = arguments.get("deck")
            limit = arguments.get("limit", 50)

            query = "is:due"
            if deck:
                query = f'deck:"{deck}" is:due'

            card_ids = await anki.find_cards(query)

            if not card_ids:
                deck_str = f" in '{deck}'" if deck else ""
                return [TextContent(
                    type="text",
                    text=f"No cards due for review{deck_str}."
                )]

            card_ids = card_ids[:limit]
            cards = await anki.cards_info(card_ids)

            deck_str = f" in '{deck}'" if deck else ""
            result_parts = [f"Found {len(cards)} cards due for review{deck_str}:\n"]

            for card in cards:
                question = card.get('question', '')[:50]
                question = re.sub(r'<[^>]+>', '', question)
                interval = card.get('interval', 0)
                due = card.get('due', 0)
                result_parts.append(f"- {question}")
                result_parts.append(f"  Card ID: {card.get('cardId')} | Interval: {interval}d | Deck: {card.get('deckName')}")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "reset_card_progress":
            card_ids = arguments.get("card_ids", [])
            query = arguments.get("query")
            confirm = arguments.get("confirm", False)

            if not card_ids and not query:
                return [TextContent(
                    type="text",
                    text="Error: Must provide either 'card_ids' or 'query' parameter"
                )]

            if query:
                card_ids = await anki.find_cards(query)
                if not card_ids:
                    return [TextContent(
                        type="text",
                        text=f"No cards found matching query: {query}"
                    )]

            if not confirm:
                return [TextContent(
                    type="text",
                    text=f"⚠ Reset cancelled. To reset {len(card_ids)} card(s) to new state, set confirm=true.\nThis will remove all review history!"
                )]

            await anki.forget_cards(card_ids)
            return [TextContent(
                type="text",
                text=f"✓ Reset {len(card_ids)} card(s) to new state"
            )]

        elif name == "set_ease_factor":
            card_ids = arguments["card_ids"]
            ease = arguments["ease"]

            # Validate ease range
            if ease < 1000 or ease > 9999:
                return [TextContent(
                    type="text",
                    text="Error: Ease factor must be between 1000 and 9999 (1300-5000 recommended)"
                )]

            # Set same ease for all cards
            ease_factors = [ease] * len(card_ids)
            results = await anki.set_ease_factors(card_ids, ease_factors)

            success_count = sum(1 for r in results if r)
            ease_percent = ease / 10

            return [TextContent(
                type="text",
                text=f"✓ Set ease factor to {ease_percent:.0f}% for {success_count}/{len(card_ids)} card(s)"
            )]

        # Tier 3: Study analytics handlers
        elif name == "get_review_history":
            deck = arguments["deck"]
            limit = arguments.get("limit", 100)

            try:
                reviews = await anki.get_card_reviews(deck)
            except AnkiConnectError:
                reviews = []

            if not reviews:
                return [TextContent(
                    type="text",
                    text=f"No review history found for deck '{deck}'."
                )]

            # Sort by review ID (most recent first) and limit
            reviews = sorted(reviews, key=lambda r: r.get('id', 0), reverse=True)[:limit]

            # Count outcomes: ease 1=Again, 2=Hard, 3=Good, 4=Easy
            outcomes = {'again': 0, 'hard': 0, 'good': 0, 'easy': 0}
            total_time = 0

            for review in reviews:
                ease = review.get('ease', 0)
                if ease == 1:
                    outcomes['again'] += 1
                elif ease == 2:
                    outcomes['hard'] += 1
                elif ease == 3:
                    outcomes['good'] += 1
                elif ease == 4:
                    outcomes['easy'] += 1
                total_time += review.get('time', 0)

            total_reviews = len(reviews)
            success_rate = (outcomes['good'] + outcomes['easy']) / total_reviews * 100 if total_reviews > 0 else 0
            avg_time = total_time / total_reviews / 1000 if total_reviews > 0 else 0  # Convert ms to seconds

            result_parts = [
                f"Review History for '{deck}' (last {total_reviews} reviews):",
                f"",
                f"Outcomes:",
                f"  Again (1): {outcomes['again']} ({outcomes['again']/total_reviews*100:.1f}%)" if total_reviews > 0 else "  Again (1): 0",
                f"  Hard (2): {outcomes['hard']} ({outcomes['hard']/total_reviews*100:.1f}%)" if total_reviews > 0 else "  Hard (2): 0",
                f"  Good (3): {outcomes['good']} ({outcomes['good']/total_reviews*100:.1f}%)" if total_reviews > 0 else "  Good (3): 0",
                f"  Easy (4): {outcomes['easy']} ({outcomes['easy']/total_reviews*100:.1f}%)" if total_reviews > 0 else "  Easy (4): 0",
                f"",
                f"Summary:",
                f"  Success rate (Good+Easy): {success_rate:.1f}%",
                f"  Average review time: {avg_time:.1f}s",
            ]

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "get_retention_stats":
            deck = arguments.get("deck")
            days = arguments.get("days", 30)

            # Get review history by day
            review_history = await anki.get_num_cards_reviewed_by_day()

            # Filter to requested days
            review_history = review_history[:days] if review_history else []

            if not review_history:
                return [TextContent(
                    type="text",
                    text="No review history available."
                )]

            # Calculate total reviews
            total_reviews = sum(day[1] for day in review_history)

            # Get problem cards to estimate retention issues
            base_query = f'deck:"{deck}"' if deck else ""

            # Find lapsed cards (indicates retention failures)
            lapse_query = f"{base_query} prop:lapses>=1".strip()
            lapsed_card_ids = await anki.find_cards(lapse_query)

            # Find reviewed cards (mature cards)
            reviewed_query = f"{base_query} prop:ivl>=21".strip()
            mature_card_ids = await anki.find_cards(reviewed_query)

            # Get lapse info
            total_lapses = 0
            if lapsed_card_ids:
                lapsed_cards = await anki.cards_info(lapsed_card_ids[:500])  # Limit for performance
                total_lapses = sum(c.get('lapses', 0) for c in lapsed_cards)

            # Estimate retention (mature cards that haven't lapsed recently)
            mature_count = len(mature_card_ids)
            lapsed_count = len(lapsed_card_ids)

            # Get ease distribution
            all_query = f'deck:"{deck}" -is:new'.strip() if deck else "-is:new"
            reviewed_ids = await anki.find_cards(all_query)

            ease_distribution = {'low': 0, 'normal': 0, 'high': 0}
            if reviewed_ids:
                cards_info = await anki.cards_info(reviewed_ids[:500])
                for card in cards_info:
                    factor = card.get('factor', 2500)
                    if factor < 2000:
                        ease_distribution['low'] += 1
                    elif factor > 2800:
                        ease_distribution['high'] += 1
                    else:
                        ease_distribution['normal'] += 1

            deck_str = f" for '{deck}'" if deck else ""
            result_parts = [
                f"Retention Statistics{deck_str} (last {days} days):",
                f"",
                f"Review Activity:",
                f"  Total reviews: {total_reviews}",
                f"  Daily average: {total_reviews/days:.1f}",
                f"",
                f"Card Health:",
                f"  Mature cards (21+ day interval): {mature_count}",
                f"  Cards with lapses: {lapsed_count}",
                f"  Total lapses recorded: {total_lapses}",
                f"",
                f"Ease Distribution:",
                f"  Low ease (<200%): {ease_distribution['low']}",
                f"  Normal ease (200-280%): {ease_distribution['normal']}",
                f"  High ease (>280%): {ease_distribution['high']}",
            ]

            # Retention estimate
            if mature_count > 0:
                # Rough retention estimate based on lapse ratio
                retention_est = max(0, 100 - (lapsed_count / max(mature_count, 1) * 20))
                result_parts.extend([
                    f"",
                    f"Estimated retention: {retention_est:.0f}%"
                ])

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "get_study_streak":
            # Get review history
            review_history = await anki.get_num_cards_reviewed_by_day()

            if not review_history:
                return [TextContent(
                    type="text",
                    text="No study history available."
                )]

            # Calculate current streak
            current_streak = 0
            for day_data in review_history:
                reviews = day_data[1]
                if reviews > 0:
                    current_streak += 1
                else:
                    break

            # Calculate longest streak (within available data)
            longest_streak = 0
            temp_streak = 0
            for day_data in review_history:
                reviews = day_data[1]
                if reviews > 0:
                    temp_streak += 1
                    longest_streak = max(longest_streak, temp_streak)
                else:
                    temp_streak = 0

            # Calculate total study days and reviews
            total_days = sum(1 for d in review_history if d[1] > 0)
            total_reviews = sum(d[1] for d in review_history)
            data_days = len(review_history)

            # Recent activity (last 7 days)
            last_7_days = review_history[:7]
            recent_reviews = sum(d[1] for d in last_7_days)
            recent_days_studied = sum(1 for d in last_7_days if d[1] > 0)

            result_parts = [
                "Study Streak Analysis:",
                f"",
                f"Current streak: {current_streak} day(s)",
                f"Longest streak: {longest_streak} day(s)",
                f"",
                f"Last 7 days:",
                f"  Days studied: {recent_days_studied}/7",
                f"  Reviews completed: {recent_reviews}",
                f"",
                f"All-time (last {data_days} days):",
                f"  Days studied: {total_days}/{data_days}",
                f"  Total reviews: {total_reviews}",
                f"  Study consistency: {total_days/data_days*100:.0f}%",
            ]

            # Add streak encouragement
            if current_streak > 0:
                result_parts.append(f"\n🔥 Keep it up! You're on a {current_streak}-day streak!")
            elif review_history and review_history[0][1] == 0:
                result_parts.append(f"\n📚 Time to study! Start a new streak today.")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "get_learning_curve":
            days = arguments.get("days", 30)

            # Get review history
            review_history = await anki.get_num_cards_reviewed_by_day()

            if not review_history:
                return [TextContent(
                    type="text",
                    text="No review history available."
                )]

            # Limit to requested days
            review_history = review_history[:days]

            # Reverse to show oldest to newest
            review_history = list(reversed(review_history))

            # Calculate weekly trends
            weeks = []
            for i in range(0, len(review_history), 7):
                week_data = review_history[i:i+7]
                week_reviews = sum(d[1] for d in week_data)
                week_days = len(week_data)
                weeks.append({
                    'reviews': week_reviews,
                    'days': week_days,
                    'avg': week_reviews / week_days if week_days > 0 else 0
                })

            # Get collection growth (new cards added/learned)
            decks = await anki.deck_names()
            all_stats = await anki.get_deck_stats(decks)

            total_new = 0
            total_learning = 0
            total_review = 0
            total_cards = 0

            for deck_stat in all_stats.values():
                total_new += deck_stat.get('new_count', 0)
                total_learning += deck_stat.get('learn_count', 0)
                total_review += deck_stat.get('review_count', 0)
                total_cards += deck_stat.get('total_in_deck', 0)

            # Calculate trend (comparing first half to second half)
            half = len(review_history) // 2
            first_half = sum(d[1] for d in review_history[:half])
            second_half = sum(d[1] for d in review_history[half:])

            if first_half > 0:
                trend_pct = ((second_half - first_half) / first_half) * 100
                trend_str = f"+{trend_pct:.0f}%" if trend_pct > 0 else f"{trend_pct:.0f}%"
            else:
                trend_str = "N/A"

            result_parts = [
                f"Learning Curve Analysis (last {len(review_history)} days):",
                f"",
                f"Current Collection:",
                f"  Total cards: {total_cards}",
                f"  New (not started): {total_new}",
                f"  Learning: {total_learning}",
                f"  Due for review: {total_review}",
                f"",
                f"Weekly Progress:"
            ]

            for i, week in enumerate(weeks, 1):
                bar_len = min(20, int(week['avg'] / 5))  # Scale bar
                bar = "█" * bar_len + "░" * (20 - bar_len)
                result_parts.append(f"  Week {i}: {bar} {week['reviews']} reviews ({week['avg']:.0f}/day)")

            result_parts.extend([
                f"",
                f"Trend (comparing halves): {trend_str}",
                f"Total reviews: {sum(d[1] for d in review_history)}",
            ])

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        elif name == "get_card_stats":
            query = arguments["query"]
            limit = arguments.get("limit", 10)

            # Find cards matching the query
            card_ids = await anki.find_cards(query)

            if not card_ids:
                return [TextContent(
                    type="text",
                    text=f"No cards found matching: {query}"
                )]

            # Limit results
            card_ids = card_ids[:limit]

            # Get detailed card information
            cards = await anki.cards_info(card_ids)

            if not cards:
                return [TextContent(
                    type="text",
                    text=f"Could not retrieve card information for query: {query}"
                )]

            # Get note information for content (front/back)
            note_ids = list(set(card.get('note') for card in cards if card.get('note')))
            notes = await anki.notes_info(note_ids) if note_ids else []

            # Create note_id -> content mapping
            note_content_map = {}
            for note in notes:
                note_id = note.get('noteId')
                fields = note.get('fields', {})
                # Extract front/back or other fields
                field_parts = []
                for field_name, field_data in fields.items():
                    value = field_data.get('value', '')
                    # Clean HTML tags
                    value = re.sub(r'<[^>]+>', '', value)
                    value = value.replace('&nbsp;', ' ').strip()
                    if value:
                        field_parts.append(f"{field_name}: {value[:100]}")
                note_content_map[note_id] = " | ".join(field_parts)

            # Card type mapping
            card_type_names = {
                0: "New",
                1: "Learning",
                2: "Review",
                3: "Relearning"
            }

            # Queue status mapping
            queue_names = {
                -1: "Suspended",
                -2: "Sibling buried",
                -3: "Manually buried",
                0: "New",
                1: "Learning",
                2: "Review",
                3: "Day learning",
                4: "Preview"
            }

            # Format results
            result_parts = [f"Card Statistics for query '{query}' ({len(cards)} cards):\n"]

            for card in cards:
                card_id = card.get('cardId')
                note_id = card.get('note')
                deck_name = card.get('deckName', 'Unknown')
                ease = card.get('factor', 0) / 1000  # Convert from permille
                interval = card.get('interval', 0)
                lapses = card.get('lapses', 0)
                reps = card.get('reps', 0)
                card_type = card_type_names.get(card.get('type', 0), 'Unknown')
                queue = queue_names.get(card.get('queue', 0), 'Unknown')
                due = card.get('due', 0)
                mod = card.get('mod', 0)

                # Get content from note
                content = note_content_map.get(note_id, 'Unknown')
                if len(content) > 80:
                    content = content[:77] + "..."

                result_parts.append(f"Card ID: {card_id}")
                result_parts.append(f"  Deck: {deck_name}")
                result_parts.append(f"  Content: {content}")
                result_parts.append(f"  Type: {card_type} | Queue: {queue}")
                result_parts.append(f"  Ease: {ease:.2f} ({ease * 100:.0f}%)")
                result_parts.append(f"  Interval: {interval} days")
                result_parts.append(f"  Lapses: {lapses}")
                result_parts.append(f"  Total reviews: {reps}")
                result_parts.append(f"  Due: {due}")
                if mod > 0:
                    # mod is Unix timestamp - format it
                    last_modified = datetime.fromtimestamp(mod).strftime('%Y-%m-%d %H:%M')
                    result_parts.append(f"  Last modified: {last_modified}")
                result_parts.append("")

            return [TextContent(
                type="text",
                text="\n".join(result_parts)
            )]

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except AnkiConnectError as e:
        return [TextContent(
            type="text",
            text=f"AnkiConnect error: {str(e)}\n\nMake sure Anki is running and AnkiConnect is installed."
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


async def async_main():
    """Run the MCP server (async)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def main():
    """Entry point for console script."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
