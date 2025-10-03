# GitHub Actions

GitHub actions provide GitHub-specific operations like environment synchronization and workflow management.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "github"
operation = "sync_environments"
# Operation-specific fields
```

## Operations

### sync_environments

Synchronize GitHub repository environments with Imbi project environments.

**Example:**
```toml
[[actions]]
name = "sync-github-envs"
type = "github"
operation = "sync_environments"
```

**Behavior:**
- Reads environments from Imbi project
- Creates/updates GitHub repository environments
- Synchronizes environment variables and secrets
- Maintains environment protection rules

## Common Use Cases

### Environment Synchronization

```toml
[[conditions]]
remote_file_exists = ".github/workflows/deploy.yml"

[[actions]]
name = "ensure-environments"
type = "github"
operation = "sync_environments"
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
operation = "sync_environments"
```

## Implementation Notes

- Requires GitHub API access
- Uses authenticated GitHub client
- Respects GitHub API rate limits
- Idempotent operations (safe to re-run)
