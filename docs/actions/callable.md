# Callable Actions

Callable actions invoke methods directly on client instances (GitHub, GitLab, Imbi), enabling dynamic API operations with template variable support.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "callable"

[actions.value]
client = "github|gitlab|imbi"
method = "method_name"

[actions.value.kwargs]
param1 = "value1"
param2 = "{{ template_var }}"
```

## Fields

### client (required)

The client instance to call the method on.

**Options:** `github`, `gitlab`, `imbi`

### method (required)

The method name to invoke on the client.

**Type:** `string` (method name)

### kwargs (optional)

Dictionary of keyword arguments to pass to the method. Values support Jinja2 templates.

**Type:** `dict[str, any]`

## Examples

### GitHub Operations

```toml
[[actions]]
name = "create-pr"
type = "callable"

[actions.value]
client = "github"
method = "create_pull_request"

[actions.value.kwargs]
title = "Automated update for {{ imbi_project.name }}"
body = "This PR updates configurations"
head_branch = "automation/{{ workflow.slug }}"
base_branch = "main"
```

### Imbi Updates

```toml
[[actions]]
name = "update-project-fact"
type = "callable"

[actions.value]
client = "imbi"
method = "update_project_fact"

[actions.value.kwargs]
project_id = "{{ imbi_project.id }}"
fact_name = "Last Updated"
fact_value = "{{ now() }}"
```

### GitLab Operations

```toml
[[actions]]
name = "create-merge-request"
type = "callable"

[actions.value]
client = "gitlab"
method = "create_merge_request"

[actions.value.kwargs]
project_id = "{{ gitlab_project.id }}"
source_branch = "feature/update"
target_branch = "main"
title = "Update {{ imbi_project.name }}"
```

## Available Clients

### GitHub Client

Common methods:
- `create_pull_request()`
- `update_repository_settings()`
- `sync_environments()`
- `get_workflow_status()`

### GitLab Client

Common methods:
- `create_merge_request()`
- `update_project_settings()`
- `get_pipeline_status()`

### Imbi Client

Common methods:
- `update_project_fact()`
- `add_project_link()`
- `update_project_metadata()`

## Common Patterns

### Update After Transformation

```toml
[[actions]]
name = "update-code"
type = "claude"
prompt = "workflow:///prompts/update.md"

[[actions]]
name = "mark-updated"
type = "callable"

[actions.value]
client = "imbi"
method = "update_project_fact"

[actions.value.kwargs]
project_id = "{{ imbi_project.id }}"
fact_name = "Automation Status"
fact_value = "Updated"
```

### Conditional API Call

```toml
{% if github_repository %}
[[actions]]
name = "update-github"
type = "callable"

[actions.value]
client = "github"
method = "update_repository_settings"

[actions.value.kwargs]
repository = "{{ github_repository.full_name }}"
allow_squash_merge = true
{% endif %}
```

## Implementation Notes

- Methods called asynchronously
- Kwargs support full Jinja2 template syntax
- Client instances authenticated from config
- Method return values logged at DEBUG level
- Errors raised if method doesn't exist or call fails
