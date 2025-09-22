# Callable Functions Reference

This page documents all callable functions available in workflow actions. These functions can be used in `callable` type actions to retrieve data or perform operations.

## Usage Format

Callable functions are used in workflow actions with the following structure:

```toml
[[actions]]
name = "action-name"
type = "callable"

[actions.value]
client = "client_name"
method = "method_name"

[actions.value.kwargs]
parameter1 = "value1"
parameter2 = "{{ template_expression }}"
```

## Available Clients

- **github**: GitHub API operations
- **imbi**: Imbi project management operations
- **utils**: File operations and utilities

---

## GitHub Client (`client = "github"`)

### Repository Operations

#### `get_repository`
Get repository information by organization and name.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name

**Returns:** `GitHubRepository` object or `None`

**Example:**
```toml
[actions.value]
client = "github"
method = "get_repository"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo_name = "{{ github_repository.name }}"
```

#### `get_repository_by_id`
Get repository information by GitHub repository ID.

**Parameters:**
- `repo_id`: GitHub repository ID (integer)

**Returns:** `GitHubRepository` object or `None`

**Example:**
```toml
[actions.value]
client = "github"
method = "get_repository_by_id"

[actions.value.kwargs]
repo_id = 12345
```

#### `get_repository_identifier`
Get repository ID for use in other operations.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name
- `branch`: Branch name (optional, ignored for compatibility)

**Returns:** Repository ID (integer) or `None`

**Example:**
```toml
[actions.value]
client = "github"
method = "get_repository_identifier"

[actions.value.kwargs]
org = "apis"
repo_name = "content-rendering"
```

### Workflow and CI Operations

#### `get_latest_workflow_status`
Get the status/conclusion of the most recent workflow run.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name
- `branch`: Branch name (optional, defaults to all branches)

**Returns:** Status string (`'success'`, `'failure'`, `'in_progress'`, etc.) or `None`

**Example:**
```toml
[actions.value]
client = "github"
method = "get_latest_workflow_status"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo_name = "{{ github_repository.name }}"
branch = "main"
```

#### `get_sonarqube_job_status`
Get the status of jobs with specific keyword from the most recent workflow run.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name
- `branch`: Branch name (optional, defaults to all branches)
- `keyword`: Keyword to search for in job names (default: 'sonar')

**Returns:** Job status (`'failure'`, `'success'`, `'skipped'`, `'in_progress'`) or `None`

**Example:**
```toml
[actions.value]
client = "github"
method = "get_sonarqube_job_status"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo_name = "{{ github_repository.name }}"
branch = "main"
keyword = "sonar"
```

### Custom Properties

#### `get_repository_custom_properties`
Get all custom property values for a repository.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name

**Returns:** Dictionary mapping property names to values

**Example:**
```toml
[actions.value]
client = "github"
method = "get_repository_custom_properties"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo_name = "{{ github_repository.name }}"
```

#### `update_repository_custom_properties`
Create or update custom property values for a repository.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name
- `properties`: Dictionary of property names to values

**Returns:** None (operation status)

**Example:**
```toml
[actions.value]
client = "github"
method = "update_repository_custom_properties"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo_name = "{{ github_repository.name }}"
properties = {"imbi_project_id": "{{ imbi_project.id }}"}
```

### Team Management

#### `get_repository_team_permissions`
Get team permissions for a repository.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name

**Returns:** Dictionary mapping team slug to permission level

**Example:**
```toml
[actions.value]
client = "github"
method = "get_repository_team_permissions"

[actions.value.kwargs]
org = "apis"
repo_name = "content-rendering"
```

#### `sync_repository_team_access`
Synchronize team access permissions for a repository.

**Parameters:**
- `org`: Organization name
- `repo_name`: Repository name
- `current_teams`: Current team permissions (team_slug → permission)
- `desired_mappings`: Desired team permissions (team_slug → permission)

**Returns:** Status string (`'success'`, `'partial'`, `'failed'`)

**Example:**
```toml
[actions.value]
client = "github"
method = "sync_repository_team_access"

[actions.value.kwargs]
org = "{{ github_repository.owner.login }}"
repo_name = "{{ github_repository.name }}"
current_teams = "{{ actions['get-teams']['result'] }}"
desired_mappings = {"api-team": "push", "security-team": "admin"}
```

---

## Imbi Client (`client = "imbi"`)

### Project Operations

#### `get_project`
Get detailed project information by ID.

**Parameters:**
- `project_id`: Imbi project ID (integer)

**Returns:** `ImbiProject` object or `None`

**Example:**
```toml
[actions.value]
client = "imbi"
method = "get_project"

[actions.value.kwargs]
project_id = "{{ imbi_project.id }}"
```

#### `get_projects_by_type`
Get all projects of a specific project type.

**Parameters:**
- `project_type_slug`: Project type slug (e.g., 'python-service')

**Returns:** List of `ImbiProject` objects

**Example:**
```toml
[actions.value]
client = "imbi"
method = "get_projects_by_type"

[actions.value.kwargs]
project_type_slug = "python-service"
```

#### `get_all_projects`
Get all active projects in Imbi.

**Parameters:** None

**Returns:** List of `ImbiProject` objects

**Example:**
```toml
[actions.value]
client = "imbi"
method = "get_all_projects"
```

### Project Facts

#### `get_project_facts`
Get all facts for a project.

**Parameters:**
- `project_id`: Imbi project ID (integer)

**Returns:** List of `ImbiProjectFact` objects

**Example:**
```toml
[actions.value]
client = "imbi"
method = "get_project_facts"

[actions.value.kwargs]
project_id = "{{ imbi_project.id }}"
```

