# Utility Actions

Utility actions provide helper operations for common workflow patterns like logging, state management, and flow control.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "utility"
operation = "log|wait|skip"
# Operation-specific fields
```

## Operations

### log

Log messages during workflow execution.

**Fields:**
- `message`: Message to log (supports templates)
- `level`: Log level (`debug`, `info`, `warning`, `error`)

**Example:**
```toml
[[actions]]
name = "log-progress"
type = "utility"
operation = "log"
message = "Processing {{ imbi_project.name }}"
level = "info"
```

### wait

Pause workflow execution for a specified duration.

**Fields:**
- `seconds`: Duration to wait

**Example:**
```toml
[[actions]]
name = "rate-limit-pause"
type = "utility"
operation = "wait"
seconds = 5
```

### skip

Conditionally skip subsequent actions.

**Fields:**
- `condition`: Jinja2 expression evaluating to boolean

**Example:**
```toml
[[actions]]
name = "skip-if-api"
type = "utility"
operation = "skip"
condition = "{{ imbi_project.project_type == 'api' }}"
```

## Common Use Cases

### Progress Logging

```toml
[[actions]]
name = "log-start"
type = "utility"
operation = "log"
message = "Starting transformation for {{ imbi_project.slug }}"
level = "info"

[[actions]]
name = "transform"
type = "claude"
prompt = "workflow:///prompts/transform.md"

[[actions]]
name = "log-complete"
type = "utility"
operation = "log"
message = "Completed transformation"
level = "info"
```

### Rate Limiting

```toml
[[actions]]
name = "api-call"
type = "callable"
client = "github"
method = "create_pull_request"
kwargs = {}

[[actions]]
name = "rate-limit-wait"
type = "utility"
operation = "wait"
seconds = 2
```

### Conditional Workflow

```toml
[[actions]]
name = "check-type"
type = "utility"
operation = "skip"
condition = "{{ imbi_project.project_type not in ['api', 'consumer'] }}"

[[actions]]
name = "api-specific-action"
type = "shell"
command = "deploy-api.sh"
```

## Implementation Notes

- Utility actions don't modify files or repositories
- Log messages output to workflow logger
- Wait operations are non-blocking for other workflows
- Skip conditions evaluated at runtime
