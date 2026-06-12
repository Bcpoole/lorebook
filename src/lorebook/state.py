from typing import List, NotRequired, TypedDict


class CharacterState(TypedDict):
    name: str
    details: str
    image_path: NotRequired[str]
    image_prompt: NotRequired[str]
    image_data: NotRequired[str]


class WizardState(TypedDict):
    raw_idea: str
    world_setting: str
    characters: List[CharacterState]
    critique_notes: str
    passed_inspection: bool
