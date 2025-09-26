# Workflow Configuration Reference

Complete reference for `config.toml` workflow files in Imbi Automations.

## Basic Structure

```toml
name = "Workflow Name"
description = "Optional description"
clone_repository = true
create_pull_request = true
ci_skip_checks = false
shallow_clone = true

[filter]
# Project filtering options

[[conditions]]
# Workflow execution conditions

[[actions]]
# Workflow actions
```

## Workflow Properties

### Required
- **`name`** (string): Workflow name

### Optional
- **`description`** (string): Workflow description
- **`clone_repository`** (boolean): Clone repository before execution (default: true)
- **`create_pull_request`** (boolean): Create PR after workflow (default: true)
- **`ci_skip_checks`** (boolean): Add `[ci skip]` to commits (default: false)
- **`shallow_clone`** (boolean): Use shallow clone (default: true)
- **`condition_type`** (string): Logic for multiple conditions ("all" or "any", default: "all")

## Project Filtering

Optional `[filter]` section to target specific projects:

```toml
[filter]
project_ids = [123, 456]
project_types = ["apis", "consumers"]
project_facts = {"Programming Language" = "Python 3.9"}
project_environments = ["staging", "production"]
requires_github_identifier = true
exclude_github_workflow_status = ["success"]
```

- **`project_ids`**: Array of specific project IDs
- **`project_types`**: Array of project type slugs
- **`project_facts`**: Key-value pairs for exact fact matching
- **`project_environments`**: Array of required environments
- **`requires_github_identifier`**: Only projects with GitHub repos
- **`exclude_github_workflow_status`**: Skip projects with these GitHub Actions statuses

## Conditions

Workflow execution conditions. All must pass unless `condition_type = "any"`.

### Remote Conditions (GitHub API)
```toml
[[conditions]]
remote_file_exists = "setup.cfg"

[[conditions]]
remote_file_not_exists = "pyproject.toml"

[[conditions]]
remote_file_contains = "version.*3\\.9"
remote_file = "setup.cfg"
```

### Local Conditions (After Clone)
```toml
[[conditions]]
file_exists = "package.json"

[[conditions]]
file_not_exists = "legacy.cfg"

[[conditions]]
file_contains = "test.*script"
file = "package.json"
```

## Actions

Sequential workflow steps. Each action has a `type` that determines its behavior.

### Common Action Fields
- **`name`** (string, required): Unique action name
- **`type`** (string, required): Action type
- **`on_failure`** (string): Action to restart from on failure
- **`condition`** (string): Legacy condition string
- **`condition_type`** (string): "all" or "any" for multiple conditions

### Action Conditions
```toml
[[actions]]
name = "conditional-action"

[[actions.conditions]]
file_exists = "setup.cfg"
```

## Action Types

### 1. Default (Client Method Call)
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

### 2. `ai-editor`
```toml
[[actions]]
name = "update-readme"
type = "ai-editor"
prompt_file = "prompt.md"
target_file = "README.md"
```

### 3. `claude`
```toml
[[actions]]
name = "migrate-config"
type = "claude"
prompt_file = "migrate.md.j2"
timeout = 600
max_retries = 3
on_failure = "prepare-migration"
```

### 4. `shell`
```toml
[[actions]]
name = "run-tests"
type = "shell"
command = "pytest --cov=src"
on_failure = "fix-tests"
```

### 5. `file`
```toml
[[actions]]
name = "copy-config"
type = "file"
command = "copy"
source = "template.yml"
destination = "config.yml"
```

**Commands**: `copy`, `rename`, `remove`

### 6. `templates`
```toml
[[actions]]
name = "render-templates"
type = "templates"
source = "templates/"
```

### 7. `git-extract`
```toml
[[actions]]
name = "extract-original"
type = "git-extract"
keyword = "g2g-migration"
strategy = "before_first_match"
source = "Dockerfile"
target_path = "Dockerfile.original"
```

**Fields**:
- **`keyword`** (required): Commit message keyword
- **`strategy`**: "before_first_match" or "before_last_match"
- **`source`** (required): File to extract
- **`target_path`**: Output file path

### 8. `git-revert`
```toml
[[actions]]
name = "revert-config"
type = "git-revert"
keyword = "migration"
strategy = "before_first_match"
source = "config.yml"
```

### 9. `docker-extract`
```toml
[[actions]]
name = "extract-assets"
type = "docker-extract"
dockerfile_path = "Dockerfile"
source_path = "/app/dist"
target_path = "./dist"
```

### 10. `add-trailing-whitespace`
```toml
[[actions]]
name = "fix-whitespace"
type = "add-trailing-whitespace"
source = "config.txt"
```

## Template Context

Jinja2 variables available in prompt files and action configurations:

### Project Data
- `imbi_project.id`, `imbi_project.name`, `imbi_project.slug`
- `imbi_project.project_type`, `imbi_project.namespace_slug`
- `github_repository.owner.login`, `github_repository.name`
- `github_repository.html_url`, `github_repository.full_name`

### Execution Context
- `workflow_run`: Current execution details
- `actions`: Previous action results
- `previous_failure`: Failure details (during restarts)

## Failure Handling

### Failure Files
Claude actions create files to signal failures:
- `ACTION_FAILED`: Generic failure
- `{ACTION_NAME}_FAILED`: Action-specific failure

### Restart Mechanism
```toml
[[actions]]
name = "validate"
on_failure = "generate"  # Restart from generate action on failure
```

- Up to 3 failures per action before workflow abort
- Restart actions receive `previous_failure` context
- Failure tracking is per-action across all restart attempts
