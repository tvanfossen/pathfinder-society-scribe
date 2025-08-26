# PF2e Society Scribe

An AI-powered Pathfinder 2e campaign assistant using local LLMs for game management, narrative generation, and rules assistance.

## Current Status (Phase 2.5)

✅ **Completed:**
- Docker environment with CUDA support for GTX 1080 Ti
- Base model classes with modern Pythonic structure
- Character and Campaign managers (JSON-based, to be migrated to SQLite)
- 81% test coverage on core models
- Tutorial campaign setup

⚠️ **In Progress:**
- Migration from JSON to SQLite for campaign data
- Web interface for GM dashboard
- LLM integration with llama-cpp-python

❌ **Pending:**
- MCP server implementation
- Discord bot integration
- Voice-to-text and text-to-voice features

## Project Structure

```
~/pf2e-campaigns/
├── campaigns/              # Campaign database files (SQLite)
│   └── {campaign_name}/
│       ├── campaign.db    # Main campaign database
│       └── backups/       # Database backups
├── config/                # Configuration files
│   └── discord-bot.env    # Discord bot config (Phase 5)
├── models/                # GGUF model files
│   └── *.gguf            # Local LLM models
└── shared/               # Shared resources
    └── pf2e.db          # PF2e rules database (scraped)

./src/
├── models/               # ✅ Data models (100% coverage)
│   ├── base.py          # Enums and base classes
│   ├── abilities.py     # Ability scores
│   ├── character.py     # Player characters
│   ├── campaign.py      # Campaigns and sessions
│   ├── equipment.py     # Items, weapons, armor
│   └── spellcasting.py  # Magic system
├── managers/            # ✅ Data persistence (needs SQLite migration)
│   ├── character_manager.py
│   └── campaign_manager.py
├── web/                 # 🚧 Web interface (next priority)
│   ├── app.py          # FastAPI/Starlette app
│   ├── routes/         # API endpoints
│   └── templates/      # Jinja2 templates
├── society_scribe/     # ❌ LLM integration (pending)
└── mcp/               # ❌ MCP server (Phase 4)
```

## Quick Start

### Prerequisites
- Docker with GPU support
- NVIDIA GPU (tested on GTX 1080 Ti)
- GGUF model file in `~/pf2e-campaigns/models/`

### Setup
```bash
# Initial setup
invoke setup

# Build Docker image
invoke build

# Run tests
invoke test --model-file=Qwen2.5-7B-Instruct-Q6_K_L.gguf

# Start web server (coming soon)
invoke run --campaign=my_campaign --port=8000
```

## Test Results

Current test status:
- **49 passed**, 6 failed
- **81% code coverage**

### Known Issues:
1. **CUDA Detection**: llama-cpp-python showing CPU-only build (needs rebuild with CUDA)
2. **Path Mismatch**: Docker environment variables not matching expected paths
3. **Shield.is_broken**: Property calculation error in equipment model
4. **Session Attendance**: Set operations not properly tracking character presence
5. **JSON vs SQLite**: Currently using JSON, needs migration to SQLite for performance

## Architecture Decisions

### Why SQLite over JSON?
- **Performance**: Fast queries on large datasets
- **Concurrency**: Better handling of simultaneous operations
- **Relationships**: Proper foreign keys and joins
- **Scalability**: Campaigns can grow to hundreds of sessions
- **Backup**: Built-in backup and recovery mechanisms

### Model Design Principles
- **Clean Class Structure**: No free-form dicts, everything is typed
- **KISS**: Simple, focused classes with single responsibilities
- **DRY**: Shared functionality in base classes and mixins
- **Encapsulation**: Business logic lives with the data
- **100% Test Coverage**: Every model has comprehensive tests

## Development Roadmap

### Phase 3: Web Interface (Current Priority)
- [ ] FastAPI/Starlette application setup
- [ ] GM Dashboard with campaign overview
- [ ] Character sheet viewer/editor
- [ ] Session management interface
- [ ] Direct LLM interaction panel
- [ ] Real-time dice rolling and rules lookup

### Phase 4: Database Migration
- [ ] SQLAlchemy models for all entities
- [ ] Migration scripts from JSON to SQLite
- [ ] Async database operations
- [ ] Backup and restore functionality

### Phase 5: LLM Integration
- [ ] Model loading and management
- [ ] Prompt templates for different contexts
- [ ] Tool execution framework
- [ ] Natural language command processing

## Contributing

This project follows strict quality standards:
- 100% pytest coverage required for new features
- Type hints on all functions
- Docstrings following Google style
- No backwards compatibility concerns (prototype phase)

## License

[License details to be added]