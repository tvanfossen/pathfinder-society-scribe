
# Pathfinder Game Apprentice

## Overview

This repository is a modular Python project for running a Pathfinder 1e campaign assistant, featuring:

- **Discord Bot:** Connects to Discord, reads text/voice, and interacts with users.
- **MCP Server:** Provides a stdio Model Context Protocol server for Pathfinder 1e rules/tools, including a data scraper for d20pfsrd.
- **Game Apprentice:** Operates the LLM-powered assistant for the Game Master.
- **Game File System (TBD):** Maintains game state for easy pickup and continuity.

## Structure

- `main.py` — Entry point, responsible only for bootstrapping the application.
- `discord_bot/` — Discord bot logic and connection management.
- `mcp_server/` — MCP server and Pathfinder 1e tools (including scraper).
- `game_apprentice/` — LLM-powered assistant logic.
- `README.md` — Project documentation and structure.

## Principles

- **Modular & Encapsulated:** Each component is self-contained and uses modern Python class structures with properties/getters/setters.
- **DRY & KISS:** Code is kept simple and avoids repetition.

## Goals

- Provide a robust Discord bot for Pathfinder 1e, supporting text and voice.
- Host Pathfinder 1e rules/tools via MCP server.
- Automate data collection from d20pfsrd.
- Maintain game state for seamless campaign management.

## Getting Started

1. Clone the repository.
2. See individual folders for setup and usage.
3. Use this README as a reference for project structure.

---

*This README will be updated as the project evolves.*