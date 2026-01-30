"""MCP server for Anki integration."""

import asyncio
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
