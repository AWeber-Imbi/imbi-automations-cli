# Git Actions

Git actions provide version control operations for extracting Git history and managing branches.

## Configuration

```toml
[[actions]]
name = "action-name"
type = "git"
command = "extract"
# Command-specific fields below
```

## Commands

### extract

Extract Git commit history from a specific commit range.

**Required Fields:**
- `starting_commit`: Starting commit SHA or ref
- `match_strategy`: How to find commits (`first_parent`, `all`)

**Optional Fields:**
- `destination`: Where to store commit data (ResourceUrl)

**Example:**
```toml
[[actions]]
name = "extract-recent-commits"
type = "git"
command = "extract"
starting_commit = "{{ starting_commit }}"
match_strategy = "first_parent"
destination = "extracted:///commits/"
```

**Match Strategies:**
- `first_parent`: Follow only first parent commits (linear history)
- `all`: Include all commits in the range (including merges)

## Common Use Cases

### Extract Commit Range

```toml
[[actions]]
name = "get-changes"
type = "git"
command = "extract"
starting_commit = "{{ starting_commit }}"
match_strategy = "first_parent"
destination = "commits.json"
```

### Analyze Commit History

```toml
[[actions]]
name = "extract-commits"
type = "git"
command = "extract"
starting_commit = "HEAD~10"
match_strategy = "all"

[[actions]]
name = "analyze-commits"
type = "shell"
command = "python scripts/analyze-commits.py"
working_directory = "{{ working_directory }}"
```

## Commit Data Structure

Extracted commit data includes:
- Commit SHA
- Author name and email
- Commit message
- Timestamp
- Changed files list
- Parent commits

## Implementation Notes

- Uses `git log` for commit extraction
- Commit data stored as JSON
- Respects `.gitignore` for file operations
- Works with current repository state
- Starting commit must exist in history
