# Shell Actions

Shell actions execute arbitrary commands with full Jinja2 template support for dynamic command construction and access to workflow context variables.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "shell"
command = "command to execute"
working_directory = "path"  # Optional
ignore_failure = false      # Optional, default: false
```

## Fields

### command (required)

The shell command to execute. Supports full Jinja2 template syntax for variable substitution.

**Type:** `string`

**Template Variables Available:**
- `workflow`: Workflow configuration object
- `imbi_project`: Complete Imbi project data
- `github_repository`: GitHub repository object (if applicable)
- `gitlab_project`: GitLab project object (if applicable)
- `working_directory`: Path to workflow working directory
- `starting_commit`: Initial Git commit SHA

### working_directory (optional)

Directory to execute the command in. Defaults to the workflow's working directory.

**Type:** `ResourceUrl` (string path)
**Default:** `{working_directory}`

### ignore_failure (optional)

Whether to continue workflow execution if the command fails (non-zero exit code).

**Type:** `boolean`
**Default:** `false`

## Examples

### Basic Command Execution

```toml
[[actions]]
name = "run-tests"
type = "shell"
command = "pytest tests/ -v"
```

### Command with Working Directory

```toml
[[actions]]
name = "build-project"
type = "shell"
command = "python setup.py build"
working_directory = "{{ working_directory }}/repository"
```

### Template Variable Usage

```toml
[[actions]]
name = "create-tag"
type = "shell"
command = "git tag -a v{{ version }} -m 'Release {{ version }} for {{ imbi_project.name }}'"
working_directory = "repository:///"
```

### Complex Multi-line Commands

```toml
[[actions]]
name = "setup-and-test"
type = "shell"
command = """
python -m venv .venv && \
source .venv/bin/activate && \
pip install -e .[dev] && \
pytest tests/ --cov={{ imbi_project.slug }}
"""
working_directory = "{{ working_directory }}/repository"
```

### Conditional Execution

```toml
[[actions]]
name = "npm-install-if-needed"
type = "shell"
command = "if [ -f package.json ]; then npm install; fi"
working_directory = "repository:///"
```

### Ignore Failures

```toml
[[actions]]
name = "optional-linting"
type = "shell"
command = "ruff check src/"
working_directory = "repository:///"
ignore_failure = true  # Don't fail workflow if linting fails
```

## Common Use Cases

### Running Tests

```toml
[[actions]]
name = "run-python-tests"
type = "shell"
command = "pytest tests/ -v --tb=short"
working_directory = "{{ working_directory }}/repository"

[[actions]]
name = "run-javascript-tests"
type = "shell"
command = "npm test"
working_directory = "repository:///"
```

### Building Artifacts

```toml
[[actions]]
name = "build-python-package"
type = "shell"
command = "python -m build"
working_directory = "{{ working_directory }}/repository"

[[actions]]
name = "build-docker-image"
type = "shell"
command = "docker build -t {{ imbi_project.slug }}:latest ."
working_directory = "repository:///"
```

### Code Quality Tools

```toml
[[actions]]
name = "run-linter"
type = "shell"
command = "ruff check --fix src/"
working_directory = "repository:///"

[[actions]]
name = "format-code"
type = "shell"
command = "ruff format src/ tests/"
working_directory = "repository:///"

[[actions]]
name = "type-check"
type = "shell"
command = "mypy src/"
working_directory = "repository:///"
```

### Git Operations

```toml
[[actions]]
name = "get-current-version"
type = "shell"
command = "git describe --tags --abbrev=0"
working_directory = "repository:///"

[[actions]]
name = "list-changed-files"
type = "shell"
command = "git diff --name-only {{ starting_commit }} HEAD"
working_directory = "{{ working_directory }}/repository"
```

### Environment Setup

```toml
[[actions]]
name = "setup-python-env"
type = "shell"
command = """
python -m venv .venv && \
.venv/bin/pip install --upgrade pip setuptools wheel
"""
working_directory = "repository:///"

