# Workflows

Workflows are the core of Imbi Automations, defining a series of actions to be executed across repositories or projects.

## Workflow Structure

Each workflow is a directory containing a `config.toml` file and supporting files:

```
workflows/
├── python39-project-fix/
│   ├── config.toml                    # Workflow configuration
│   ├── generate_pyproject_prompt.md.j2  # Claude Code prompts
│   ├── validate_migration_prompt.md.j2
│   └── Dockerfile-consumer            # Template files
```

## Basic Workflow Configuration

```toml
name = "Python 3.9 Project Fix"
description = "Multi-step workflow to update and fix Python 3.9 projects"
clone_repository = true
create_pull_request = true

[filter]
project_types = ["apis", "consumers"]
requires_github_identifier = true

[[conditions]]
remote_file_exists = "setup.cfg"

[[actions]]
name = "generate-config"
type = "claude"
prompt_file = "generate_prompt.md.j2"
```

## Configuration Options

### Workflow Settings
- **`name`** (required): Workflow identifier
- **`description`**: Human-readable description
- **`clone_repository`**: Whether to clone repos (default: true)
- **`create_pull_request`**: Create PR after execution (default: true)
- **`ci_skip_checks`**: Add `[ci skip]` to commits (default: false)
- **`shallow_clone`**: Use shallow git clone (default: true)

### Project Filtering
Filter which projects the workflow targets:

```toml
[filter]
project_ids = [123, 456]                           # Specific project IDs
project_types = ["apis", "consumers", "daemons"]   # Project types
project_facts = {"Programming Language" = "Python 3.9"}  # Exact fact matching
requires_github_identifier = true                  # Must have GitHub repo
exclude_github_workflow_status = ["success"]       # Skip if CI passing
```

## Conditions

Define when workflows should execute for a project:

### Remote Conditions (Pre-Clone)
More efficient - checked via GitHub API before cloning:

```toml
[[conditions]]
remote_file_exists = "setup.cfg"

[[conditions]]
remote_file_not_exists = "pyproject.toml"

[[conditions]]
remote_file_contains = "version.*3\\.9"
remote_file = ".python-version"
```

### Local Conditions (Post-Clone)
Checked after repository is cloned:

```toml
[[conditions]]
file_exists = "package.json"

[[conditions]]
file_contains = "test.*script"
file = "package.json"
```

## Actions

Actions are the workflow steps, executed sequentially:

### Client Method Calls (Default)
Execute methods on GitHub, GitLab, or Imbi clients:

```toml
[[actions]]
name = "sync-environments"

[actions.value]
client = "github"
method = "sync_project_environments"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo = "{{ github_repository.name }}"
```

### Claude Code Integration
AI-powered code analysis and transformation:

```toml
[[actions]]
name = "migrate-config"
type = "claude"
prompt_file = "migration_prompt.md.j2"
timeout = 600
on_failure = "prepare-migration"
```

### Shell Commands
Execute shell commands in the working directory:

```toml
[[actions]]
name = "run-tests"
type = "shell"
command = "pytest --cov=src"
```

### File Operations
Copy, rename, or remove files:

```toml
[[actions]]
name = "copy-config"
type = "file"
command = "copy"
source = "template.yml"
destination = "config.yml"
```

### AI Editor
Focused file editing with AI:

```toml
[[actions]]
name = "update-readme"
type = "ai-editor"
prompt_file = "readme_prompt.md"
target_file = "README.md"
```

### Git Operations
Extract or revert files from git history:

```toml
[[actions]]
name = "extract-original"
type = "git-extract"
keyword = "g2g-migration"
source = "Dockerfile"
target_path = "Dockerfile.original"
```

## Failure Handling and Retries

### Failure Files
Claude Code actions can signal failure by creating files:
- `ACTION_FAILED`: Generic action failure
- `{ACTION_NAME}_FAILED`: Action-specific failure

### Restart on Failure
Actions can restart from earlier actions when they fail:

```toml
[[actions]]
name = "validate-migration"
type = "claude"
prompt_file = "validate.md.j2"
on_failure = "generate-migration"  # Restart from generation if validation fails
```

- Each action can fail up to 3 times before aborting
- Restart actions receive `previous_failure` context
- Enables self-healing workflows that learn from mistakes

## Template Context

All prompt files and action configurations support Jinja2 templating:

### Project Information
```jinja2
{{ imbi_project.name }}          # Project name
{{ imbi_project.project_type }}  # Project type (apis, consumers, etc.)
{{ imbi_project.slug }}          # Project slug
{{ github_repository.html_url }} # GitHub repository URL
```

### Previous Action Results
```jinja2
{{ actions['previous-action']['result'] }}
```

### Conditional Templates
```jinja2
{% if github_repository -%}
Repository: {{ github_repository.full_name }}
{% endif %}
```

## Action Conditions

Individual actions can have conditions:

```toml
[[actions]]
name = "conditional-action"
type = "shell"
command = "echo 'Running only if conditions met'"

[[actions.conditions]]
file_exists = "setup.cfg"

[[actions.conditions]]
file_not_exists = "pyproject.toml"
```

## Best Practices

1. **Use Jinja2 templates** (`.md.j2`) for all Claude Code prompts to provide project-specific context
2. **Remote conditions first** - More efficient than local conditions
3. **Conditional actions** - Use conditions to skip unnecessary actions
4. **Failure handling** - Configure `on_failure` for critical action sequences
5. **Descriptive names** - Use clear action and workflow names
6. **Modular design** - Keep actions focused on single responsibilities
7. **Test incrementally** - Start with single projects before running on all projects

## Example: Complete Migration Workflow

```toml
name = "Python Migration"
description = "Migrate Python projects to modern standards"
clone_repository = true
create_pull_request = true

[filter]
project_types = ["apis", "consumers"]
project_facts = {"Programming Language" = "Python 3.9"}

[[conditions]]
remote_file_exists = "setup.cfg"

[[actions]]
name = "generate-config"
type = "claude"
prompt_file = "generate.md.j2"

[[actions]]
name = "validate-config"
type = "claude"
prompt_file = "validate.md.j2"
on_failure = "generate-config"

[[actions]]
name = "cleanup"
type = "shell"
command = "rm -f legacy-files"
```

This workflow demonstrates project filtering, conditions, Claude Code integration with failure handling, and cleanup operations.
