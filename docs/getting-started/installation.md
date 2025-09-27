# Installation

## Requirements

- Python 3.12 or higher
- Git (for repository operations)
- GitHub CLI (`gh`) for GitHub Enterprise integration

## Install from Source

```bash
# Clone the repository
git clone https://github.com/imbi/imbi-automations-cli
cd imbi-automations-cli

# Install in development mode
pip install -e .[dev]

# Install pre-commit hooks (for development)
pre-commit install
```

## Verify Installation

```bash
# Check that the CLI is available
imbi-automations --help

# Verify version
imbi-automations --version
```

## Dependencies

### Runtime Dependencies

- **colorlog**: Colored logging for CLI applications
- **httpx**: Modern async HTTP client for API calls
- **jinja2**: Template engine for file generation
- **pydantic**: Data validation and configuration management
- **rich**: Rich text and progress displays
- **truststore**: SSL certificate handling
- **yarl**: URL parsing and manipulation

### Development Dependencies

- **build**: Package building tools
- **coverage[toml]**: Test coverage measurement
- **mkdocs**: Documentation site generator
- **mkdocs-material**: Material Design theme for MkDocs
- **pre-commit**: Git hooks for code quality
- **pytest**: Test framework
- **pytest-cov**: Pytest coverage plugin
- **ruff**: Fast Python linter and formatter

## Configuration

After installation, you'll need to create a configuration file. See [Configuration](configuration.md) for details.
