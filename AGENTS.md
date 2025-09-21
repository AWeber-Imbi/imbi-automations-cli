# AGENTS.md

This file provides guidance to AI Agents like Claude Code (claude.ai/code) when working with code in this repository.

**Note**: AI assistants should maintain and update this file when making significant changes to the codebase architecture, dependencies, or development processes.

## Project Overview

Imbi Automations is a CLI framework for executing dynamic workflows across software project repositories with deep integration to the Imbi project management system. The architecture is based on the proven g2g-migration tool which handled complex GitLab→GitHub migrations with AI-powered transformations.

## Development Commands

### Setup and Dependencies
```bash
# Development setup
pip install -e .[dev]
pre-commit install

# Run the CLI
imbi-automations config.toml

# Development with virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -e .[dev]
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src/imbi_automations

# Run single test file
pytest tests/test_http.py
```

### Code Quality
```bash
# Format code
ruff format

# Lint code
ruff check --fix

# Run all pre-commit hooks
pre-commit run --all-files
```

## Architecture

### Core Components

- **CLI Interface** (`cli.py`): Argument parsing, logging configuration, entry point
- **Models** (`models.py`): Pydantic data models for configuration and Imbi entities
- **HTTP Client** (`http.py`): Base HTTP client with authentication and error handling
- **Imbi Client** (`imbi.py`): Integration with Imbi project management API
- **GitHub Client** (`github.py`): GitHub API integration for repository operations
- **Git Operations** (`git.py`): Git repository management and operations
- **Utilities** (`utils.py`): Configuration loading, directory management, URL sanitization

### Configuration Structure

The tool uses TOML configuration files with Pydantic validation:

```toml
[github]
api_key = "ghp_..."
hostname = "github.com"  # Optional, defaults to github.com

[imbi]
api_key = "uuid-here"
hostname = "imbi.example.com"

[claude_code]
executable = "claude"  # Optional, defaults to 'claude'
```

### Transformation Architecture

Based on the PRD, the system supports four transformation types:

1. **Template Manager**: Jinja2-based file placement with project context
2. **AI Editor**: Fast, focused file edits using Claude 3.5 Haiku
3. **Claude Code**: Complex multi-file analysis and transformation
4. **Shell**: Arbitrary command execution with context variables

### Workflow Structure

Workflows are organized in a directory structure:

```
workflows/
├── sync-github-metadata/
│   ├── workflow.toml              # Workflow definition
│   ├── transformations/           # Transformation steps
│   │   ├── ai-editor/priority-75-update-readme/
│   │   ├── templates/priority-50-add-codeowners/
│   │   └── shell/priority-25-run-tests/
│   └── conditions/                # Workflow applicability
```

## Code Style and Standards

- **Line length**: 79 characters (enforced by ruff)
- **Python version**: 3.12+ required
- **Type hints**: Required for all functions and methods
- **Quotes**: Single quotes preferred, double quotes for docstrings
- **Import organization**: Use module imports over direct class/function imports
- **Logging**: Use module-level LOGGER, colored logging for CLI applications
- **Error handling**: Use specific exception types, include context in log messages

## Testing Infrastructure

- **Base class**: `AsyncTestCase` inherits from `unittest.IsolatedAsyncioTestCase`
- **HTTP mocking**: Uses `httpx.MockTransport` with JSON fixture files in `tests/data/`
- **Mock data**: Path-based JSON files matching URL endpoints
- **Async support**: Full asyncio test support with proper teardown
- **Test isolation**: HTTP client instances cleared between tests

## Key Implementation Notes

- **HTTP Client Pattern**: Singleton pattern with instance caching (`_instances.clear()`)
- **URL Sanitization**: Passwords masked in logs using regex pattern replacement
- **Configuration Loading**: TOML files loaded with tomllib, validated with Pydantic
- **Colored Logging**: Uses colorlog for CLI output with different colors per log level
- **Directory Management**: Automatic parent directory creation with proper error handling
- **Authentication**: Secret string handling for API keys in configuration

## Dependencies

### Runtime Dependencies
- `colorlog`: Colored logging for CLI applications
- `httpx`: Modern async HTTP client
- `pydantic`: Data validation and configuration management
- `rich`: Rich text and progress displays
- `truststore`: SSL certificate handling
- `yarl`: URL parsing and manipulation

### Development Dependencies
- `build`: Package building
- `coverage[toml]`: Test coverage with TOML configuration
- `pre-commit`: Git hooks for code quality
- `pytest`: Test framework
- `ruff`: Fast Python linter and formatter

## Future Implementation Areas

Based on the PRD, these areas are planned but not yet implemented:
- Workflow discovery and execution engine
- Transaction-style rollback operations
- File action transformations (rename, remove, regex)
- Batch processing with checkpoint resumption
- Provider abstraction for GitLab support
