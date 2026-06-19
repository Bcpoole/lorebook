"""API routes for Persona CRUD operations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lorebook.config.personas import load_persona, save_persona, list_personas, delete_persona
from lorebook.config.prompts import get_template_persona
from lorebook.config.prompts._types import PersonaMeta, PersonaPrompts

router = APIRouter(prefix="/personas", tags=["personas"])


class PersonaPromptRequest(BaseModel):
    """Request model for persona prompt."""
    key: str
    name: str
    system_prompt: str
    description: str = ""


class PersonaRequest(BaseModel):
    """Request model for creating/updating a persona."""
    id: str
    name: str
    description: str
    tags: list[str] = []
    favorite: bool | None = None
    avatar: str = ""
    prompts: dict | list[PersonaPromptRequest] = {}


def _prompt_items(prompts: PersonaPrompts) -> list[dict]:
    return [
        {
            "key": p.key,
            "name": p.name,
            "system_prompt": p.system_prompt,
            "description": p.description,
        }
        for p in prompts.to_prompt_items()
    ]


def _parse_prompts(payload: dict | list[PersonaPromptRequest]) -> PersonaPrompts:
    if isinstance(payload, list):
        items = [p.model_dump() if hasattr(p, "model_dump") else p.dict() for p in payload]
        return PersonaPrompts.from_prompt_items(items)
    if isinstance(payload, dict):
        return PersonaPrompts.from_dict(payload)
    return PersonaPrompts()


def _avatar_url(persona: PersonaMeta) -> str | None:
    return f"/api/personas/{persona.id}/avatar" if str(persona.avatar or "").strip() else None


def _persona_payload(persona: PersonaMeta, include_prompts: bool = False) -> dict:
    payload = {
        "id": persona.id,
        "name": persona.name,
        "description": persona.description,
        "tags": persona.tags,
        "favorite": bool(persona.favorite),
        "avatar": persona.avatar,
        "avatarUrl": _avatar_url(persona),
        "promptCount": len(persona.prompts.to_prompt_items()),
        "created": persona.created,
        "modified": persona.modified,
    }
    if include_prompts:
        payload["prompts"] = _prompt_items(persona.prompts)
    return payload


@router.get("")
async def list_all_personas() -> list[dict]:
    """Return metadata for all persisted personas."""
    persisted = list_personas()
    result = []
    for persona in persisted:
        result.append(_persona_payload(persona))
    return result


@router.get("/template")
async def get_template() -> dict:
    """Return the template persona with all default prompts."""
    template = get_template_persona()
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "tags": template.tags,
        "favorite": bool(template.favorite),
        "avatar": template.avatar,
        "avatarUrl": _avatar_url(template),
        "created": template.created,
        "modified": template.modified,
        "prompts": _prompt_items(template.prompts),
    }


@router.get("/{persona_id}")
async def get_persona(persona_id: str) -> dict:
    """Get a persona by ID."""
    # Only allow simple alphanumeric + hyphen/underscore ids to prevent path traversal
    if not persona_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid persona id")
    
    persona = load_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    return _persona_payload(persona, include_prompts=True)


@router.post("")
async def create_persona(request: PersonaRequest) -> dict:
    """Create a new persona."""
    # Validate ID
    if not request.id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid persona id")
    
    # Check if persona already exists
    existing = load_persona(request.id)
    if existing:
        raise HTTPException(status_code=409, detail="Persona already exists")
    
    # Create persona with prompts
    prompts = _parse_prompts(request.prompts)
    
    persona = PersonaMeta(
        id=request.id,
        name=request.name,
        description=request.description,
        tags=request.tags,
        favorite=bool(request.favorite) if request.favorite is not None else False,
        avatar=request.avatar,
        prompts=prompts,
    )
    
    success = save_persona(persona)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save persona")
    
    return _persona_payload(persona, include_prompts=True)


@router.put("/{persona_id}")
async def update_persona(persona_id: str, request: PersonaRequest) -> dict:
    """Update an existing persona."""
    # Only allow simple alphanumeric + hyphen/underscore ids to prevent path traversal
    if not persona_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid persona id")
    
    # Check if persona exists
    existing = load_persona(persona_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    # Create updated persona
    prompts = _parse_prompts(request.prompts)
    
    persona = PersonaMeta(
        id=persona_id,  # Keep original ID
        name=request.name,
        description=request.description,
        tags=request.tags,
        favorite=existing.favorite if request.favorite is None else bool(request.favorite),
        avatar=request.avatar,
        prompts=prompts,
    )
    
    success = save_persona(persona)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update persona")
    
    return _persona_payload(persona, include_prompts=True)


@router.delete("/{persona_id}")
async def delete_persona_route(persona_id: str) -> dict:
    """Delete a persona by ID."""
    # Only allow simple alphanumeric + hyphen/underscore ids to prevent path traversal
    if not persona_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid persona id")
    
    # Check if persona exists
    existing = load_persona(persona_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    success = delete_persona(persona_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete persona")
    
    return {"success": True, "message": f"Persona {persona_id} deleted"}
