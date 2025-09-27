# Imbi Automations CLI Refactoring Plan

## Executive Summary

The Imbi Automations CLI has evolved organically into a powerful tool, but the piece-by-piece development approach has resulted in architectural inconsistencies, scattered responsibilities, and missed opportunities for abstraction. This refactoring plan addresses code quality, maintainability, and architectural coherence while preserving the system's proven functionality.

## Project Context

### Current Architecture Overview
- **Entry Point**: `cli.py` - CLI argument parsing and engine initialization
- **Core Engine**: `engine.py` (~1000 LOC) - Contains both `AutomationEngine` and `WorkflowEngine`
- **Client Libraries**: `github.py`, `imbi.py`, `gitlab.py` - HTTP API clients
- **Action Handlers**: `claude_code.py`, `ai_editor.py` - AI transformation handlers
- **Models**: `models.py` - 25+ Pydantic models for configuration and data
- **Utilities**: `git.py`, `docker.py`, `utils.py`, `environment_sync.py`

### Current File Structure
```
src/imbi_automations/
├── cli.py              # CLI interface and argument parsing
├── engine.py           # AutomationEngine + WorkflowEngine (1000+ LOC)
├── models.py           # All Pydantic models (25+ classes)
├── claude_code.py      # Claude Code subprocess integration
├── ai_editor.py        # AI Editor implementation
├── github.py           # GitHub API client
├── imbi.py            # Imbi API client
├── gitlab.py          # GitLab API client
├── git.py             # Git operations
├── docker.py          # Docker operations
├── utils.py           # Configuration and utilities
└── environment_sync.py # GitHub environment synchronization
```

### Workflow Configuration Locations
- **Main workflows**: `workflows/*/config.toml` (22 existing workflows)
- **Action types supported**: `claude`, `ai-editor`, `shell`, `templates`, `file`, `callable`, direct client calls
- **Template files**: `.md`, `.md.j2` prompt files alongside configs

## Critical Issues Identified

### 1. Architectural Inconsistencies

**Problem**: Multiple "Engine" classes with overlapping responsibilities
- `AutomationEngine`: High-level orchestration and project iteration
- `WorkflowEngine`: Workflow execution and transformation management
- Mixed concerns between iteration logic and workflow execution

**Impact**: Confusing responsibility boundaries, difficult testing, code duplication

### 2. Action Implementation Inconsistencies

**Problem**: While multiple action types are intentionally designed, their implementations lack consistency
- **Direct method calls**: Well-structured with `client.method_name(**kwargs)`
- **Typed actions**: Some have hardcoded logic, others are well-abstracted
- **Shell execution**: Minimal abstraction and inconsistent error handling

**Impact**: Implementation quality varies by action type, making some harder to maintain than others

### 3. Subprocess Over SDK Usage

**Problem**: Claude Code integration uses subprocess instead of proper SDK
- Current: `subprocess.exec(..., stdin=prompt)` in `claude_code.py:201`
- Available: `ClaudeSDKClient` and `query()` methods with proper error handling

**Impact**: Poor error handling, no streaming, loss of conversation context

### 4. Configuration Model Explosion

**Problem**: Over 25 Pydantic models with unclear relationships
- Mixed domain concepts (GitHub, Imbi, workflows, conditions)
- Nested models without clear inheritance hierarchy
- Configuration spread across multiple TOML files

**Impact**: Difficult validation, unclear data flow, maintenance overhead

### 5. Poor Module Separation

**Problem**: Circular dependencies and mixed concerns
- `engine.py`: 1000+ lines mixing iteration, orchestration, and execution
- All modules depend on `models.py` creating tight coupling
- HTTP clients mixed with business logic

**Impact**: Testing difficulties, hard to modify, unclear interfaces

## Refactoring Strategy

### Phase 1: Core Architecture Separation (High Priority)

#### 1.1 Extract Iteration Logic
**Current**: Mixed in `AutomationEngine`
**Target**: New `Iterator` module with distinct strategies

```python
# New structure
from imbi_automations.iterators import (
    ImbiProjectIterator,
    GitHubRepositoryIterator,
    GitLabRepositoryIterator
)
```

**Benefits**: Clear separation of concerns, testable iteration logic

#### 1.2 Standardize Action Implementation Quality
**Current**: Varying implementation quality across action types
**Target**: Consistent patterns within each action type (preserving type variety)

**Improvements**:
- **Shell actions**: Better error handling and logging consistency
- **Typed actions**: Remove hardcoded logic, improve abstraction
- **Callable actions**: Maintain current good patterns as reference
- **Common interfaces**: Shared error handling and result patterns without forcing unified execution

#### 1.3 Redesign Engine Hierarchy
**Current**: Two overlapping engines
**Target**: Single `WorkflowEngine` with injected strategies

