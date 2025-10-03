# Claude Actions

Claude actions leverage the Claude Code SDK for AI-powered code transformations, enabling complex multi-file analysis and intelligent code modifications that would be difficult or error-prone with traditional approaches.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "claude"
prompt = "prompt-file-or-url"          # Required
agent = "task"                         # Optional, default: "task"
validator_prompt = "validator-prompt"  # Optional
max_cycles = 3                         # Optional, default: 3
on_failure = "cleanup-action"          # Optional
```

## Fields

### prompt (required)

Path to Jinja2 template file containing the prompt for Claude.

**Type:** `ResourceUrl` (string path)
**Format:** Jinja2 template with full workflow context
**Location:** Usually in `workflow:///prompts/` directory

### agent (optional)

Agent type to use for the transformation.

**Type:** `string`
**Options:**
- `task` (default): General-purpose transformation agent
- `validator`: Validation-focused agent

### validator_prompt (optional)

Path to validation prompt template. Used to verify transformation success.

**Type:** `ResourceUrl` (string path)

### max_cycles (optional)

Maximum number of retry cycles if transformation fails.

**Type:** `integer`
**Default:** `3`
**Range:** 1-10

### on_failure (optional)

Action name to restart from if this action fails after all retry cycles.

**Type:** `string` (action name)

## Prompt Context

Prompts have access to all workflow context variables:

| Variable | Description |
|----------|-------------|
| `workflow` | Workflow configuration |
| `imbi_project` | Imbi project data |
| `github_repository` | GitHub repository (if applicable) |
| `gitlab_project` | GitLab project (if applicable) |
| `working_directory` | Execution directory path |
| `starting_commit` | Initial commit SHA |
| `commit_author` | Git commit author (from config) |
| `commit_author_name` | Author name only |
| `commit_author_address` | Author email only |
| `workflow_name` | Current workflow name |

## Examples

### Basic Code Transformation

**Workflow config:**
```toml
[[actions]]
name = "update-python-version"
type = "claude"
prompt = "workflow:///prompts/update-python.md"
```

