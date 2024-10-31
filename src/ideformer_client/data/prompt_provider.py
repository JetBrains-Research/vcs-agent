from textwrap import dedent
from typing import Optional

from src.ideformer_client.environment.scenario_type import ScenarioType


class PromptProvider:

    _USER_PROMPT_CHUNK = ('In the staging area of the git repository within the current directory you will find a file'
                       'with some staged changes. I want you to iteratively commit these changes as logically coherent'
                       'and cohesive as possible. Base your decisions on Clean Code principles, design patterns and system design '
                       'and act as a staff senior software engineer would. Create these commits in the "demo" branch and show'
                       'me the git log of only the branch and commits you created.'
                        ''
                        'Here is some context about the current state of the repository:'
                        '{context}')

    _USER_PROMPT_REBASE = ('Clean up the commit history of the current Git branch. Focus on the last n commits, '
                              'starting from the current state up to the commit "68e876ee". Rebase interactively to reduce the '
                              'total number of commits to k, where k<n. Squash or regroup related commits, ensuring each '
                              'remaining commit represents a distinct, logical change. Eliminate redundant or trivial commits'
                              ' where possible, and ensure commit messages are clear and meaningful. After the rebase, '
                              'verify that the resulting commit history is concise, readable, and free of conflicts.'
                              'Use the exact commits specified and pay attention to use the correct hashes.'
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
    def get_prompt_for(cls, scenario_type: ScenarioType, context: Optional[str]):
        """
        Args:
            scenario_type (ScenarioType): The type of scenario to get the prompt for.
            context (Optional[str]): Additional context for the model to orient itself in the repository. E.g.: git status,
                truncated git log etc.

        Raises:
            ValueError if called by an invalid scenario type.
            NotImplementedError if called with merge or cherry pick scenario type.

        Returns:
            str: Returns appropriate response for the given scenario type.
        """
        if scenario_type is ScenarioType.FILE_COMMIT_GRAM_CHUNK:
            return cls._USER_PROMPT_CHUNK.format(context=context)
        elif scenario_type is ScenarioType.FILE_COMMIT_GRAM_REBASE:
            return cls._USER_PROMPT_REBASE.format(context=context)
        elif scenario_type is ScenarioType.MERGE:
            return NotImplementedError
        elif scenario_type is ScenarioType.CHERRY_PICK:
            return NotImplementedError
        else:
            return ValueError('No other scenarios are valid.')