```python
class WorkflowEngine:
    def __init__(
        self,
        iterator: ProjectIterator,
        executor_factory: ActionExecutorFactory,
        clients: ClientRegistry
    ) -> None:
```

### Phase 2: Claude Code SDK Integration (High Priority)

#### 2.1 Replace Subprocess with SDK
**Current**: `claude_code.py:201` uses `subprocess.create_subprocess_exec`
```python
# Current problematic code in claude_code.py
process = await asyncio.create_subprocess_exec(
    *command,
    cwd=self.working_directory,
    env=env,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

**Target**: Use `ClaudeSDKClient` and `query()` methods
```python
# New implementation
from claude_code_sdk import ClaudeSDKClient, ClaudeCodeOptions

class ClaudeCodeExecutor:
    async def execute_prompt(self, prompt_content: str, timeout_seconds: int = 600):
        options = ClaudeCodeOptions(
            allowed_tools=["Read", "Write", "Bash", "Edit"],
            permission_mode='acceptEdits'
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt_content)
            async for message in client.receive_response():
                # Process streaming messages
                yield message
```

**Implementation Steps**:
1. Add `claude_code_sdk` to dependencies in `pyproject.toml`
2. Replace subprocess implementation directly in `ClaudeCode.execute_prompt()` method
3. Maintain identical public interface and return values
4. Test extensively to ensure identical behavior for existing workflows

**Files to Modify**:
- `src/imbi_automations/claude_code.py` - Replace subprocess logic completely
- `pyproject.toml` - Add `claude_code_sdk` dependency
- Tests - Update to verify identical behavior with new SDK implementation

#### 2.2 Add AI Editor SDK Integration
**Current**: `ai_editor.py` likely uses similar subprocess pattern
**Target**: Lightweight Claude integration for focused file edits
**Files to Check**: `src/imbi_automations/ai_editor.py`

### Phase 3: Configuration System Refactoring (Medium Priority)

#### 3.1 Simplify Model Hierarchy
**Current**: 25+ models with unclear relationships
**Target**: Domain-grouped models with clear inheritance

```python
# Domain separation
from imbi_automations.models.clients import GitHubConfig, ImbiConfig
from imbi_automations.models.workflows import WorkflowDefinition
from imbi_automations.models.execution import ExecutionContext
```

#### 3.2 Configuration Validation Pipeline
**Current**: Scattered validation in CLI and models
**Target**: Centralized validation with clear error messages

```python
class ConfigurationValidator:
    def validate_workflow(self, workflow: WorkflowDefinition) -> ValidationResult
    def validate_clients(self, config: Configuration) -> ValidationResult
```

### Phase 4: Module Restructuring (Medium Priority)

#### 4.1 Break Up Large Modules
**Current**: `engine.py` (1000+ lines), `models.py` (complex hierarchy)
**Target**: Focused modules by domain

```
src/imbi_automations/
├── core/               # Core abstractions
│   ├── interfaces.py   # Protocols and abstract bases
│   ├── context.py      # Execution context management
│   └── results.py      # Result types and handling
├── iterators/          # Project iteration strategies
├── executors/          # Action execution implementations
├── clients/            # HTTP clients (GitHub, Imbi, GitLab)
├── models/             # Domain models by concern
│   ├── clients.py
│   ├── workflows.py
│   └── execution.py
└── workflows/          # Workflow management
```

#### 4.2 Create Clear Client Registry
**Current**: Direct client instantiation in engine
**Target**: Dependency injection with client registry

```python
class ClientRegistry:
    def get_github_client(self) -> GitHubClient | None
    def get_imbi_client(self) -> ImbiClient | None
    def get_gitlab_client(self) -> GitLabClient | None
