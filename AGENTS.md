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
imbi-automations config.toml workflows/workflow-name --all-projects

# Resume processing from a specific project (useful for large batches)
imbi-automations config.toml workflows/workflow-name --all-projects --start-from-project my-project-slug

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
- **GitHub Client** (`github.py`): GitHub API integration for repository operations with pattern-aware workflow file detection
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

### Workflow Conditions

Workflows support conditional execution based on repository state. There are two types of conditions:

#### Local Conditions (Post-Clone)
Evaluated after cloning the repository:
- **`file_exists`**: Check if a file exists at the specified path
- **`file_not_exists`**: Check if a file does not exist at the specified path
- **`file_contains`**: Check if a file contains specified text or matches a regex pattern

#### Remote Conditions (Pre-Clone)
Evaluated before cloning using GitHub API, providing performance benefits:
- **`remote_file_exists`**: Check if a file exists in the remote repository
- **`remote_file_not_exists`**: Check if a file does not exist in the remote repository
- **`remote_file_contains`**: Check if a remote file contains specified text or regex pattern

#### File Contains Conditions (Local and Remote)

Both `file_contains` and `remote_file_contains` support string literals and regular expressions:

```toml
# Local conditions (require git clone)
[[conditions]]
file_exists = "package.json"

[[conditions]]
file_contains = "compose.yml"
file = "bootstrap"

# Remote conditions (checked before cloning - more efficient)
[[conditions]]
remote_file_exists = "README.md"

[[conditions]]
remote_file_not_exists = "legacy-config.json"

[[conditions]]
remote_file_contains = "node.*18"
remote_file = ".nvmrc"

# Mixed local and remote conditions
[[conditions]]
remote_file_exists = "package.json"  # Check remotely first

[[conditions]]
file_contains = "test.*script"       # Then check locally after clone
file = "package.json"
```

#### Advanced Pattern Examples

```toml
# Version checking with regex
[[conditions]]
remote_file_contains = "\"version\":\\s*\"\\d+\\.\\d+\\.\\d+\""
remote_file = "package.json"

# Docker base image checking
[[conditions]]
remote_file_contains = "FROM python:[3-4]\\.[0-9]+"
remote_file = "Dockerfile"

# GitHub Actions workflow detection
[[conditions]]
remote_file_exists = ".github/workflows/ci.yml"

# Legacy file cleanup detection
[[conditions]]
remote_file_not_exists = ".travis.yml"  # No Travis CI
[[conditions]]
remote_file_exists = ".github/workflows"  # Has GitHub Actions
```

#### Performance Benefits

**Remote Conditions:**
- ⚡ **Faster**: GitHub API calls are faster than git clone
- 💾 **Bandwidth efficient**: Skip clone entirely for non-matching repos
- 🔄 **Early filtering**: Fail fast before expensive operations

**Best Practices:**
- Use remote conditions for initial filtering (file existence, basic content checks)
- Use local conditions for complex file analysis requiring full repository access
- String search is performed first (fast), with regex fallback only when string search fails
- Invalid regex patterns gracefully fall back to string search behavior

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
- **Pattern-Aware File Detection**: GitHub client supports both exact file paths and regex patterns for workflow file detection
- **Resumable Processing**: `--start-from-project` CLI option allows resuming batch processing from a specific project slug

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

## Available Workflows

### Environment Synchronization (`sync-project-environments`)

Synchronizes environments between an Imbi project and its corresponding GitHub repository.

**Purpose**: Ensures that GitHub repository environments match the environments defined in the Imbi project. This workflow:
- Removes GitHub environments that don't exist in the Imbi project's environment list
- Creates missing GitHub environments that are defined in the Imbi project

**Configuration**: `workflows/sync-project-environments/config.toml`
- **Type**: Action-based workflow (no repository cloning required)
- **Conditions**: Automatically runs on all projects; skips projects without environments defined
- **Source of Truth**: Imbi project's `environments` field

**Implementation Details**:
- **Models**: `GitHubEnvironment` in `models.py`
- **Client Methods**: `get_repository_environments()`, `create_environment()`, `delete_environment()`, `sync_project_environments()` in `github.py`
- **Sync Logic**: `environment_sync.py` module with comprehensive error handling and logging
- **Template Handling**: Supports both list and string input with HTML entity decoding for Jinja2 compatibility

**API Endpoints Used**:
- GitHub: `GET /repos/{owner}/{repo}/environments` - List repository environments
- GitHub: `PUT /repos/{owner}/{repo}/environments/{environment_name}` - Create environment
- GitHub: `DELETE /repos/{owner}/{repo}/environments/{environment_name}` - Delete environment

**Testing**: Comprehensive unit tests in `tests/test_environment_sync.py` covering success scenarios, error handling, and edge cases.

**Usage Example**:
```toml
[[actions]]
name = "sync-environments"

[actions.value]
client = "github"
method = "sync_project_environments"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo = "{{ github_repository.name }}"
imbi_environments = "{{ imbi_project.environments }}"
```

## Future Implementation Areas

Based on the PRD, these areas are planned but not yet implemented:
- Workflow discovery and execution engine
- Transaction-style rollback operations
- File action transformations (rename, remove, regex)
- Batch processing with checkpoint resumption
- Provider abstraction for GitLab support
