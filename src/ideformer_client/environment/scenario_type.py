from enum import Enum


class ScenarioType(Enum):
    FILE_COMMIT_GRAM_REBASE = 'file_commit_gram_scenarios-rebase'
    FILE_COMMIT_GRAM_CHUNK = 'file_commit_gram_scenarios-chunk'
    MERGE = 'merge_scenarios'
    CHERRY_PICK = 'cherry_pick_scenarios'