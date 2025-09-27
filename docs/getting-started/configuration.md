# Configuration

## Configuration File Format

Imbi Automations uses TOML configuration files for API credentials and settings:

```toml
[github]
api_key = "ghp_your_github_token_here"
hostname = "github.com"  # Optional, defaults to github.com

[imbi]
api_key = "your-imbi-uuid-key-here"
hostname = "imbi.example.com"

[claude_code]
executable = "claude"  # Optional, defaults to 'claude'
```

## API Keys and Authentication

### GitHub Configuration

For GitHub.com:
```toml
[github]
api_key = "ghp_xxxxxxxxxxxxxxxxxxxx"
```

For GitHub Enterprise:
```toml
[github]
api_key = "ghp_xxxxxxxxxxxxxxxxxxxx"
hostname = "github.enterprise.com"
```

**Getting a GitHub Token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with required scopes:
   - `repo` (for private repositories)
   - `workflow` (for GitHub Actions)
   - `read:org` (for organization data)

### Imbi Configuration

```toml
[imbi]
api_key = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
hostname = "imbi.yourdomain.com"
```

**Getting an Imbi API Key:**
Contact your Imbi administrator to generate an API key with appropriate permissions.

### Claude Code Integration

```toml
[claude_code]
executable = "claude"  # Path to Claude Code CLI
```

**Installing Claude Code:**
Follow the installation guide at [claude.ai/code](https://claude.ai/code)

## Environment Variables

You can also use environment variables instead of config files:

```bash
export GITHUB_API_KEY="ghp_xxxxxxxxxxxxxxxxxxxx"
export GITHUB_HOSTNAME="github.enterprise.com"
export IMBI_API_KEY="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export IMBI_HOSTNAME="imbi.yourdomain.com"
```

## Configuration Validation

The configuration is validated using Pydantic models. Common validation errors:

- **Invalid API key format**: Ensure GitHub tokens start with `ghp_` or similar
- **Invalid hostname**: Must be a valid domain name
- **Missing required fields**: `api_key` is required for each service

## Multiple Configurations

You can maintain different configuration files for different environments:

```bash
# Production environment
imbi-automations prod-config.toml

# Development environment
imbi-automations dev-config.toml
```

## Security Best Practices

- **Never commit API keys to version control**
- Store configuration files outside the repository
- Use environment variables in CI/CD pipelines
- Rotate API keys regularly
- Use minimal required scopes for tokens
