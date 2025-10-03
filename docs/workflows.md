# Workflow Configuration

Workflows define automated processes to execute across projects. Each workflow is a directory containing a `config.toml` file that specifies actions, conditions, filters, and behavior.

## Three Levels of Project Selection

In addition to the `--project-id`, `--project-type`, and `--all-projects` command-line arguments, Imbi Automations provides three complementary mechanisms to control which projects to process and which actions execute:

### 1. **Project Filters** - Pre-filter before processing
Target specific project subsets using Imbi metadata:
- Project IDs, types, facts
- GitHub identifier requirements
- GitHub workflow status

**When evaluated:** Before any workflow processing begins
**Effect:** Projects that don't match are never processed
**Use for:** Broad targeting (e.g., "only Python APIs")

### 2. **Workflow Conditions** - Skip entire workflow
Check repository state to determine if workflow should run:
- Remote conditions (checked via API before cloning)
- Local conditions (checked after cloning repository)

**When evaluated:** Once per project, before any actions execute
**Effect:** If conditions fail, entire workflow is skipped for that project
**Use for:** Workflow applicability (e.g., "only if Dockerfile exists")

### 3. **Action Conditions** - Skip individual actions
Check repository state before each action:
- Same condition types as workflow conditions
- Evaluated independently for each action

**When evaluated:** Before each action executes
**Effect:** If conditions fail, only that specific action is skipped
**Use for:** Conditional behavior (e.g., "update setup.py only if it exists")

### Evaluation Flow

```
1. Filter projects        → Reduces: 1000 projects → 50 matching projects
   [filter] section

2. Check workflow         → Skips: 50 projects → 30 applicable projects
   conditions
   [[conditions]]

3. Clone repository       → Working with: 30 repositories

4. For each action:       → Executes: Only when action conditions pass
   Check action
   conditions
   [[actions.conditions]]
```

**Key Insight:** Use filters for broad targeting, workflow conditions for applicability checks, and action conditions for per-action variation within applicable projects.

## Workflow Structure

```
workflows/workflow-name/
├── config.toml          # Required - workflow configuration
├── prompts/             # Optional - Claude prompt templates
│   ├── task.md.j2
│   └── validator.md.j2
├── templates/           # Optional - Jinja2 templates
│   ├── config.yaml.j2
│   └── README.md.j2
└── files/               # Optional - static resources
    ├── .gitignore
    └── .pre-commit-config.yaml
```

## Minimal Configuration

The simplest workflow requires only a name and actions:

```toml
name = "update-gitignore"

[[actions]]
name = "copy-gitignore"
type = "file"
command = "copy"
source = "workflow:///.gitignore"
destination = "repository:///.gitignore"
```

## Complete Configuration

```toml
# Workflow Metadata
name = "update-python-version"
description = "Update Python version to 3.12 across all projects"
prompt = "workflow:///prompts/base-prompt.md"

# Project Filtering
[filter]
project_ids = [123, 456]
project_types = ["api", "consumer"]
project_facts = {"Programming Language" = "Python 3.11"}
github_identifier_required = true
github_workflow_status_exclude = ["success"]

# Git Configuration
[git]
clone = true
commit = true
commit_message = "Update Python to 3.12"

# GitHub Configuration
[github]
create_pull_request = true
replace_branch = true

# GitLab Configuration
[gitlab]
create_merge_request = true
replace_branch = false

# Workflow-Level Conditions
condition_type = "all"  # or "any"

[[conditions]]
remote_file_exists = "pyproject.toml"

[[conditions]]
remote_file_contains = "python.*3\\.11"
remote_file = "pyproject.toml"

# Actions
[[actions]]
name = "update-configs"
type = "claude"
prompt = "workflow:///prompts/update.md"
```

## Workflow Metadata

### name (required)

Workflow display name shown in logs and reports.

**Type:** `string`

```toml
name = "Update Python Dependencies"
```

### description (optional)

Human-readable description of workflow purpose.

**Type:** `string`

```toml
description = "Updates Python dependencies to latest compatible versions"
```

### prompt (optional)

Custom prompt file for Claude Code actions.

**Type:** `ResourceUrl` (path to prompt file)

```toml
prompt = "workflow:///prompts/base-prompt.md"
```

## Project Filtering

The `[filter]` section pre-filters projects before workflow execution.

### project_ids

Target specific projects by Imbi project ID.

**Type:** `list[int]`

```toml
[filter]
project_ids = [123, 456, 789]
```

### project_types

Filter by project type slugs.

**Type:** `list[string]`

```toml
[filter]
project_types = ["api", "consumer", "scheduled-job"]
```

### project_facts

Filter by exact fact value matches.

**Type:** `dict[string, string]`

```toml
[filter]
project_facts = {
    "Programming Language" = "Python 3.12",
    "Framework" = "FastAPI"
}
```

