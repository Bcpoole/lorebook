from typing import Dict, List, TypedDict


class WizardState(TypedDict):
    raw_idea: str
    world_setting: str
    characters: List[Dict[str, str]]
    critique_notes: str
    passed_inspection: bool
