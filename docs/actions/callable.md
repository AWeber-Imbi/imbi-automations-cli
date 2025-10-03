# Callable Actions

⚠️ **NOT IMPLEMENTED**: Callable actions raise `NotImplementedError`. This action type is currently a placeholder.

Callable actions are intended to invoke Python callable objects (functions, methods, classes) dynamically with flexible arguments.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "callable"
import = "module.path.to.callable"
callable = "function_or_class_name"
args = []      # Optional positional arguments
kwargs = {}    # Optional keyword arguments
ai_commit = true  # Optional, default: true
```

## Fields

### import (required)

Python module path to import the callable from.

**Type:** `string`

**Field Name:** `import` (model field: `import_name`)


**Example:** `"imbi_automations.clients.github"`


### callable (required)

The callable object (function, method, or class) to invoke.

**Type:** `Callable` (Python callable object)


**Note:** The model expects an actual callable object, not a string. The TOML configuration likely needs to reference importable callables by name.

### args (optional)

Positional arguments to pass to the callable.

**Type:** `list`

**Default:** `[]`


### kwargs (optional)

Keyword arguments to pass to the callable.

**Type:** `dict`

**Default:** `{}`


### ai_commit (optional)

Whether to use AI-generated commit messages for changes.

**Type:** `boolean`

**Default:** `true`


## Implementation Status

**Status:** ❌ Not implemented

The implementation in `src/imbi_automations/actions/callablea.py` line 25 shows:

```python
async def execute(self, action: models.WorkflowCallableAction) -> None:
    raise NotImplementedError('Callable actions not yet supported')
```

**Model Definition:** `src/imbi_automations/models/workflow.py:107-120`

```python
class WorkflowCallableAction(WorkflowAction):
    type: typing.Literal['callable'] = 'callable'
    import_name: str = pydantic.Field(alias='import')
    callable: typing.Callable
    args: list[typing.Any] = pydantic.Field(default_factory=list)
    kwargs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    ai_commit: bool = True
```

## Intended Usage Examples

**Note:** These examples show the intended usage once implemented. They will currently fail with `NotImplementedError`.

### Call GitHub Client Method

```toml
[[actions]]
name = "create-github-issue"
type = "callable"
import = "imbi_automations.clients.github"
callable = "GitHubClient.create_issue"

[[actions.kwargs]]
title = "Automated issue"
body = "Issue created by workflow"
```

### Call Imbi Client Method

```toml
[[actions]]
name = "update-project"
type = "callable"
import = "imbi_automations.clients.imbi"
callable = "ImbiClient.update_project_fact"

[[actions.kwargs]]
project_id = 123
fact_name = "Automation Status"
fact_value = "Updated"
```

### Call Utility Function

```toml
[[actions]]
name = "parse-version"
type = "callable"
import = "semver"
callable = "parse"
args = ["1.2.3"]
```

## Design Questions

The current model definition has some unclear aspects:

1. **Callable Type**: The `callable` field expects a `typing.Callable` object, but TOML configuration can only contain strings. How is this resolved?

2. **Import Resolution**: How does `import` + `callable` get resolved to an actual callable object? Is `callable` a string name looked up in the imported module?

3. **Client Access**: How would this access workflow clients (GitHub, GitLab, Imbi) that are already instantiated in the workflow context?

4. **Context Passing**: How would the callable receive workflow context (repository, project data, etc.)?

These design questions suggest the feature may need additional planning before implementation.

## Workarounds

Until callable actions are implemented, use alternative approaches:

1. **Client Operations**: Use specific action types (github, imbi) when they exist
2. **Custom Logic**: Use shell actions to call Python scripts
3. **Claude Actions**: Use Claude for complex operations requiring decision-making

### Shell Action Alternative

```toml
[[actions]]
name = "custom-operation"
type = "shell"
command = "python -c 'from mymodule import func; func()'"
working_directory = "repository:///"
```

## Implementation Notes

- Action type defined but not implemented
- Raises `NotImplementedError` on execution
- Model uses `typing.Callable` which may need runtime resolution
- Field `import` aliased to `import_name` to avoid Python keyword
- Intended for direct Python callable invocation with flexible arguments
- AI commit enabled by default when implemented
