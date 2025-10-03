# Imbi Automations CLI

A comprehensive CLI framework for executing automated workflows across software project repositories with AI-powered transformations and deep integration to the Imbi project management system.

## Overview

Imbi Automations enables bulk automation across your software projects with intelligent targeting, conditional execution, and powerful transformation capabilities. Built on a modern async Python architecture, it provides seamless integration with GitHub, GitLab, and the Imbi project management platform.

### Key Features

- **Multi-Provider Support**: Native GitHub and GitLab API integration
- **AI-Powered Transformations**: Claude Code SDK for intelligent code changes
- **Advanced Filtering**: Target specific project subsets with multiple criteria
- **Conditional Execution**: Smart workflow execution based on repository state
- **Batch Processing**: Concurrent processing with resumption capabilities
- **Template System**: Jinja2-based file generation with full project context

### Action Types

The framework supports multiple transformation types:

- **Callable Actions**: Direct API method calls with dynamic parameters
- **Claude Code Integration**: Complex multi-file analysis and AI transformations
- **Docker Operations**: Container-based file extraction and manipulation
- **Git Operations**: Version control operations and branch management
- **File Actions**: Copy, move, delete, and regex replacement operations
- **Shell Commands**: Execute arbitrary commands with template variables
- **Utility Actions**: Helper operations for common workflow patterns

## Installation

### From PyPI

```bash
pip install imbi-automations
```

### Development Installation

```bash
git clone <repository-url>
cd imbi-automations-cli
pip install -e .[dev]
pre-commit install
```

## Getting Started

### 1. Configuration

Create a `config.toml` file with your API credentials:

```toml
[github]
api_key = "ghp_your_github_token"
hostname = "github.com"  # Optional, defaults to github.com

[imbi]
api_key = "your-imbi-api-key"
hostname = "imbi.example.com"

[claude_code]
executable = "claude"  # Optional, defaults to 'claude'
```

### 2. Run a Workflow

Execute workflows across all your projects:

```bash
# Run a specific workflow
imbi-automations config.toml workflows/workflow-name --all-projects

# Resume from a specific project (useful for large batches)
imbi-automations config.toml workflows/workflow-name --all-projects --start-from-project my-project-slug
```

### 3. Available Workflows

The tool includes 25+ pre-built workflows for common tasks:

- **Python Version Updates**: Upgrade projects to newer Python versions
- **Docker Image Updates**: Update base images and dependencies
- **GitHub Actions**: Fix and optimize CI/CD pipelines
- **Code Quality**: Apply linting, formatting, and pre-commit hooks
- **Infrastructure Updates**: Modernize project configurations and tooling

## Documentation

- **[Architecture Guide](architecture.md)**: Comprehensive technical documentation
- **[Workflow Actions](actions/index.md)**: Complete action types reference
- **Workflow Configuration**: See workflows directory in repository
- **Developer Guide**: See AGENTS.md in repository

## Requirements

- Python 3.12 or higher
- GitHub API access (for GitHub workflows)
- GitLab API access (for GitLab workflows)
- Imbi project management system access