**Note:** All fact filters must match (AND logic).

### github_identifier_required

Require projects to have GitHub identifier.

**Type:** `boolean`
**Default:** `false`

```toml
[filter]
github_identifier_required = true
```

### github_workflow_status_exclude

Exclude projects with specific GitHub Actions workflow statuses.

**Type:** `list[string]`
**Values:** `"success"`, `"failure"`, `"pending"`, `"skipped"`

```toml
[filter]
github_workflow_status_exclude = ["success"]  # Only process failing/missing workflows
```

**Use Case:** Target only projects with failing builds.

## Git Configuration

The `[git]` section controls repository cloning and committing behavior.

### clone

Whether to clone the repository.

**Type:** `boolean`
**Default:** `true`

```toml
[git]
clone = true
```

**Note:** Most workflows require cloning. Set to `false` only for API-only workflows.

### commit

Whether to create Git commits after actions.

**Type:** `boolean`
**Default:** `true`

```toml
[git]
commit = true
```

### commit_message

Default commit message for workflow changes.

**Type:** `string`
**Default:** Workflow name

```toml
[git]
commit_message = "Update Python version to 3.12"
```

**Note:** Individual actions can override with `ai_commit = true` for AI-generated messages.

## GitHub Configuration

The `[github]` section controls GitHub integration.

### create_pull_request

Create GitHub pull request after committing changes.

**Type:** `boolean`
**Default:** `true`

```toml
[github]
create_pull_request = true
```

### replace_branch

Delete remote branch if it exists before creating new one.

**Type:** `boolean`
**Default:** `false`

```toml
[github]
create_pull_request = true
replace_branch = true  # Force-replace existing PR branch
```

**Note:** `replace_branch` requires `create_pull_request = true`.

## GitLab Configuration

The `[gitlab]` section controls GitLab integration.

### create_merge_request

Create GitLab merge request after committing changes.

**Type:** `boolean`
**Default:** `true`

```toml
[gitlab]
create_merge_request = true
```

### replace_branch

Delete remote branch if it exists before creating new one.

**Type:** `boolean`
**Default:** `false`

```toml
[gitlab]
create_merge_request = true
replace_branch = false
```

## Workflow Conditions

Workflow-level conditions determine if the entire workflow should execute.

### condition_type

How to evaluate multiple conditions.

**Type:** `string`
**Values:** `"all"` (AND), `"any"` (OR)
**Default:** `"all"`

```toml
condition_type = "all"  # All conditions must pass

[[conditions]]
remote_file_exists = "package.json"

[[conditions]]
remote_file_contains = "node.*18"
remote_file = ".nvmrc"
```

With `condition_type = "all"`, workflow executes only if BOTH conditions pass.

```toml
condition_type = "any"  # Any condition passing is sufficient

[[conditions]]
remote_file_exists = "requirements.txt"

[[conditions]]
remote_file_exists = "pyproject.toml"
```

With `condition_type = "any"`, workflow executes if EITHER file exists.

### Local Conditions

Evaluated after cloning repository (have full filesystem access).

#### file_exists

Check if file or directory exists.

**Type:** `ResourceUrl` (path)
**Supports:** Glob patterns (`*.py`, `**/*.yaml`)

```toml
[[conditions]]
file_exists = "Dockerfile"

[[conditions]]
file_exists = "**/*.tf"  # Any Terraform file recursively
```

#### file_not_exists

Check if file or directory does NOT exist.

**Type:** `ResourceUrl` (path)
**Supports:** Glob patterns

```toml
[[conditions]]
file_not_exists = ".travis.yml"  # No legacy CI

[[conditions]]
file_not_exists = "*.pyc"  # No compiled Python
```

#### file_contains / file

Check if file contains specific text or regex pattern.

**Type:** `string` (pattern)
**Requires:** `file` field with target file path

```toml
[[conditions]]
file_contains = "python.*3\\.12"
file = "pyproject.toml"

[[conditions]]
file_contains = "FROM python:3"
file = "Dockerfile"
```

**Pattern Matching:**
- String search first (fast)
- Falls back to regex if string not found
- Use regex escaping: `\\.` for literal `.`, `\\d` for digits

#### file_doesnt_contain / file

Check if file does NOT contain pattern.

```toml
[[conditions]]
file_doesnt_contain = "python.*3\\.9"
file = "pyproject.toml"
```

### Remote Conditions

Evaluated via API before cloning (faster, more efficient).

#### remote_file_exists

Check if file exists via API.

**Type:** `string` (path)
**Supports:** Glob patterns via Git Trees API

```toml
[[conditions]]
remote_file_exists = "package.json"

[[conditions]]
remote_file_exists = "**/*.tf"  # Any Terraform file
```