```

### Phase 5: Testing and Documentation (Low Priority)

#### 5.1 Test Architecture Alignment
**Current**: Tests follow old architecture patterns
**Target**: Tests match new module structure

#### 5.2 API Documentation
**Current**: Scattered docstrings
**Target**: Comprehensive API documentation with examples

## Implementation Priority

### High Priority (Immediate Impact)
1. **Claude Code SDK Integration** - Fixes immediate subprocess issues
2. **Action Executor Unification** - Resolves inconsistent execution patterns
3. **Engine Responsibility Separation** - Clarifies core architecture

### Medium Priority (Architectural Health)
4. **Configuration Model Simplification** - Improves maintainability
5. **Module Restructuring** - Enables future development

### Low Priority (Polish)
6. **Testing Infrastructure** - Supports ongoing development
7. **Documentation** - Improves developer experience

## Migration Strategy & Backward Compatibility

### Core Compatibility Guarantee
**All 22 existing workflow configurations must continue to work without modification during and after refactoring.**

### Existing Workflow Inventory
The refactoring must preserve functionality for these workflow patterns:

**Action Types in Use:**
- `type = "ai-editor"` - 2 workflows (ai-editor-example, compose-volume-fix)
- `type = "claude"` - 4 workflows (compose-fix, docker-healthchecker, fix-workflow)
- `type = "shell"` - 3 workflows (bootstrap-fix, pre-commit-fix)
- `type = "templates"` - 2 workflows (backend-gitignore, frontend-gitignore)
- `type = "file"` - 1 workflow (remove-extra-ci-files)
- `type = "callable"` - 1 workflow (failing-sonarqube)
- Direct client calls - 9 workflows (sync-project-environments, ensure-github-teams, etc.)

**Configuration Features:**
- Remote and local conditions
- Project filtering
- Jinja2 templating
- Conditional logic (`condition_logic = "any"`)
- Multiple action sequences

### Migration Phases

#### Phase 1: Internal Refactoring (Zero Breaking Changes)
**Duration**: 2-3 weeks
**Approach**: Behind-the-scenes improvements only

1. **Configuration Parsing**: Keep existing TOML format 100% compatible
   - Preserve all current keys and structures
   - Add new optional fields without changing defaults
   - Maintain exact Pydantic model behavior

2. **Action Execution**: Improve implementation without changing interfaces
   - Claude Code subprocess → SDK (direct replacement, identical behavior)
   - Better error handling in shell actions
   - Consistent logging across action types

3. **Engine Architecture**: Refactor internal structure
   - Split AutomationEngine/WorkflowEngine responsibilities
   - Extract iteration logic to separate modules
   - Keep CLI interface identical

**Validation**: All existing workflows run with identical results

#### Phase 2: Enhanced Features (Additive Only)
**Duration**: 1-2 weeks
**Approach**: New optional capabilities

1. **New Configuration Options**:
   ```toml
   # Optional new fields, defaults preserve old behavior
   [execution]
   claude_sdk_mode = true  # default: false for compatibility
   enhanced_error_handling = true  # default: false
   ```

2. **Improved Action Types**: Add capabilities without breaking existing syntax
   - Better Claude Code streaming (behind the scenes)
   - Enhanced shell action error reporting
   - Improved template processing

**Validation**: Existing workflows work identically, new features opt-in only

#### Phase 3: Architecture Cleanup (Internal Only)
**Duration**: 2-3 weeks
**Approach**: Module reorganization without external changes

1. **File Structure**: Reorganize internal modules
   ```
   # Keep import compatibility
   from imbi_automations import models  # Still works
   from imbi_automations.models import *  # Still works
   ```

2. **Class Hierarchy**: Improve inheritance without changing public APIs

**Validation**: No workflow changes required, all APIs preserved

### Compatibility Testing Strategy

#### Automated Regression Testing
```bash
# Test matrix for each phase
for workflow in workflows/*/; do
    # Run with old version
    imbi-automations config.toml "$workflow" --project-id 123 > old_result.json

    # Run with new version
    imbi-automations config.toml "$workflow" --project-id 123 > new_result.json

    # Compare results
    diff -u old_result.json new_result.json || echo "REGRESSION: $workflow"
done
```

#### Workflow Compatibility Matrix
Create comprehensive test suite covering:

| Workflow Pattern | Phase 1 | Phase 2 | Phase 3 | Migration Required |
|-----------------|---------|---------|---------|-------------------|
| Direct client calls | ✅ | ✅ | ✅ | None |
| `type="claude"` | ✅ | ✅ | ✅ | None (SDK swap internal) |
| `type="ai-editor"` | ✅ | ✅ | ✅ | None |
| `type="shell"` | ✅ | ✅ | ✅ | None |
| `type="templates"` | ✅ | ✅ | ✅ | None |
| Jinja2 templating | ✅ | ✅ | ✅ | None |
| Remote conditions | ✅ | ✅ | ✅ | None |
| Project filtering | ✅ | ✅ | ✅ | None |

### Rollback Procedures

#### Phase-Level Rollback
Each phase includes immediate rollback capability:
```bash
# Automated rollback script
./scripts/rollback-to-phase.sh previous
```

#### Feature-Level Rollback
Individual improvements can be disabled:
```toml
[compatibility]
force_legacy_claude_mode = true
disable_enhanced_logging = true
```

#### Emergency Procedures
1. **Git-level rollback**: Every phase tagged for instant revert
2. **Configuration override**: Force legacy mode via environment variables
3. **Workflow-level bypass**: Individual workflows can skip improvements

### Documentation Updates
- **CHANGELOG.md**: Document what changes in each phase
- **MIGRATION.md**: Guide for adopting new optional features
- **COMPATIBILITY.md**: Matrix of supported configurations
- **AGENTS.md**: Keep updated with architectural changes

### Success Criteria
- **Zero workflow modifications required**
- **Identical execution results** for existing configurations
- **No performance regressions**
- **All tests pass** throughout migration
- **Complete rollback capability** at each phase

## Implementation Quick Start Guide

### Phase 1 Implementation Order

#### Step 1: Claude Code SDK Replacement (Highest Impact)
**Priority**: Start here - immediate improvement with clear success criteria

1. **Examine Current Implementation**:
   ```bash
   # Study the current subprocess approach
   grep -n "subprocess" src/imbi_automations/claude_code.py
   # Look for the _run_claude_command method around line 144-233
   ```

2. **Add SDK Dependency**:
   ```toml
   # Add to pyproject.toml [project.dependencies]
   "claude-code-sdk>=1.0.0"
   ```

3. **Replace Implementation**:
   - Keep `ClaudeCode.__init__()` signature identical
   - Keep `execute_prompt()` method signature identical
   - Replace `_run_claude_command()` method with SDK calls
   - Maintain exact return format: `{'status': 'success'|'failed', 'stdout': str, 'stderr': str, 'return_code': int, 'execution_time': float, 'attempts': int}`

4. **Test with Existing Workflows**:
   ```bash
   # Test with a simple Claude workflow
   imbi-automations config.toml workflows/compose-fix --project-id [test-id]
   ```

#### Step 2: Engine Responsibility Separation
**Files**: `src/imbi_automations/engine.py` (lines 1-1000+)

1. **Identify Split Points**:
   - `AutomationEngine` (lines ~69-400): Project iteration logic
   - `WorkflowEngine` (lines ~1030+): Workflow execution logic
   - Look for method boundaries and shared state

2. **Create New Files**:
   ```
   src/imbi_automations/
   ├── iterators/
   │   ├── __init__.py
   │   ├── base.py          # ProjectIterator protocol
   │   ├── imbi.py          # ImbiProjectIterator
   │   ├── github.py        # GitHubRepositoryIterator
   │   └── gitlab.py        # GitLabRepositoryIterator
   ```

3. **Extract Gradually**:
   - Move iteration methods first (lowest risk)
   - Keep original classes working during transition
   - Update imports only after verification

#### Step 3: Action Implementation Standardization
**Focus**: Improve existing action types without changing interfaces

1. **Shell Actions** (`engine.py` shell command handling):
   - Add consistent error logging
   - Standardize timeout handling
   - Improve subprocess error capture

2. **Template Actions** (search for `type == "templates"` in engine.py):
   - Ensure consistent file handling
   - Standardize Jinja2 error reporting

### Development Environment Setup
```bash
# Clone and setup
git checkout -b refactor-phase-1
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Run existing tests to establish baseline
pytest --cov=src/imbi_automations

# Test specific workflows
imbi-automations config.toml workflows/ai-editor-example --project-id [test-id]
```

### Key Code Locations for Implementer

#### Current Architecture Entry Points
- **CLI Entry**: `src/imbi_automations/cli.py:222-240` (`main()` function)
- **Engine Factory**: `src/imbi_automations/cli.py:230-235` (AutomationEngine instantiation)
- **Workflow Execution**: `engine.py` around `WorkflowEngine.run()` method
- **Action Dispatch**: Look for large if/elif blocks handling `action.type`

#### Critical Compatibility Points
- **CLI Arguments**: `cli.py:142-219` - Argument parser must remain identical
- **Configuration Loading**: `cli.py:76-90` - TOML parsing must stay the same
- **Workflow Loading**: `cli.py:93-140` - Workflow validation must be preserved
- **Action Results**: Any code returning results to users must maintain format

#### Testing Strategy
```bash
# Before any changes - capture baseline
for workflow in workflows/*/; do
    echo "Testing $workflow"
    timeout 30 imbi-automations config.toml "$workflow" --project-id 123 2>&1 | tee "baseline_$(basename $workflow).log" || true
done

# After each change - compare results
for workflow in workflows/*/; do
    echo "Comparing $workflow"
    timeout 30 imbi-automations config.toml "$workflow" --project-id 123 2>&1 | diff "baseline_$(basename $workflow).log" - || echo "REGRESSION in $workflow"
done
```

## Success Metrics

### Code Quality
- Reduce cyclomatic complexity in `engine.py` from ~15 to <8
- Eliminate circular dependencies
- Achieve >90% test coverage on new modules

### Maintainability
- New workflow types implementable in <100 LOC
- Clear separation between domain concerns
- Consistent error handling patterns

### Performance
- Maintain current workflow execution speed
- Improve error reporting and debugging experience
- Reduce memory usage through better resource management

## Conclusion

This refactoring plan addresses the core architectural issues while preserving the system's proven functionality. The phased approach allows for incremental improvements with minimal disruption to existing workflows. The focus on unifying execution patterns and proper SDK integration will significantly improve code quality and maintainability.

The modular design will make the system more extensible for future requirements while the simplified configuration model will reduce the learning curve for new developers and workflow authors.
