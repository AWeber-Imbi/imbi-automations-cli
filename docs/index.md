# Imbi Automations CLI

A powerful CLI framework for executing dynamic workflows across software project repositories with deep integration to the Imbi project management system.

## Overview

Imbi Automations CLI is designed to automate common development and maintenance tasks across multiple repositories. Built on the proven architecture from the g2g-migration tool, it provides:

- **Dynamic Workflows**: Execute configurable workflows with conditional logic
- **Multi-Platform Support**: GitHub and GitLab integration
- **AI-Powered Transformations**: Claude Code integration for complex code changes
- **Template Management**: Jinja2-based file generation and templating
- **Project Management**: Deep integration with Imbi for project metadata
- **Conditional Execution**: Skip or execute actions based on previous results

## Key Features

### 🔄 Workflow Engine
- Template-based file operations
- AI-powered code editing with Claude 3.5 Haiku
- Complex multi-file analysis with Claude Code
- Shell command execution with context variables

### 🏗️ Architecture
- Modular client system (GitHub, GitLab, Imbi, Utils)
- Transaction-style operations with rollback support
- Batch processing with checkpoint resumption
- Extensible action types and conditions

### 🎯 Use Cases
- Repository standardization across organizations
- Automated compliance updates
- Bulk configuration changes
- CI/CD pipeline management
- Code quality improvements

## Quick Start

```bash
# Install with development dependencies
pip install -e .[dev]

# Configure your workflow
imbi-automations config.toml

# Run against Imbi project types
imbi-automations --imbi-project-type python-service config.toml
```

## Example Workflow

```toml
name = "failing-sonarqube"
description = "Identify repositories with failing SonarQube jobs"
clone_repository = false

[[actions]]
name = "check-sonarqube"
type = "callable"

[actions.value]
client = "github"
method = "get_sonarqube_job_status"
kwargs.org = "{{ github_repository.owner.login }}"
kwargs.repo_name = "{{ github_repository.name }}"
kwargs.branch = "main"

[[actions]]
name = "log-failures"
type = "callable"
condition = "actions['check-sonarqube']['result'] == 'failure'"

[actions.value]
client = "utils"
method = "append_file"
kwargs.file = "/tmp/failing-projects.csv"
kwargs.value = "{{ imbi_project.name + ',' + github_repository.html_url + '\n' }}"
```

## Next Steps

- [Installation Guide](getting-started/installation.md)
- [Configuration](getting-started/configuration.md)
- [Workflow Development](user-guide/workflows.md)
- [API Reference](api/cli.md)
