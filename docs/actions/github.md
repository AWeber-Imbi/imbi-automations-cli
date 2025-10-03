# GitHub Actions

GitHub actions provide GitHub-specific operations like environment synchronization and workflow management.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "github"
command = "sync_environments"
# Command-specific fields
```

## Commands

### sync_environments

**Status:** ❌ Not yet implemented (raises NotImplementedError)

Synchronize GitHub repository environments with Imbi project environments.

**Example:**
```toml
[[actions]]
name = "sync-github-envs"
type = "github"
command = "sync_environments"
```

**Planned Behavior:**
- Read environments from Imbi project
- Create/update GitHub repository environments
- Synchronize environment variables and secrets
- Maintain environment protection rules

## Common Use Cases

**Note:** These examples show the intended usage once `sync_environments` is implemented.

### Environment Synchronization

```toml
[[conditions]]
remote_file_exists = ".github/workflows/deploy.yml"

[[actions]]
name = "ensure-environments"
type = "github"
command = "sync_environments"
```

### Post-Deployment Updates

```toml
[[actions]]
name = "deploy-code"
type = "shell"
command = "deploy.sh"

[[actions]]
name = "update-environments"
type = "github"
command = "sync_environments"
```

## Implementation Status

Currently, the GitHub action type is defined but not implemented:
- `sync_environments`: Raises `NotImplementedError`

The action type exists in the codebase but will error when executed. This is likely a placeholder for future functionality.

## Planned Implementation Notes

When implemented, the action would:
- Require GitHub API access with appropriate permissions
- Use authenticated GitHub client from workflow context
- Respect GitHub API rate limits
- Provide idempotent operations (safe to re-run)
- Integrate with Imbi project environment configuration
