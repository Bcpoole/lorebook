from typing import Dict, List, NotRequired, TypedDict


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
    id: NotRequired[str]           # urn:lorebook:character:{uuid}
    name: str
    details: str
    summary: NotRequired[str]      # short bio generated at save time
    role: NotRequired[str]         # "character" | "persona"
    tags: NotRequired[List[str]]
    relationships: NotRequired[Dict[str, str]]  # { urn -> relationship label }
    # image fields — live UI only, stripped before disk save
    image_path: NotRequired[str]   # renamed from image_path; path on disk
    image_prompt: NotRequired[str]
    image_data: NotRequired[str]   # base64 data URI — NOT saved to disk


class WizardState(TypedDict):
    raw_idea: str
    world_setting: str
    characters: List[CharacterState]
    critique_notes: str
    passed_inspection: bool
    story_artifact: NotRequired[StoryArtifact]
    story_setup: NotRequired[Dict[str, str]]
    story_instruction: NotRequired[str]
