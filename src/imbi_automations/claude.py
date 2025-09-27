import enum
import json
import logging
import pathlib

import anthropic
import claude_code_sdk
import pydantic

from imbi_automations import mixins, models, prompts, utils, version

LOGGER = logging.getLogger(__name__)
BASE_PATH = pathlib.Path(__file__).parent


class AgentType(enum.StrEnum):
    """Enum for available actions."""

    generator = 'generator'
    validator = 'validator'
    commit = 'commit'


@claude_code_sdk.tool(
    name='response_validator',
    description='Validate the response format from for the final message',
    input_schema=str,
)
def response_validator(message: str) -> str:
    """Use to format the result of an agent run."""
    LOGGER.debug('Validator tool invoked')
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return 'Payload not validate as JSON'
    try:
        models.AgentRun.model_validate(payload)
    except pydantic.ValidationError as exc:
        return str(exc)
    return 'Response is valid'


class Claude(mixins.WorkflowLoggerMixin):
    """Claude Code client for executing AI-powered code transformations."""

    def __init__(
        self,
        config: models.Configuration,
        working_directory: pathlib.Path,
        commit_author: str,
        verbose: bool = False,
    ) -> None:
        super().__init__(verbose)
        self.anthropic = anthropic.AsyncAnthropic()
        self.anthropic_model = config.anthropic.model
        self.commit_author = commit_author
        self.config = config.claude_code
        self.logger: logging.Logger = LOGGER
        self.working_directory = working_directory
        self.client = self._create_client()
        self.session_id: str | None = None

    async def commit(
        self, context: models.WorkflowContext, action: models.WorkflowAction
    ) -> None:
        """Leverage the `commit` agent in Claude Code to commit changes."""
        self.session_id = None
        self._log_verbose_info(
            'Using Claude Code to commit changes fir %s', action.name
        )
        await self.client.connect()
        run = await self._execute_agent(context, action, AgentType.commit)
        await self.client.disconnect()
        if run.result == models.AgentRunResult.failure:
            raise RuntimeError(f'Claude Code commit failed: {run.message}')

    async def execute(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowClaudeAction,
    ) -> None:
        """Execute the Claude Code action."""
        self._set_workflow_logger(context.workflow)
        self._log_verbose_info('Executing Claude Code action: %s', action.name)
        self.session_id = None
        await self.client.connect()

        for cycle in range(1, action.max_cycles + 1):
            self._log_verbose_info(
                'Claude Code cycle %d/%d for action %s',
                cycle,
                action.max_cycles,
                action.name,
            )
            if await self._execute_cycle(context, action, cycle):
                LOGGER.debug('Claude Code cycle %d successful', cycle)
                break

        await self.client.disconnect()

    async def query(self, prompt: str) -> str:
        """Use the Anthropic API to run one-off tasks"""
        message = await self.anthropic.messages.create(
            model=self.anthropic_model,
            max_tokens=8192,
            messages=[{'role': 'user', 'content': prompt}],
        )
        return message.content[0].text

    def _create_client(self) -> claude_code_sdk.ClaudeSDKClient:
        """Create the Claude SDK client, initializing the environment"""
        settings = self._initialize_working_directory()
        LOGGER.debug('Claude Code settings: %s', settings)

        agent_tools = claude_code_sdk.create_sdk_mcp_server(
            'agent_tools', version, [response_validator]
        )

        system_prompt = (BASE_PATH / 'prompts' / 'CLAUDE.md').read_text()
        options = claude_code_sdk.ClaudeCodeOptions(
            add_dirs=[
                self.working_directory / 'workflow',
                self.working_directory / 'extracted',
            ],
            append_system_prompt=system_prompt,
            allowed_tools=[
                'Bash',
                'Bash(git:*)',
                'BashOutput',
                'Edit',
                'Glob',
                'Grep',
                'KillShell',
                'MultiEdit',
                'Read',
                'Task',
                'Write',
                'Write',
                'WebFetch',
                'WebSearch',
                'SlashCommand',
                'mcp__agent_tools__response_validator',
            ],
            cwd=self.working_directory / 'repository',
            extra_args={'settings': str(settings), 'setting-sources': 'local'},
            mcp_servers={'agent_tools': agent_tools},
            settings=str(settings),
            permission_mode='bypassPermissions',
        )
        return claude_code_sdk.ClaudeSDKClient(options)

    async def _execute_agent(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowAction | models.WorkflowClaudeAction,
        agent: AgentType,
    ) -> models.AgentRun:
        prompt = self._get_prompt(context, action, agent)
        await self.client.query(prompt, session_id=self.session_id)
        async for message in self.client.receive_response():
            response = self._parse_message(message)
            if response and isinstance(response, models.AgentRun):
                return response

        return models.AgentRun(
            result=models.AgentRunResult.failure,
            message='Unspecified failure',
            errors=[],
        )

    async def _execute_cycle(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowClaudeAction,
        cycle: int,
    ) -> bool:
        for agent in [AgentType.generator, AgentType.validator]:
            self._log_verbose_info(
                'Executing Claude Code %s agent in cycle %d', agent, cycle
            )
            execution = await self._execute_agent(context, action, agent)
            LOGGER.debug('Execute agent result: %r', execution)
            if execution.result == models.AgentRunResult.failure:
                self.logger.error(
                    'Claude Code %s agent failed in cycle %d', agent, cycle
                )
                return False
        return True

    def _get_prompt(
        self,
        context: models.WorkflowContext,
        action: models.WorkflowAction | models.WorkflowClaudeAction,
        agent: AgentType,
    ) -> str:
        """Return the rendered prompt for the given agent."""
        prompt = f'/{agent}\n\n'

        if agent == AgentType.generator:
            prompt_file = self.working_directory / 'workflow' / action.prompt
        elif agent == AgentType.validator:
            prompt_file = (
                self.working_directory / 'workflow' / action.validation_prompt
            )
        elif agent == AgentType.commit:
            prompt_file = BASE_PATH / 'prompts' / 'commit-context.md.j2'
        else:
            raise RuntimeError(f'Unknown agent: {agent}')

        if prompt_file.suffix == '.j2':
            data = {'commit_author': self.commit_author}
            data.update(context.model_dump())
            data.update({'action': action.model_dump()})
            for key in {'source', 'destination'}:
                if key in data:
                    del data[key]
            prompt += prompts.render(prompt_file, **data)
        else:
            prompt += prompt_file.read_text(encoding='utf-8')

        if agent != AgentType.commit:
            prompt += f'\n\n# Context Data: {context.model_dump_json()}'
        return prompt

    def _initialize_working_directory(self) -> pathlib.Path:
        """Setup dynamic agents and settings for claude-agents action.

        Returns:
            Path to generated settings.json file

        """
        claude_dir = self.working_directory.parent / '.claude'
        agents_dir = claude_dir / 'agents'
        agents_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = pathlib.Path(__file__).parent / 'prompts'

        # Copy over agent prompts
        for action in AgentType:
            source = prompt_path / f'{action}.md'
            destination = agents_dir / f'{action}.md'
            utils.copy(source, destination)

        # Create custom settings.json - disable all global settings
        settings = claude_dir / 'settings.json'
        settings.write_text(
            json.dumps(
                {
                    'agentsPath': str(agents_dir),
                    'hooks': {},
                    'outputStyle': 'plain',
                    'settingSources': ['local'],
                },
                indent=2,
            ),
            encoding='utf-8',
        )

        with settings.open('r', encoding='utf-8') as f:
            LOGGER.debug('Claude Code settings: %s', f.read())

        return settings

    def _log_message(
        self,
        message_type: str,
        content: str
        | list[
            claude_code_sdk.TextBlock
            | claude_code_sdk.ContentBlock
            | claude_code_sdk.ToolUseBlock
            | claude_code_sdk.ToolResultBlock
        ],
    ) -> None:
        """Log the message from Claude Code passed in as a dataclass."""
        if isinstance(content, list):
            for entry in content:
                if isinstance(
                    entry,
                    claude_code_sdk.ToolUseBlock
                    | claude_code_sdk.ToolResultBlock,
                ):
                    continue
                elif isinstance(entry, claude_code_sdk.TextBlock):
                    self.logger.debug('%s: %s', message_type, entry.text)
                else:
                    raise RuntimeError(f'Unknown message type: {type(entry)}')
        else:
            self.logger.debug('%s: %s', message_type, content)

    def _parse_message(
        self, message: claude_code_sdk.Message
    ) -> models.AgentRun | None:
        """Parse the response from Claude Code."""
        if isinstance(message, claude_code_sdk.AssistantMessage):
            self._log_message('Claude Assistant', message.content)
        elif isinstance(message, claude_code_sdk.SystemMessage):
            self.logger.debug('Claude System: %s', message.data)
        elif isinstance(message, claude_code_sdk.UserMessage):
            self._log_message('Claude User', message.content)
        elif isinstance(message, claude_code_sdk.ResultMessage):
            if self.session_id != message.session_id:
                self.session_id = message.session_id
            if message.is_error:
                return models.AgentRun(
                    result=models.AgentRunResult.failure,
                    message='Claude Error',
                    errors=[message.result],
                )
            if message.result.startswith('```json'):
                message.result = message.result[7:]
            if message.result.endswith('```'):
                message.result = message.result[:-3]

            LOGGER.debug('Result (%s): %r', message.session_id, message.result)

            try:
                payload = utils.extract_json(message.result)
            except json.JSONDecodeError as err:
                self.logger.error('Failed to parse JSON result: %s', err)
                return models.AgentRun(
                    result=models.AgentRunResult.failure,
                    errors=[f'Failed to parse JSON result: {err}'],
                    message='Agent Contract Failure',
                )
            return models.AgentRun.model_validate(payload)
        return None