**Prompt (`prompts/update-python.md`):**
```markdown
# Update Python Version to 3.12

Update all Python version references in this repository to Python 3.12.

## Files to Update

1. `pyproject.toml` - Update `requires-python` field
2. `.github/workflows/*.yml` - Update GitHub Actions Python version
3. `Dockerfile` - Update base image to python:3.12
4. `README.md` - Update installation instructions if they mention Python version

## Requirements

- Maintain backwards compatibility where possible
- Update all version strings consistently
- Preserve existing configuration structure
- Do not modify other unrelated settings

## Project Context

- **Project**: {{ imbi_project.name }}
- **Type**: {{ imbi_project.project_type }}
- **Current Python**: {{ imbi_project.facts.get('Programming Language', 'unknown') }}

## Success Criteria

Create a commit with all Python version references updated to 3.12.

## Failure Indication

If you cannot complete this task, create a file named `ACTION_FAILED` with details about what prevented completion.
```

### Multi-Cycle Transformation with Retry

**Workflow config:**
```toml
[[actions]]
name = "refactor-codebase"
type = "claude"
prompt = "workflow:///prompts/refactor.md"
max_cycles = 5
on_failure = "create-issue"  # Create GitHub issue if fails
```

### With Validator

**Workflow config:**
```toml
[[actions]]
name = "update-dependencies"
type = "claude"
prompt = "workflow:///prompts/update-deps.md"
validator_prompt = "workflow:///prompts/validate-deps.md"
agent = "task"
```

**Validator prompt:**
```markdown
# Validate Dependency Updates

Verify that the dependency updates were successful:

1. Check that `requirements.txt` or `pyproject.toml` has been updated
2. Verify no breaking changes were introduced
3. Confirm all imports still resolve correctly
4. Check that version constraints are reasonable

Return success if validation passes, failure otherwise with specific errors.
```

### Complex Transformation

**Workflow config:**
```toml
[[actions]]
name = "migrate-to-pydantic-v2"
type = "claude"
prompt = "workflow:///prompts/pydantic-migration.md"
max_cycles = 10
```

**Prompt:**
```markdown
# Migrate to Pydantic V2

Migrate this codebase from Pydantic v1 to Pydantic v2.

## Migration Steps

1. **Update imports**: Change `pydantic` imports to v2 syntax
2. **Config classes**: Convert `Config` class to `model_config` dict
3. **Validators**: Update `@validator` to `@field_validator`
4. **Field definitions**: Update `Field(...)` syntax changes
5. **JSON methods**: Replace `.dict()` with `.model_dump()`, `.json()` with `.model_dump_json()`

## Files to Process

Scan the repository for Python files containing:
- `from pydantic import`
- `class.*\\(.*BaseModel\\)`
- `@validator`
- `.dict()` or `.json()` calls on Pydantic models

## Testing

After making changes:
1. Run tests if they exist: `pytest tests/`
2. Check for import errors
3. Verify all models still validate correctly

## Commit Message

```
Migrate from Pydantic v1 to v2

- Update imports to v2 syntax
- Convert Config classes to model_config
- Update validators to field_validator
- Replace .dict()/.json() with .model_dump()/.model_dump_json()

Project: {{ imbi_project.name }}
```

## Failure Conditions

Create `PYDANTIC_MIGRATION_FAILED` file if:
- Unable to identify Pydantic usage patterns
- Migration would break existing functionality
- Tests fail after migration
- Manual intervention required

Include specific error details and affected files.
```

## Prompt Best Practices

### Clear Objectives

```markdown
# Update Docker Base Image

**Goal**: Update the Dockerfile to use python:3.12-slim as the base image.

**Files**: `Dockerfile`, `docker-compose.yml`

**Requirements**:
- Change base image in all Dockerfiles
- Maintain multi-stage build structure if present
- Update docker-compose.yml references
- Keep existing COPY, RUN, CMD instructions
```

### Specific Instructions

```markdown
## Step-by-Step Process

1. Locate all Dockerfile* files in the repository
2. For each Dockerfile:
   a. Find the `FROM` instruction
   b. Replace with `FROM python:3.12-slim`
   c. Keep any `AS builder` or stage names
3. Update docker-compose.yml if it hardcodes Python version
4. Commit changes with message: "Update Python base image to 3.12"
```

### Success/Failure Criteria

```markdown
## Success Criteria

You must:
- ✓ Update all Dockerfiles
- ✓ Maintain working configuration
- ✓ Create a git commit
- ✓ Include descriptive commit message

## Failure Indication

Create `DOCKER_UPDATE_FAILED` file if:
- No Dockerfile found in repository
- Unable to parse existing Dockerfile syntax
- Changes would break the build process
- Multiple conflicting Dockerfile versions exist

Include the specific error and list of files examined.
```

### Project Context Usage

```markdown
## Project-Specific Considerations

- **Project**: {{ imbi_project.name }}
- **Type**: {{ imbi_project.project_type }}
- **Namespace**: {{ imbi_project.namespace }}

{% if imbi_project.project_type == 'api' %}
This is an API project - ensure uvicorn/fastapi configurations are preserved.
{% elif imbi_project.project_type == 'consumer' %}
This is a consumer - ensure message handling configurations are intact.
{% endif %}

{% if imbi_project.facts %}
## Known Facts
{% for key, value in imbi_project.facts.items() %}
- **{{ key }}**: {{ value }}
{% endfor %}
{% endif %}
```

## Failure Handling

### Failure Files

Claude actions detect failure through specific files created in the working directory:

| File Name | Meaning |
|-----------|---------|
| `ACTION_FAILED` | Generic action failure |
| `{ACTION_NAME}_FAILED` | Specific action failure |
| Custom names | Custom failure indicators |

**Prompt instructions for failure:**
```markdown
## Failure Indication

If you cannot complete this task, create a file named `UPDATE_DEPENDENCIES_FAILED` containing:

1. **Reason**: Why the task failed
2. **Files Examined**: List of files you checked
3. **Errors Encountered**: Specific error messages
4. **Manual Steps**: What a human would need to do
5. **Context**: Any relevant information for debugging

Example:
```
REASON: Unable to parse pyproject.toml due to syntax error
FILES: pyproject.toml, requirements.txt
ERROR: toml.decoder.TomlDecodeError at line 15
MANUAL: Fix toml syntax error in pyproject.toml line 15
```
```

### Retry Mechanism

```toml
[[actions]]
name = "fragile-transformation"
type = "claude"
prompt = "workflow:///prompts/transform.md"
max_cycles = 5        # Try up to 5 times
on_failure = "cleanup" # Run cleanup action if all cycles fail
```

**Cycle behavior:**
1. Execute transformation
2. Check for failure files
3. If failure detected and cycles remaining, retry
4. If all cycles exhausted, trigger `on_failure` action
5. Pass error context to retry attempts

### Error Context in Retries

On retry, the prompt receives additional context:

```python
# Appended to prompt automatically:
"""
---
You need to fix problems identified from a previous run.
The errors for context are:

{
  "result": "failure",
  "message": "Unable to update dependencies",
  "errors": ["Package X not found", "Version conflict with Y"]
}
"""
```

## Advanced Usage

### Conditional Prompts

**Workflow:**
```toml
[[actions]]
name = "language-specific-update"
type = "claude"
prompt = "workflow:///prompts/{{ imbi_project.facts.get('Programming Language', 'unknown') | lower }}-update.md"
```

### Multi-Stage Transformations

```toml
[[actions]]
name = "stage1-refactor"
type = "claude"
prompt = "workflow:///prompts/stage1.md"

[[actions]]
name = "stage2-optimize"
type = "claude"
prompt = "workflow:///prompts/stage2.md"

[[actions]]
name = "stage3-document"
type = "claude"
prompt = "workflow:///prompts/stage3.md"
```

### With Pre/Post Actions

```toml
[[actions]]
name = "backup-files"
type = "file"
command = "copy"
source = "repository:///src/"
destination = "repository:///src.backup/"

[[actions]]
name = "ai-refactor"
type = "claude"
prompt = "workflow:///prompts/refactor.md"
on_failure = "restore-backup"

[[actions]]
name = "run-tests"
type = "shell"
command = "pytest tests/"
working_directory = "repository:///"

[[actions]]
name = "restore-backup"
type = "file"
command = "move"
source = "repository:///src.backup/"
destination = "repository:///src/"
```

## Integration with Other Actions

### Claude + Shell (Test Verification)

```toml
[[actions]]
name = "ai-code-update"
type = "claude"
prompt = "workflow:///prompts/update.md"

[[actions]]
name = "verify-tests"
type = "shell"
command = "pytest tests/ -v"
working_directory = "repository:///"
```

### Claude + File (Template Application)

```toml
[[actions]]
name = "generate-base-config"
type = "template"
source_path = "workflow:///config.yaml.j2"
destination_path = "repository:///config.yaml"

[[actions]]
name = "customize-config"
type = "claude"
prompt = "workflow:///prompts/customize-config.md"
```

### Claude + Git (Commit Verification)

```toml
[[actions]]
name = "ai-transformation"
type = "claude"
prompt = "workflow:///prompts/transform.md"

[[actions]]
name = "verify-commit"
type = "shell"
command = "git log -1 --pretty=%B"
working_directory = "repository:///"
```

## Performance Considerations

- **API Costs**: Each cycle makes Claude API calls
- **Execution Time**: Complex transformations can take several minutes
- **Context Size**: Large repositories may hit context limits
- **Rate Limiting**: Respect Anthropic API rate limits

## Security Considerations

- **Code Execution**: Claude can execute arbitrary code in the repository context
- **Sensitive Data**: Prompts and code are sent to Anthropic API
- **API Keys**: Ensure API keys are properly secured
- **Verification**: Always verify AI-generated changes before merging

## Implementation Notes

- Uses Claude Code SDK with MCP tool support
- Supports both agent-based and direct API queries
- Custom agents defined in `claude-code/agents/` directory
- Working directory isolated per execution
- Automatic cleanup on success or failure
- Full logging of Claude interactions at DEBUG level
