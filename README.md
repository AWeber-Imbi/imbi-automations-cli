# Imbi Automations CLI

CLI tool for executing automated workflows across Imbi projects with AI-powered transformations and GitHub PR integration.

## Overview

Imbi Automations is a comprehensive CLI framework that enables bulk automation across software project repositories with deep integration to the Imbi project management system. The tool supports multiple workflow types with advanced filtering, conditional execution, and AI-powered transformations.

## Installation

### From PyPI

```bash
pip install imbi-automations
```

### Development Setup

```bash
git clone https://github.com/AWeber-Imbi/imbi-automations.git
cd imbi-automations
pip install -e .[dev]
pre-commit install
```

## Quick Start

```bash
# Run workflows
imbi-automations config.toml workflows/workflow-name --all-projects

# Resume from a specific project
imbi-automations config.toml workflows/workflow-name --all-projects --start-from-project my-project-slug
```

## Key Features

- **Multi-Provider Support**: GitHub and GitLab API integration
- **Workflow Engine**: Action-based processing with conditional execution
- **AI Integration**: Claude Code SDK for intelligent transformations
- **Batch Processing**: Concurrent processing with resumption capabilities
- **Template System**: Jinja2-based file generation with full project context
- **Advanced Filtering**: Target specific project subsets with multiple criteria

## Action Types

- **Callable Actions**: Direct method calls on client instances
- **Claude Code**: Comprehensive AI-powered code transformations
- **Docker Operations**: Container-based file extraction and manipulation
- **Git Operations**: Version control operations and branch management
- **File Actions**: Copy, move, delete, and regex replacement operations
- **Shell Commands**: Execute arbitrary commands with template variables
- **Utility Actions**: Helper operations for common workflow tasks
- **Template System**: Generate files from Jinja2 templates

## Documentation

See [AGENTS.md](AGENTS.md) for comprehensive architecture documentation, development commands, and implementation details.
