# Utility Actions

⚠️ **ALL COMMANDS NOT IMPLEMENTED**: All utility commands currently raise `NotImplementedError`. This action type is a placeholder for future functionality.

Utility actions are intended to provide helper operations for Docker tag parsing, Dockerfile analysis, semantic versioning comparison, and Python constraint parsing.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "utility"
command = "docker_tag|dockerfile_from|compare_semver|parse_python_constraints"
path = "repository:///path/to/file"  # Optional
args = []      # Optional
kwargs = {}    # Optional
```

## Fields

### command (required)

The utility operation to perform.

**Type:** `string`

**Options:**

- `docker_tag` - Parse Docker image tags (not implemented)
- `dockerfile_from` - Extract FROM directive from Dockerfile (not implemented)
- `compare_semver` - Compare semantic version strings (not implemented)
- `parse_python_constraints` - Parse Python version constraints (not implemented)

### path (optional)

File path for operations that require file input.

**Type:** [`ResourceUrl`](index.md#resourceurl-path-system) (string path)

**Default:** None


### args (optional)

Positional arguments for the utility operation.

**Type:** `list`

**Default:** `[]`


### kwargs (optional)

Keyword arguments for the utility operation.

**Type:** `dict`

**Default:** `{}`


## Commands

### docker_tag

**Status:** ❌ Not implemented (raises NotImplementedError)

Parse and manipulate Docker image tags.

**Intended Usage:**
```toml
[[actions]]
name = "parse-docker-tag"
type = "utility"
command = "docker_tag"
args = ["python:3.12-slim"]
```

### dockerfile_from

**Status:** ❌ Not implemented (raises NotImplementedError)

Extract the base image FROM directive from a Dockerfile.

**Intended Usage:**
```toml
[[actions]]
name = "get-base-image"
type = "utility"
command = "dockerfile_from"
path = "repository:///Dockerfile"
```

### compare_semver

**Status:** ❌ Not implemented (raises NotImplementedError)

Compare two semantic version strings.

**Intended Usage:**
```toml
[[actions]]
name = "check-version"
type = "utility"
command = "compare_semver"
args = ["1.2.3", "1.2.4"]
```

### parse_python_constraints

**Status:** ❌ Not implemented (raises NotImplementedError)

Parse Python version constraint strings (e.g., `>=3.8,<4.0`).

**Intended Usage:**
```toml
[[actions]]
name = "parse-constraints"
type = "utility"
command = "parse_python_constraints"
args = [">=3.8,<4.0"]
```

## Implementation Status

Currently, all utility commands are defined but not implemented. The implementation in `src/imbi_automations/actions/utility.py` lines 24-43 shows:

```python
async def execute(self, action: models.WorkflowUtilityAction) -> None:
    match action.command:
        case models.WorkflowUtilityCommands.docker_tag:
            raise NotImplementedError('Utility docker_tag not yet supported')
        case models.WorkflowUtilityCommands.dockerfile_from:
            raise NotImplementedError('Utility dockerfile_from not yet supported')
        case models.WorkflowUtilityCommands.compare_semver:
            raise NotImplementedError('Utility compare_semver not yet supported')
        case models.WorkflowUtilityCommands.parse_python_constraints:
            raise NotImplementedError('Utility parse_python_constraints not yet supported')
```

**Workarounds:**

Until these utilities are implemented, use alternative approaches:


1. **Docker tag parsing**: Use shell action with `docker inspect` or regex
2. **Dockerfile FROM**: Use file action with regex pattern or shell action with `grep`
3. **Semver comparison**: Use shell action with `semver` CLI tool
4. **Python constraints**: Use shell action with Python's `packaging` library

## Implementation Notes

- All commands currently raise `NotImplementedError`
- Model defined in `src/imbi_automations/models/workflow.py:373-398`
- Implementation skeleton in `src/imbi_automations/actions/utility.py:1-44`
- Fields `path`, `args`, and `kwargs` are defined but unused
- This action type exists as a placeholder for future functionality