**Performance:** Much faster than cloning for simple checks.

#### remote_file_not_exists

Check if file does NOT exist via API.

```toml
[[conditions]]
remote_file_not_exists = ".travis.yml"
```

#### remote_file_contains / remote_file

Check if remote file contains pattern.

**Type:** `string` (pattern)
**Requires:** `remote_file` field

```toml
[[conditions]]
remote_file_contains = "\"node\":.*\"18"
remote_file = "package.json"

[[conditions]]
remote_file_contains = "FROM python:[3-4]"
remote_file = "Dockerfile"
```

#### remote_file_doesnt_contain / remote_file

Check if remote file does NOT contain pattern.

```toml
[[conditions]]
remote_file_doesnt_contain = "python.*2\\."
remote_file = "setup.py"
```

#### remote_client

Which API client to use for remote checks.

**Type:** `string`
**Values:** `"github"` (default), `"gitlab"`

```toml
[[conditions]]
remote_client = "gitlab"
remote_file_exists = ".gitlab-ci.yml"
```

### Condition Examples

**Check for Python project:**
```toml
condition_type = "any"

[[conditions]]
remote_file_exists = "pyproject.toml"

[[conditions]]
remote_file_exists = "requirements.txt"

[[conditions]]
remote_file_exists = "setup.py"
```

**Require Docker with Python 3.12:**
```toml
condition_type = "all"

[[conditions]]
remote_file_exists = "Dockerfile"

[[conditions]]
remote_file_contains = "FROM python:3\\.12"
remote_file = "Dockerfile"
```

**Exclude legacy projects:**
```toml
[[conditions]]
remote_file_not_exists = ".travis.yml"

[[conditions]]
remote_file_not_exists = "circle.yml"
```

## Actions

Actions define the operations to perform. Each action has:
- Common fields (all action types)
- Type-specific fields (documented in [Actions](actions/index.md))

### Common Action Fields

#### name (required)

Action identifier for logging and error messages.

**Type:** `string`

```toml
[[actions]]
name = "copy-gitignore"
```

#### type (required)

Action type determines which fields are available.

**Type:** `string`
**Values:** `callable`, `claude`, `docker`, `file`, `git`, `github`, `shell`, `template`, `utility`

```toml
[[actions]]
type = "file"
```

#### ai_commit (optional)

Use AI to generate commit message for this action's changes.

**Type:** `boolean`
**Default:** `false`
**Requires:** Anthropic API key configured

```toml
[[actions]]
name = "complex-refactor"
type = "claude"
ai_commit = true  # AI-generated commit message
```

#### committable (optional)

Whether this action's changes should be committed.

**Type:** `boolean`
**Default:** `true`

```toml
[[actions]]
name = "temporary-file"
type = "file"
committable = false  # Don't include in git commit
```

**Use Cases:**
- Temporary files for other actions
- Diagnostic output
- Intermediate processing

#### on_failure (optional)

Action name to restart from if this action fails.

**Type:** `string` (action name)
**Max Retries:** 3 per action

```toml
[[actions]]
name = "backup-files"
type = "file"
command = "copy"
source = "repository:///src/"
destination = "repository:///src.backup/"

[[actions]]
name = "risky-operation"
type = "claude"
on_failure = "restore-backup"

[[actions]]
name = "restore-backup"
type = "file"
command = "move"
source = "repository:///src.backup/"
destination = "repository:///src/"
```

### Action-Level Conditions

Actions can have their own conditions, evaluated before execution.

```toml
[[actions]]
name = "update-dockerfile"
type = "file"
condition_type = "all"
committable = true

# Action-level conditions
[[actions.conditions]]
file_exists = "Dockerfile"

[[actions.conditions]]
file_contains = "FROM python:3\\.11"
file = "Dockerfile"

# Action-specific fields
command = "write"
path = "repository:///Dockerfile"
content = "FROM python:3.12"
```

**Behavior:**
- Workflow conditions evaluated once (before clone)
- Action conditions evaluated before each action
- If action conditions fail, action is skipped (not a failure)

### Action Condition Type

Each action can specify how to evaluate its conditions.

```toml
[[actions]]
name = "update-python-files"
type = "template"
condition_type = "any"  # Any ONE condition passing is sufficient

[[actions.conditions]]
file_exists = "setup.py"

[[actions.conditions]]
file_exists = "pyproject.toml"

[[actions.conditions]]
file_exists = "requirements.txt"

# Execute template action if ANY Python config file exists
source_path = "workflow:///python-config.j2"
destination_path = "repository:///config.yaml"
```

## Complete Examples

### Simple File Copy Workflow

