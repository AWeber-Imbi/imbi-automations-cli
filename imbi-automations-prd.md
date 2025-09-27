# Imbi Automations PRD

## Executive Summary

**Product**: `imbi-automations` - An open-source CLI framework for executing dynamic workflows across software project repositories, with deep integration to the Imbi project management system.

**Vision**: Provide teams with a powerful, extensible automation framework that can synchronize project metadata, apply code transformations at scale, and maintain consistency across large software portfolios.

## Background & Motivation

Based on successful production deployment of `g2g-migration` which handled complex GitLab→GitHub migrations with AI-powered transformations, Imbi Automations generalizes the proven architecture for broader automation use cases while maintaining the reliability and rollback capabilities that made g2g-migration successful.

## Core Architecture

### Unified Transformation Framework
- **Priority-based execution** with adaptive re-evaluation after each successful transformation
- **Four transformation types**: Template Manager, AI Editor, Claude Code, Shell
- **File Actions** for rename/remove operations with rollback support
- **Conditional execution** with dynamic re-evaluation

### Analysis Framework
- **Project discovery** based on project type, namespace, or custom filters
- **Fact rules** for automatic updates based on workflow results
- **Link rules** for dynamic link creation with template support

### Transaction-Style Operations
- Detailed rollback tracking for all operations
- Atomic workflow execution with cleanup on failure
- Checkpoint system for resumable batch operations

### Extensible Plugin Architecture
```
workflows/
├── sync-github-metadata/
│   ├── workflow.toml              # Workflow definition
│   ├── transformations/           # Transformation steps
│   │   ├── ai-editor/priority-75-update-readme/
│   │   ├── templates/priority-50-add-codeowners/
│   │   └── shell/priority-25-run-tests/
│   └── conditions/                # Workflow applicability
└── python-modernization/
    ├── workflow.toml
    └── transformations/
```

## Feature Requirements

### Core Workflow Engine
- **Workflow Discovery**: Automatic detection of applicable workflows based on project filters
- **Conditional Execution**: File-based, project-type, and dynamic conditions
- **Priority Orchestration**: Deterministic execution order with dependency handling
- **Rollback Management**: Full transaction rollback on any failure

### Imbi Integration
- **Project Discovery**: Query projects by type, namespace, or custom filters
- **Metadata Sync**: Bidirectional sync of facts, links, and project data
- **Fact Rules**: Automatic fact updates based on workflow results
- **Link Rules**: Dynamic link creation with template support

### Repository Operations
- **Multi-SCM Support**: GitHub, GitLab, with extensible provider system
- **Branch Strategies**: Direct push or PR-based workflows
- **Git Operations**: Full history preservation, LFS support
- **Large File Handling**: Automatic LFS conversion for files ≥100MB

### Transformation System
1. **Template Manager**: Jinja2-based file placement with project context
2. **AI Editor**: Fast, focused file edits using Claude 3.5 Haiku
3. **Claude Code**: Complex multi-file analysis and transformation
4. **Shell**: Arbitrary command execution with context variables
5. **File Actions**: Rename, remove, regex operations with rollback

## Technical Specifications

### Configuration Structure
```toml
[imbi]
hostname = "imbi.example.com"
api_key = "uuid-here"

[providers.github]
hostname = "api.github.com"
api_key = "ghp_token"

[providers.gitlab]
hostname = "gitlab.com"
api_key = "glpat_token"

[execution]
max_concurrent = 5
checkpoint_file = ".imbi-automations-checkpoint"
rollback_on_failure = true
```

### CLI Interface
```bash
# Workflow execution
imbi-automations run --workflow workflows/sync-github-metadata --project-id 123
imbi-automations run --workflow workflows/python-modernization --project-type api
imbi-automations run --workflow workflows/validate-standards --namespace platform

# Utility commands
imbi-automations validate-workflow --workflow-dir ./workflows/custom-workflow
```

### Workflow Definition Format
```toml
[workflow]
name = "Python Modernization"
description = "Upgrade Python projects to latest standards"
version = "1.0.0"

[filters]
project_types = ["api", "backend-libraries", "consumers"]
programming_languages = ["Python"]
exclude_archived = true

[execution]
branch_strategy = "pull_request"  # or "direct_push"
pr_title = "Automated Python modernization"
pr_body = "Automated updates via imbi-automations"

[rollback]
track_file_changes = true
track_imbi_updates = true
track_repository_operations = true
```

## Use Case Coverage

### Project Synchronization
- **GitHub→Imbi sync**: Extract repository metadata, topics, languages
- **Imbi→GitHub sync**: Apply project facts as repository topics/settings
- **Discovery auditing**: Find projects in one system but not the other

### Code Modernization
- **Python upgrades**: Automated version bumps, dependency updates
- **Standards compliance**: Apply consistent linting, CI/CD, security configs
- **Template propagation**: Roll out standard files across project portfolios

### Repository Management
- **Dead code identification**: Analyze commit history, dependency usage
- **Migration automation**: Move repositories between SCM providers
- **Compliance validation**: Ensure projects meet organizational standards

## Success Metrics

### Reliability
- **Zero data loss**: All operations must be fully recoverable
- **Complete rollback**: All failed operations fully reversed

### Usability
- **Workflow authoring**: Non-developers can create basic workflows
- **Clear logging**: Every operation traceable with detailed output
- **Resume capability**: Large batch operations survive interruption

## Risk Mitigation

### Operational Risks
- **API rate limits**: Implement exponential backoff, respect provider limits
- **Large repository handling**: Stream processing for repositories >1GB
- **Concurrent operation limits**: Configurable concurrency with sane defaults

### Data Integrity Risks
- **Rollback verification**: Test rollback paths in CI/CD
- **Backup integration**: Hook into existing backup systems where available
- **Audit logging**: Complete operation history for troubleshooting

### Security Considerations
- **Token management**: Secure credential handling, rotation support
- **Code execution**: Sandbox shell operations where possible
- **Access control**: Respect existing repository and project permissions

## Architecture Decisions

### Transformation System Design
The unified transformation system proven in g2g-migration will be preserved and extended:

- **Priority-based execution**: Higher priority transformations run first
- **Adaptive re-evaluation**: Conditions checked after each successful transformation
- **Type-specific handling**: Each transformation type optimized for its use case
- **Rollback tracking**: Every operation tracked for potential reversal

### Configuration Management
- **TOML-based configuration**: Human-readable, version-controllable
- **Environment variable overrides**: Secure credential handling
- **Hierarchical loading**: Global → workspace → workflow specific configs

### Error Handling Strategy
- **Fail-fast philosophy**: Stop execution on first failure
- **Complete rollback**: Reverse all operations on failure
- **Detailed logging**: Every operation logged with context
- **Retry mechanisms**: Configurable retry for transient failures

### Plugin Architecture
- **Provider abstraction**: Common interface for GitHub, GitLab, etc.
- **Workflow composition**: Mix and match transformation types
- **Custom transformation types**: Extensible beyond the core four types
