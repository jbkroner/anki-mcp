# Anki MCP Server

A Model Context Protocol (MCP) server that connects Claude Desktop to your local Anki instance via AnkiConnect. Enables Claude to create, manage, and search flashcards directly in your Anki decks.

## Features

- **Health Check**: Verify Anki and AnkiConnect are running
- **Deck Management**: List and create decks
- **Flashcard Creation**: Add single or batch flashcards
- **Cloze Deletions**: Create cloze deletion cards for sentence learning
- **Search**: Find existing notes using Anki's search syntax
- **Sync**: Trigger AnkiWeb synchronization
- **Spanish Helpers**: Built-in utilities for formatting Spanish vocabulary cards

## Prerequisites

Before using this MCP server, you need:

1. **Anki Desktop** - Download from [ankiweb.net](https://apps.ankiweb.net/)
2. **AnkiConnect Add-on** - Install from Anki:
   - Open Anki
   - Go to Tools → Add-ons → Get Add-ons
   - Enter code: `2055492159`
   - Restart Anki
3. **Python 3.11+** - Required for running the server
4. **uv** - Python package manager (optional but recommended)

### Verify AnkiConnect is Running

After installing AnkiConnect, verify it's working:

```bash
curl http://localhost:8765
```

You should see: `"AnkiConnect v.6"`

## Installation

### Option 1: Using uv (Recommended)

**uv** is a fast Python package manager. If you don't have it, [install it first](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/jbkroner/anki-mcp.git
cd anki-mcp

# Install dependencies and create virtual environment
uv sync
```

### Option 2: Using pip

```bash
# Clone the repository
git clone https://github.com/jbkroner/anki-mcp.git
cd anki-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Configuration

### Claude Desktop Setup

Add this to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### If installed with uv:

```json
{
  "mcpServers": {
    "anki": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/anki-mcp",
        "anki-mcp-server"
      ]
    }
  }
}
```

Replace `/absolute/path/to/anki-mcp` with the actual path to this directory.

#### If installed with pip/venv:

```json
{
  "mcpServers": {
    "anki": {
      "command": "/absolute/path/to/anki-mcp/.venv/bin/anki-mcp-server",
      "args": []
    }
  }
}
```

### Restart Claude Desktop

After updating the configuration, completely quit and restart Claude Desktop for changes to take effect.

## Available Tools

### `anki_health_check`

Check if Anki is running with AnkiConnect enabled.

**Example:**
```
User: "Is Anki running?"
Claude: [Uses anki_health_check]
```

### `list_decks`

List all available Anki decks.

**Example:**
```
User: "What decks do I have?"
Claude: [Uses list_decks]
```

### `list_note_types`

List all note types (models) and their fields.

**Example:**
```
User: "What note types are available?"
Claude: [Uses list_note_types]
```

### `add_flashcard`

Add a single flashcard to Anki.

**Parameters:**
- `deck` (required): Target deck name
- `front` (required): Front of the card
- `back` (required): Back of the card
- `tags` (optional): List of tags
- `model` (optional): Note type (default: "Basic")

**Example:**
```
User: "Add a flashcard: 'What is the capital of France?' → 'Paris' to my Geography deck"
Claude: [Uses add_flashcard with deck="Geography", front="What is the capital of France?", back="Paris"]
```

### `add_flashcards_batch`

Add multiple flashcards in one operation (much faster than adding individually).

**Parameters:**
- `deck` (required): Target deck name
- `cards` (required): List of card objects with `front`, `back`, and optional `tags`
- `tags` (optional): Tags applied to all cards
- `model` (optional): Note type (default: "Basic")

**Example:**
```
User: "Add these Spanish words to my Spanish::Vocabulary deck:
- perro = dog
- gato = cat
- casa = house"

Claude: [Uses add_flashcards_batch with appropriate cards]
```

### `search_notes`

Search for existing notes using Anki's search syntax.

**Parameters:**
- `query` (required): Search query
- `limit` (optional): Max results (default: 20)

**Search Syntax Examples:**
- `deck:Spanish` - All notes in Spanish deck
- `tag:verb` - All notes tagged "verb"
- `deck:Spanish tag:verb` - Spanish verbs
- `front:hablar` - Notes with "hablar" in front field

**Example:**
```
User: "Find all my Spanish verb cards"
Claude: [Uses search_notes with query="deck:Spanish tag:verb"]
```

### `add_cloze_card`

Create a cloze deletion card for learning sentences/phrases.

**Parameters:**
- `deck` (required): Target deck name
- `text` (required): Text with `{{c1::deletions}}` markup
- `extra` (optional): Additional context
- `tags` (optional): List of tags

**Example:**
```
User: "Make a cloze card: 'I have to wake up early tomorrow' focusing on 'have to'"
Claude: [Creates: "I {{c1::have to}} wake up early tomorrow"]
```

### `sync_anki`

Synchronize the local collection with AnkiWeb.

**Example:**
```
User: "Sync my Anki collection"
Claude: [Uses sync_anki]
```

## Usage Examples

### Spanish Vocabulary Workflow

**Quick Vocab Add:**
```
User: "Add these words to Spanish::Vocabulary:
- madrugada = dawn/early morning
- trasnochar = to stay up late
- madrugar = to wake up early"

Claude: I'll add these Spanish vocabulary words to your deck.
[Uses add_flashcards_batch with formatted cards]
```

**Verb with Conjugation Notes:**
```
User: "Add the verb 'poder' (to be able to) with a note that it's stem-changing o→ue"

Claude: [Creates verb card with conjugation note and appropriate tags]
```

**Sentence Mining with Cloze:**
```
User: "I heard 'Tengo que madrugar mañana' in my podcast. Make a cloze card for 'madrugar'"

Claude: [Creates: "Tengo que {{c1::madrugar}} mañana" with translation and tags]
```

### General Flashcard Workflows

**Study Set Creation:**
```
User: "Create a deck called 'Japanese::JLPT N5::Verbs' and add these:
- 食べる (taberu) = to eat
- 飲む (nomu) = to drink
- 見る (miru) = to see"

Claude: [Creates deck and adds cards in batch]
```

**Finding Duplicates:**
```
User: "Do I already have a card for 'ephemeral'?"
Claude: [Uses search_notes with query="front:ephemeral"]
```

## Spanish Helper Functions

The server includes Python helper functions for formatting Spanish cards (located in `src/anki_mcp/spanish.py`):

### `format_vocab_card()`
Creates consistently formatted vocabulary cards with:
- Gender indicators (el/la)
- Example sentences
- Proper structure

### `format_verb_card()`
Creates verb cards with:
- Verb type identification (AR/ER/IR)
- Conjugation notes
- Example usage

### `format_sentence_cloze()`
Automatically creates cloze deletions from sentences.

### `suggest_tags()`
Suggests appropriate tags based on:
- Part of speech
- Verb characteristics (reflexive, irregular, etc.)
- Custom categories

## Recommended Deck Structure

For Spanish learning:

```
Spanish/
├── Vocabulary/
│   ├── Core
│   └── Thematic
├── Verbs/
│   ├── Present
│   ├── Past
│   └── Irregular
└── Sentences/
    └── Cloze
```

## Recommended Tags

### Part of Speech
`verb`, `noun`, `adjective`, `adverb`, `phrase`, `expression`

### Verb Specifics
`verb-ar`, `verb-er`, `verb-ir`, `irregular`, `reflexive`

### Noun Specifics
`masculine`, `feminine`

### Frequency
`freq-high`, `freq-medium`, `freq-low`

### Source Tracking
`source-podcast`, `source-book`, `source-conversation`, `source-lingoda`

### Topics
`topic-food`, `topic-travel`, `topic-work`, `topic-daily`

## Development

### Running Tests

```bash
# Make sure Anki is running with AnkiConnect
uv run pytest

# Or with pip
pytest
```

**Note:** Tests require Anki to be running with AnkiConnect installed. They will create test decks in your collection.

### Project Structure

```
anki-mcp/
├── pyproject.toml              # Project configuration
├── README.md                   # This file
├── src/
│   └── anki_mcp/
│       ├── __init__.py        # Package initialization
│       ├── server.py          # MCP server + tool definitions
│       ├── anki_client.py     # AnkiConnect API wrapper
│       └── spanish.py         # Spanish-specific helpers
└── tests/
    ├── test_anki_client.py    # AnkiConnect tests
    └── test_spanish.py        # Spanish helper tests
```

## Troubleshooting

### "AnkiConnect error" messages

**Solution:** Make sure Anki is running and AnkiConnect is installed. Test with:
```bash
curl http://localhost:8765
```

### Cards not appearing in Anki

**Solution:** Check that:
1. The deck name is correct (case-sensitive)
2. You're looking in the right deck
3. Anki is in the main window (not the browser)

### MCP server not connecting

**Solution:**
1. Verify the path in Claude Desktop config is absolute (not relative)
2. Check that `uv` or `python` is in your system PATH
3. Restart Claude Desktop completely
4. Check Claude Desktop logs for errors

### Duplicate cards being skipped

**Solution:** This is expected behavior. AnkiConnect prevents duplicate cards. Use `search_notes` to find existing cards.

## Links

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [AnkiConnect API](https://foosoft.net/projects/anki-connect/)
- [Anki Search Syntax](https://docs.ankiweb.net/searching.html)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## License

MIT

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.