```toml
name = "Update .gitignore"
description = "Deploy standard .gitignore to all projects"

[git]
commit_message = "Update .gitignore from template"

[github]
create_pull_request = true

[[conditions]]
remote_file_exists = ".git"  # Must be git repo

[[actions]]
name = "copy-gitignore"
type = "file"
command = "copy"
source = "workflow:///.gitignore"
destination = "repository:///.gitignore"
```

### AI-Powered Migration Workflow

```toml
name = "Migrate to Pydantic V2"
description = "AI-powered migration from Pydantic v1 to v2"

[filter]
project_types = ["api", "consumer"]
project_facts = {"Programming Language" = "Python 3.12"}

[git]
commit_message = "Migrate to Pydantic v2"

[github]
create_pull_request = true
replace_branch = true

condition_type = "all"

[[conditions]]
remote_file_exists = "pyproject.toml"

[[conditions]]
remote_file_contains = "pydantic"
remote_file = "pyproject.toml"

[[actions]]
name = "backup-code"
type = "file"
command = "copy"
source = "repository:///src/"
destination = "repository:///src.backup/"
committable = false  # Don't commit backup

[[actions]]
name = "migrate-pydantic"
type = "claude"
prompt = "workflow:///prompts/pydantic-v2.md"
max_cycles = 5
on_failure = "restore-backup"
ai_commit = true  # AI-generated commit message

[[actions]]
name = "run-tests"
type = "shell"
command = "pytest tests/ -v"
working_directory = "repository:///"

[[actions]]
name = "restore-backup"
type = "file"
command = "move"
source = "repository:///src.backup/"
destination = "repository:///src/"
```

### Multi-Stage Template Workflow

```toml
name = "Generate Project Configs"
description = "Generate configuration files from templates"

[filter]
project_types = ["api"]
github_identifier_required = true

condition_type = "any"

[[conditions]]
remote_file_not_exists = "config/app.yaml"

[[conditions]]
remote_file_not_exists = "config/database.yaml"

[[actions]]
name = "render-configs"
type = "template"
source_path = "workflow:///templates/"
destination_path = "repository:///config/"

[[actions]]
name = "validate-configs"
type = "shell"
command = "yamllint config/"
working_directory = "repository:///"

[[actions]]
name = "update-readme"
type = "template"
source_path = "workflow:///README.md.j2"
destination_path = "repository:///README.md"

# Only update README if it exists
[[actions.conditions]]
file_exists = "repository:///README.md"
```

### Conditional Docker Update

```toml
name = "Update Docker Base Image"

[git]
commit_message = "Update Python Docker base image to 3.12"

[github]
create_pull_request = true

[[conditions]]
remote_file_exists = "Dockerfile"

[[conditions]]
remote_file_contains = "FROM python:[23]\\."
remote_file = "Dockerfile"

[[actions]]
name = "update-dockerfile"
type = "file"
command = "write"
path = "repository:///Dockerfile"

# Only execute if current image is old
[[actions.conditions]]
file_contains = "FROM python:(2\\.|3\\.[0-9]|3\\.1[01])"
file = "Dockerfile"

content = """
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
"""

[[actions]]
name = "update-compose"
type = "file"
command = "write"
path = "repository:///docker-compose.yml"

# Only if docker-compose exists
[[actions.conditions]]
file_exists = "docker-compose.yml"

content = """
version: '3.8'
services:
  app:
    build: .
    image: myapp:latest
"""
```

## Best Practices

### Use Remote Conditions

Remote conditions are faster and avoid unnecessary cloning:

```toml
# ✅ Good - check remotely first
[[conditions]]
remote_file_exists = "package.json"

[[conditions]]
remote_file_contains = "node.*18"
remote_file = "package.json"

# ❌ Slower - clones every repo
[[conditions]]
file_exists = "package.json"
```

### Filter Early

Use workflow filters to reduce processing scope:

```toml
# ✅ Good - filter at workflow level
[filter]
project_types = ["api"]
project_facts = {"Programming Language" = "Python 3.12"}

# ❌ Less efficient - processes all, filters per-action
[[actions.conditions]]
# checking project type in every action
```

### Action-Level Conditions for Variation

Use action conditions when behavior varies per project:

```toml
[[actions]]
name = "update-setup-py"
# Only runs if setup.py exists
[[actions.conditions]]
file_exists = "setup.py"

[[actions]]
name = "update-pyproject"
# Only runs if pyproject.toml exists
[[actions.conditions]]
file_exists = "pyproject.toml"
```

### Idempotent Workflows

Design workflows to be safely re-runnable:

```toml
# Check current state before modifying
[[actions.conditions]]
file_not_exists = "config/app.yaml"  # Only create if missing
```

## See Also

- [Actions Reference](actions/index.md) - Detailed action type documentation
- [CLI Reference](cli.md) - Command-line options
- [Configuration](configuration.md) - Global configuration options
- [Debugging](debugging.md) - Troubleshooting workflows
