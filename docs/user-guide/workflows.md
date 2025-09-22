# Workflows

Workflows are the core of Imbi Automations, defining a series of actions to be executed across repositories or projects.

## Workflow Structure

Workflows are organized in directories with the following structure:

```
workflows/
├── sync-github-metadata/
│   ├── workflow.toml              # Workflow definition
│   ├── transformations/           # Transformation steps
│   │   ├── ai-editor/priority-75-update-readme/
│   │   ├── templates/priority-50-add-codeowners/
│   │   └── shell/priority-25-run-tests/
│   └── conditions/                # Workflow applicability
```

## Workflow Configuration

### Basic Configuration

```toml
name = "sync-github-metadata"
description = "Synchronize repository metadata with GitHub"
clone_repository = true
ci_skip_checks = false
```

#### Configuration Fields

- **name**: Unique identifier for the workflow
- **description**: Human-readable description
- **clone_repository**: Whether to clone repositories for file operations
- **ci_skip_checks**: Add `[ci skip]` to commit messages

### Actions

Actions define the operations to be performed:

```toml
[[actions]]
name = "check-status"
type = "callable"

[actions.value]
client = "github"
method = "get_sonarqube_job_status"
kwargs.org = "{{ github_repository.owner.login }}"
kwargs.repo_name = "{{ github_repository.name }}"
kwargs.branch = "main"

[[actions]]
name = "update-file"
type = "callable"
condition = "actions['check-status']['result'] == 'failure'"

[actions.value]
client = "utils"
method = "append_file"
kwargs.file = "/tmp/failing-projects.txt"
kwargs.value = "{{ github_repository.html_url + '\n' }}"
```

#### Action Types

1. **callable**: Execute client method calls
2. **templates**: Copy and render Jinja2 templates
3. **file**: Perform file operations (rename, remove, regex)

## Conditional Execution

Actions can be conditionally executed based on previous results:

```toml
[[actions]]
name = "conditional-action"
type = "callable"
condition = "actions['previous-action']['result'] == 'failure'"
```

### Condition Examples

```toml
# Execute only if previous action succeeded
condition = "actions['check-status']['result'] == 'success'"

# Execute only if previous action failed
condition = "actions['sonar-check']['result'] == 'failure'"

# Execute only if result contains specific text
condition = "'error' in str(actions['analyze']['result'])"

# Complex boolean conditions
condition = "actions['test']['result'] == 'success' and actions['lint']['result'] == 'success'"
```

## Template Context

Actions have access to template context variables:

### Available Variables

- **github_repository**: GitHub repository data
- **gitlab_project**: GitLab project data
- **imbi_project**: Imbi project metadata
- **workflow**: Current workflow configuration
- **workflow_run**: Runtime data
- **actions**: Results from previous actions

### Template Examples

```toml
# Repository information
value = "{{ github_repository.name }}"
value = "{{ github_repository.owner.login }}"
value = "{{ github_repository.html_url }}"

# Project metadata
value = "{{ imbi_project.name }}"
value = "{{ imbi_project.namespace_slug }}"

# Action results
value = "{{ actions['previous-action']['result'] }}"

# Complex templates
value = "{{ imbi_project.name + ',' + github_repository.html_url + '\n' }}"
```

## Workflow Conditions

Define when workflows should run:

```toml
condition_type = "all"  # or "any"

[[conditions]]
file_exists = "package.json"

[[conditions]]
file_not_exists = ".python-version"
```

### Condition Types

- **all**: All conditions must be true
- **any**: At least one condition must be true

### Supported Conditions

- **file_exists**: File or directory exists
- **file_not_exists**: File or directory does not exist

## Workflow Filters

Filter which projects workflows apply to:

```toml
[filter]
project_ids = [123, 456, 789]
project_types = ["python-service", "react-app"]
```

## Best Practices

1. **Descriptive Names**: Use clear, descriptive workflow names
2. **Modular Actions**: Keep actions focused on single responsibilities
3. **Error Handling**: Use conditions to handle different scenarios
4. **Documentation**: Include clear descriptions for complex workflows
5. **Testing**: Test workflows on small sets before broad deployment
6. **Idempotency**: Design workflows to be safely re-runnable
