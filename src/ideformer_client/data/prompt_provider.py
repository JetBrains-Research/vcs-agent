from textwrap import dedent
from typing import Optional, Dict

from src.ideformer_client.environment.scenario_type import ScenarioType


class PromptProvider:

    _USER_PROMPT_CHUNK = ('In the staging area of the git repository within the current directory you will find a file'
                        'with some staged changes. I want you to iteratively commit these changes as logically coherent'
                        'and cohesive as possible. Base your decisions on Clean Code principles, design patterns and system design '
                        'and act as a staff senior software engineer would. Your task is to split the diff into as many'
                        'commits as are needed for the diff to be coherent and cohesive, but always into > 1 commit.'
                        'Create these commits exclusively on in the "{agent_target_branch_name}" branch.'
                        ''
                        'Here is some context about the current state of the repository:'
                        '{context}')

    _USER_PROMPT_REBASE = ('Clean up the commit history of the current Git branch. Focus on the last n commits, '
                              'starting from the current state up to the commit "{scenario_first_commit}". Rebase interactively to reduce the '
                              'total number of commits to k, where k<n. Squash or regroup related commits, ensuring each '
                              'remaining commit represents a distinct, logical change. Eliminate redundant or trivial commits'
                              ' where possible, and ensure commit messages are clear and meaningful. After the rebase, '
                              'verify that the resulting commit history is concise, readable, and free of conflicts.'
                              'Use the exact commits specified and pay attention to use the correct hashes.'
                           ''
                           'Create these commits exclusively on in the "{agent_target_branch_name}" branch.'
                           ''
                           'Here is some context about the current state of the repository:'
                           '{context}')

    _SYSTEM_PROMPT = dedent("""
                You MUST follow the instructions for answering:
                - You are an agent which can operate with the command line and change the file system.
                - You need to execute the given task with the best quality.
                - I have no fingers and the placeholders trauma. Return the entire code template for an answer when needed. NEVER use placeholders.
                - You ALWAYS will be PENALIZED for wrong and low-effort answers.
                - I'm going to tip $1,000,000 for the best reply.
                - Your answer is critical for my career.
                - YOU MUST USE THE PROVIDED TOOLS TO ACTUALLY CHANGE THE FILE SYSTEM.
                """)

    @classmethod
    def get_system_prompt(cls):
        return cls._SYSTEM_PROMPT

    @classmethod
    def get_prompt_for(cls, scenario_type: ScenarioType, scenario: Dict, context: Optional[str],
                       agent_target_branch_name: Optional[str] = None):
        """
        Constructs a prompt for the given task based on the provided scenario type and specifications.

        Args:
            scenario_type (ScenarioType): The type of scenario to get the prompt for.
            scenario (Dict): The actual specifications of the scenario for the given scenario type.
            context (Optional[str]): Additional context for the model to orient itself in the repository. E.g.: git status,
                truncated git log etc.
            agent_target_branch_name (Optional[str]): The name of the branch on which the agent should carry out its actions.

        Raises:
            ValueError if called by an invalid scenario type.
            NotImplementedError if called with merge or cherry pick scenario type.

        Returns:
            str: Returns appropriate response for the given scenario type.
        """
        if scenario_type is ScenarioType.FILE_COMMIT_GRAM_CHUNK:
            return cls._USER_PROMPT_CHUNK.format(context=context, agent_target_branch_name=agent_target_branch_name)
        elif scenario_type is ScenarioType.FILE_COMMIT_GRAM_REBASE:
            return cls._USER_PROMPT_REBASE.format(context=context, agent_target_branch_name=agent_target_branch_name,
                                                  scenario_first_commit=scenario['first_commit'])
        elif scenario_type is ScenarioType.MERGE:
            return NotImplementedError
        elif scenario_type is ScenarioType.CHERRY_PICK:
            return NotImplementedError
        else:
            return ValueError('No other scenarios are valid.')