#### `get_project_fact_value`
Get current value of a specific project fact.

**Parameters:**
- `project_id`: Imbi project ID (integer)
- `fact_name`: Name of the fact to retrieve

**Returns:** Current fact value (string) or `None`

**Example:**
```toml
[actions.value]
client = "imbi"
method = "get_project_fact_value"

[actions.value.kwargs]
project_id = "{{ imbi_project.id }}"
fact_name = "CI Pipeline Status"
```

#### `update_project_fact`
Update a single project fact by name or ID.

**Parameters:**
- `project_id`: Imbi project ID (integer)
- `fact_name`: Name of the fact to update (alternative to fact_type_id)
- `fact_type_id`: ID of the fact type (alternative to fact_name)
- `value`: New value for the fact
- `skip_validations`: Skip project type and current value validations (default: false)

**Returns:** None (operation status)

**Enhanced Validations (enabled by default):**
- Skips update if current value is the same
- Skips update if fact type doesn't support the project's type

**Example:**
```toml
[actions.target]
client = "imbi"
method = "update_project_fact"

[actions.target.kwargs]
project_id = "{{ imbi_project.id }}"
fact_name = "CI Pipeline Status"
value = "{{ actions['check-status']['result'] }}"
```

### GitHub Integration

#### `update_github_identifier`
Update GitHub identifier for a project.

**Parameters:**
- `project_id`: Imbi project ID (integer)
- `identifier_name`: Name of the identifier (e.g., 'github')
- `value`: New identifier value

**Returns:** None (operation status)

**Example:**
```toml
[actions.value]
client = "imbi"
method = "update_github_identifier"

[actions.value.kwargs]
project_id = "{{ imbi_project.id }}"
identifier_name = "github"
value = "{{ github_repository.id }}"
```

### Search Operations

#### `search_projects_by_github_url`
Find projects by GitHub repository URL.

**Parameters:**
- `github_url`: GitHub repository URL

**Returns:** List of matching `ImbiProject` objects

**Example:**
```toml
[actions.value]
client = "imbi"
method = "search_projects_by_github_url"

[actions.value.kwargs]
github_url = "{{ github_repository.html_url }}"
```

---

## Utils Client (`client = "utils"`)

### File Operations

#### `append_file`
Append content to a file (creates file and directories if needed).

**Parameters:**
- `file`: Path to the file to append to
- `value`: Content to append to the file

**Returns:** Status string (`'success'` or `'failed'`)

**Example:**
```toml
[actions.value]
client = "utils"
method = "append_file"

[actions.value.kwargs]
file = "/tmp/failing-projects.csv"
value = "{{ imbi_project.name + ',' + github_repository.html_url + '\n' }}"
```

---

## Template Context Variables

All callable functions have access to template context variables:

### Repository Context
- `github_repository.owner.login` - GitHub organization name
- `github_repository.name` - Repository name
- `github_repository.html_url` - Repository web URL
- `github_repository.id` - Repository ID
- `github_repository.full_name` - Full name (org/repo)

### Project Context
- `imbi_project.id` - Imbi project ID
- `imbi_project.name` - Project name
- `imbi_project.slug` - Project URL slug
- `imbi_project.namespace_slug` - Namespace slug
- `imbi_project.project_type_slug` - Project type slug

### Action Results
- `actions['action-name']['result']` - Result from previous action

---

## Value Mapping

Transform returned values using value mapping:

```toml
[actions.value_mapping]
"success" = "Pass"
"failure" = "Fail"
"cancelled" = "Cancelled"
"in_progress" = "In Progress"
"null" = "Not Found"
```

---

## Conditional Execution

Execute actions only when conditions are met:

```toml
[[actions]]
name = "conditional-action"
type = "callable"
condition = "actions['check-status']['result'] == 'failure'"

[actions.value]
client = "utils"
method = "append_file"
kwargs.file = "/tmp/failures.txt"
kwargs.value = "{{ github_repository.html_url + '\n' }}"
```

---

## Complete Workflow Example

```toml
name = "repository-health-check"
description = "Check repository health and update project facts"
clone_repository = false

# Get CI status
[[actions]]
name = "check-ci-status"
type = "callable"

[actions.value]
client = "github"
method = "get_latest_workflow_status"
kwargs.org = "{{ github_repository.owner.login }}"
kwargs.repo_name = "{{ github_repository.name }}"
kwargs.branch = "main"

# Update Imbi fact with CI status
[[actions]]
name = "update-ci-fact"
type = "callable"

[actions.target]
client = "imbi"
method = "update_project_fact"
kwargs.project_id = "{{ imbi_project.id }}"
kwargs.fact_name = "CI Pipeline Status"
kwargs.value = "{{ actions['check-ci-status']['result'] }}"

[actions.value_mapping]
"success" = "Pass"
"failure" = "Fail"

# Log failures to file
[[actions]]
name = "log-failures"
type = "callable"
condition = "actions['check-ci-status']['result'] == 'failure'"

[actions.value]
client = "utils"
method = "append_file"
kwargs.file = "/tmp/failing-repos.txt"
kwargs.value = "{{ github_repository.html_url + '\n' }}"
```

## Best Practices

1. **Use Template Variables**: Leverage context variables for dynamic values
2. **Handle Null Values**: Use value mapping to handle null/empty responses
3. **Conditional Logic**: Use conditions to control when actions execute
4. **Error Handling**: Check return values and use appropriate conditions
5. **Validation**: Imbi fact updates include automatic validation by default
6. **Performance**: Enhanced validations prevent unnecessary API calls
