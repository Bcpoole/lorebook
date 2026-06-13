from typing import List, NotRequired, TypedDict


class StoryEntity(TypedDict):
    name: str
    description: str
    tags: NotRequired[List[str]]


class StoryExample(TypedDict):
    label: str
    text: str


class StoryCharacterArtifact(TypedDict):
    name: str
    role: str
    summary: str
    tags: NotRequired[List[str]]


class StoryArtifact(TypedDict):
    title: str
    description: str
    plot: List[str]
    setting: str
    style: str
    tags: List[str]
    characters_artifact: List[StoryCharacterArtifact]
    locations: List[StoryEntity]
    objects: List[StoryEntity]
    opening: str
    examples: List[StoryExample]


class CharacterState(TypedDict):
    name: str
    details: str
    role: NotRequired[str]
    tags: NotRequired[List[str]]
    image_path: NotRequired[str]
    image_prompt: NotRequired[str]
    image_data: NotRequired[str]


class WizardState(TypedDict):
    raw_idea: str
    world_setting: str
    characters: List[CharacterState]
    critique_notes: str
    passed_inspection: bool
    story_artifact: NotRequired[StoryArtifact]
