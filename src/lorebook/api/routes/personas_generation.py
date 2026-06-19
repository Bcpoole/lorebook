"""API routes for persona generation via wizard."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lorebook.llm import call_local_llm
from lorebook.config.prompts import get_template_persona

router = APIRouter(prefix="/personas-generation", tags=["personas"])


class GeneratePersonaPromptsRequest(BaseModel):
    """Request for generating persona prompts."""
    description: str
    style: str = "balanced"


class GeneratePersonaImageRequest(BaseModel):
    """Request for generating persona avatar image."""
    persona_name: str
    style: str = "balanced"


@router.post("/generate-prompts")
async def generate_persona_prompts(request: GeneratePersonaPromptsRequest) -> dict:
    """Generate all system prompts for a new persona based on description.
    
    Takes a high-level persona description and generates custom system prompts
    for each of the required prompt types.
    """
    try:
        template = get_template_persona()
        
        # Create a generation prompt that uses the template as reference
        prompt_list = "\n".join([f"- {p.name}: {p.description}" for p in template.prompts.to_prompt_items()])
        
        generation_system = (
            "You are an expert at creating specialized LLM personas and system prompts. "
            "Given a persona description, generate custom system prompts that embody that persona. "
            "Return ONLY valid JSON with no markdown or extra text. "
            "Keep each system_prompt concise (1-3 sentences)."
        )
        
        generation_user = f"""Create a persona named based on this description:
{request.description}

Style: {request.style}

Generate JSON with this exact structure (no markdown):
{{
  "name": "Persona Name",
  "description": "Short description",
  "tags": ["tag1", "tag2", "tag3"],
  "prompts": [
    {{
      "key": "loremaster_system",
      "system_prompt": "..."
    }},
    {{
      "key": "character_system",
      "system_prompt": "..."
    }},
    {{
      "key": "editor_system",
      "system_prompt": "..."
    }},
    {{
      "key": "sd_prompt_system",
      "system_prompt": "..."
    }},
    {{
      "key": "review_summary_system",
      "system_prompt": "..."
    }},
    {{
      "key": "character_summary_system",
      "system_prompt": "..."
    }},
    {{
      "key": "character_related_system",
      "system_prompt": "..."
    }}
  ]
}}

Each prompt should be customized for the persona described above, building on these templates:
{prompt_list}"""
        
        response = call_local_llm(
            system_prompt=generation_system,
            user_prompt=generation_user,
            max_length=1200,
        )
        
        # Parse the response as JSON
        import json
        data = json.loads(response)
        
        return {
            "name": data.get("name", "New Persona"),
            "description": data.get("description", ""),
            "tags": data.get("tags", ["custom"]),
            "prompts": data.get("prompts", []),
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prompts: {str(e)}")


@router.post("/generate-image")
async def generate_persona_image(request: GeneratePersonaImageRequest) -> dict:
    """Generate an avatar image for a persona (placeholder).
    
    Currently returns a placeholder. In production, this would call Stable Diffusion
    or another image generation API.
    """
    # For now, return a placeholder response
    # In production, this would call an image generation service
    return {
        "avatar": "",  # Empty for now - would be image path or data URI
        "message": "Image generation not yet configured"
    }