[[actions]]
name = "setup-node-env"
type = "shell"
command = "npm ci"
working_directory = "repository:///"
```

## Advanced Template Examples

### Using Imbi Project Data

```toml
[[actions]]
name = "project-specific-command"
type = "shell"
command = """
echo "Processing {{ imbi_project.name }}"
echo "Type: {{ imbi_project.project_type }}"
echo "Namespace: {{ imbi_project.namespace }}"
"""
```

### Conditional Logic with Jinja2

```toml
[[actions]]
name = "environment-specific-deploy"
type = "shell"
command = """
{% if imbi_project.project_type == 'api' %}
  python deploy_api.py
{% elif imbi_project.project_type == 'consumer' %}
  python deploy_consumer.py
{% else %}
  echo "Unknown project type"
{% endif %}
"""
working_directory = "repository:///"
```

### Using Project Facts

```toml
[[actions]]
name = "language-specific-test"
type = "shell"
command = """
{% if imbi_project.facts.get('Programming Language') == 'Python 3.12' %}
  pytest tests/ --python=3.12
{% elif imbi_project.facts.get('Programming Language') == 'Python 3.11' %}
  pytest tests/ --python=3.11
{% endif %}
"""
working_directory = "repository:///"
```

### Iterating Over Lists

```toml
[[actions]]
name = "install-dependencies"
type = "shell"
command = """
{% for dep in dependencies %}
pip install {{ dep }}
{% endfor %}
"""
working_directory = "repository:///"
```

## Path Resolution

Working directory supports all ResourceUrl schemes:

```toml
# Repository directory
[[actions]]
type = "shell"
command = "ls -la"
working_directory = "repository:///"

# Workflow directory
[[actions]]
type = "shell"
command = "cat templates/README.md"
working_directory = "workflow:///"

# Extracted files directory
[[actions]]
type = "shell"
command = "find . -name '*.conf'"
working_directory = "extracted:///"

# Explicit working directory path
[[actions]]
type = "shell"
command = "pwd"
working_directory = "{{ working_directory }}/repository"
```

## Command Output

### Captured Output
- **stdout**: Logged at DEBUG level
- **stderr**: Logged at DEBUG level
- **Exit Code**: Non-zero exit codes cause workflow failure (unless `ignore_failure = true`)

### Output in Logs

```python
# Logger output example:
DEBUG: Executing shell command: pytest tests/ -v
DEBUG: Command stdout: ===== test session starts =====
DEBUG: Command stderr:
DEBUG: Command exit code: 0
```

## Error Handling

### Exit Code Handling

```toml
# Fail workflow on error (default)
[[actions]]
name = "critical-command"
type = "shell"
command = "important-operation"
# Fails workflow if exit code != 0

# Continue on error
[[actions]]
name = "optional-command"
type = "shell"
command = "optional-operation"
ignore_failure = true  # Continues even if exit code != 0
```

### Command Not Found

```toml
[[actions]]
name = "missing-command"
type = "shell"
command = "nonexistent-command"
# Raises RuntimeError: Command 'nonexistent-command' not found
```

## Security Considerations

### Command Injection Prevention

Template variables are NOT shell-escaped automatically. Be cautious with user-provided data:

```toml
# UNSAFE - if imbi_project.name contains shell metacharacters
[[actions]]
type = "shell"
command = "echo {{ imbi_project.name }}"

# SAFER - use quotes
[[actions]]
type = "shell"
command = "echo '{{ imbi_project.name }}'"

# SAFEST - avoid untrusted input in shell commands
```

### Environment Variables

Commands execute with the same environment as the workflow process:

```toml
[[actions]]
name = "use-env-var"
type = "shell"
command = "echo $HOME && echo $USER"
```

## Performance Tips

### Chaining Commands

Use `&&` for dependent commands (fail fast):
```toml
[[actions]]
type = "shell"
command = "cd repository && make build && make test"
```

Use `;` for independent commands (always run all):
```toml
[[actions]]
type = "shell"
command = "make clean; make build; make test"
```

### Background Processes

Not recommended - commands block until completion. For long-running operations, consider using Docker actions instead.

## Implementation Notes

- Commands execute in a subprocess using asyncio
- Full shell features available (pipes, redirects, environment variables)
- Working directory resolved before command execution
- Template rendering occurs before command execution
- Timeout: Configurable (default varies by implementation)
- Shell: Uses system default shell (`/bin/sh` on Unix, `cmd.exe` on Windows)
