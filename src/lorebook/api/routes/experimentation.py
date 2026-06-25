import base64

import requests
from fastapi import APIRouter, HTTPException

from .. import storage
from lorebook.config.prompts._types import (
    PROMPT_DESCRIPTIONS,
    PROMPT_KEYS,
    PROMPT_LABELS,
    clean_system_prompt_text,
)

router = APIRouter(prefix="/experimentation", tags=["experimentation"])


DEFAULT_EXPERIMENTATION_CONFIG = {
    "general": {
        "outputFormat": "markdown",
        "multilineReplies": True,
        "addCopyTagOnDuplicate": True,
        "includeDefaultSdStyles": True,
    },
    "experimentation": {
        "temperature": 0.7,
        "topP": 0.9,
        "topK": 40,
        "repetitionPenalty": 1.1,
        "maxLength": 512,
        "contextSize": 2048,
        "minP": 0,
        "presencePenalty": 0,
        "samplerSeed": -1,
    },
    "sd": {
        "style": "balanced",
        "endpoint": "http://127.0.0.1:7860",
        "steps": 30,
        "width": 768,
        "height": 768,
        "cfgScale": 3,
        "samplerName": "DPM++ 2M",
        "negativePrompt": "",
    },
}


def get_experimentation_config_path():
    """Get the path to the experimentation config file."""
    base_dir = storage.get_outputs_root()
    return base_dir / "experimentation.json"


@router.post("/save")
async def save_experimentation_config(config: dict) -> dict:
    """Save the experimentation configuration to a local file."""
    try:
        import json

        config_path = get_experimentation_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        return {"status": "success", "path": str(config_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@router.get("/load")
async def load_experimentation_config() -> dict:
    """Load the experimentation configuration from the local file."""
    try:
        import json

        config_path = get_experimentation_config_path()

        if not config_path.exists():
            return DEFAULT_EXPERIMENTATION_CONFIG

        with open(config_path, "r") as f:
            saved = json.load(f)

        # Backward compatibility for older flat experimentation schema.
        if isinstance(saved, dict) and "experimentation" not in saved and (
            "temperature" in saved or "topP" in saved
        ):
            return {
                "general": {
                    "outputFormat": saved.get("outputFormat", DEFAULT_EXPERIMENTATION_CONFIG["general"]["outputFormat"]),
                    "multilineReplies": saved.get(
                        "multilineReplies", DEFAULT_EXPERIMENTATION_CONFIG["general"]["multilineReplies"]
                    ),
                    "addCopyTagOnDuplicate": saved.get(
                        "addCopyTagOnDuplicate",
                        DEFAULT_EXPERIMENTATION_CONFIG["general"]["addCopyTagOnDuplicate"],
                    ),
                    "includeDefaultSdStyles": saved.get(
                        "includeDefaultSdStyles",
                        DEFAULT_EXPERIMENTATION_CONFIG["general"]["includeDefaultSdStyles"],
                    ),
                },
                "experimentation": {
                    "temperature": saved.get("temperature", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["temperature"]),
                    "topP": saved.get("topP", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["topP"]),
                    "topK": saved.get("topK", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["topK"]),
                    "repetitionPenalty": saved.get(
                        "repetitionPenalty", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["repetitionPenalty"]
                    ),
                    "maxLength": saved.get("maxLength", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["maxLength"]),
                    "contextSize": saved.get(
                        "contextSize", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["contextSize"]
                    ),
                    "minP": saved.get("minP", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["minP"]),
                    "presencePenalty": saved.get(
                        "presencePenalty", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["presencePenalty"]
                    ),
                    "samplerSeed": saved.get("samplerSeed", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["samplerSeed"]),
                },
                "sd": {
                    **DEFAULT_EXPERIMENTATION_CONFIG["sd"],
                    **saved.get("sd", {}),
                },
            }

        return {
            "general": {
                **DEFAULT_EXPERIMENTATION_CONFIG["general"],
                **(saved.get("general", {}) if isinstance(saved, dict) else {}),
            },
            "experimentation": {
                **DEFAULT_EXPERIMENTATION_CONFIG["experimentation"],
                **(saved.get("experimentation", {}) if isinstance(saved, dict) else {}),
            },
            "sd": {
                **DEFAULT_EXPERIMENTATION_CONFIG["sd"],
                **(saved.get("sd", {}) if isinstance(saved, dict) else {}),
            },
        }
    except Exception:
        # Return defaults on error
        return DEFAULT_EXPERIMENTATION_CONFIG


@router.post("/generate-persona-prompts")
async def generate_persona_prompts(request: dict) -> dict:
    """Generate all system prompts for a new persona based on description."""
    try:
        from lorebook.config.prompts import get_template_persona
        from lorebook.llm import call_local_llm
        import json
        
        description = request.get("description", "")
        style = request.get("style", "balanced")
        
        if not description:
            raise HTTPException(status_code=400, detail="Description is required")
        
        template = get_template_persona()
        
        # Create a generation prompt that uses the template as reference
        prompt_list = "\n".join([f"- {p.name}: {p.description}" for p in template.prompts.to_prompt_items()])
        
        generation_system = (
            "You are an expert at creating specialized LLM personas and system prompts. "
            "Given a persona description, generate custom system prompts that embody that persona. "
            "Return ONLY valid JSON with no markdown or extra text. "
            "Keep each system_prompt concise (1-3 sentences)."
        )
        
        generation_user = f"""Create a persona based on this description:
{description}

Style: {style}

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
        data = json.loads(response)
        
        prompts = data.get("prompts", [])
        cleaned_prompts = []
        if isinstance(prompts, list):
            for item in prompts:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key", "")).strip()
                system_prompt = clean_system_prompt_text(str(item.get("system_prompt", "")), key or None)
                cleaned_item = dict(item)
                cleaned_item["key"] = key
                cleaned_item["system_prompt"] = system_prompt
                cleaned_prompts.append(cleaned_item)

        return {
            "name": data.get("name", "New Persona"),
            "description": data.get("description", ""),
            "tags": data.get("tags", ["custom"]),
            "prompts": cleaned_prompts,
        }
    
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse generated JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prompts: {str(e)}")


@router.post("/generate-persona-prompt")
async def generate_persona_prompt(request: dict) -> dict:
    """Generate a single system prompt string for a persona."""
    try:
        from lorebook.llm import call_local_llm

        description = str(request.get("description", "")).strip()
        style = str(request.get("style", "balanced")).strip()
        prompt_key = str(request.get("prompt_key", "")).strip()
        template_value = str(request.get("template_value", "")).strip()
        existing_prompt = str(request.get("existing_prompt", "")).strip()

        if not description:
            raise HTTPException(status_code=400, detail="Description is required")
        if prompt_key not in PROMPT_KEYS:
            raise HTTPException(status_code=400, detail=f"Invalid prompt key: {prompt_key}")

        prompt_name = PROMPT_LABELS[prompt_key]
        prompt_description = PROMPT_DESCRIPTIONS[prompt_key]

        generation_system = (
            "You are an expert prompt engineer for story-generation assistants. "
            "Generate exactly one system prompt text, no JSON, no markdown, no code fences. "
            "Keep it concise and practical (3-8 sentences)."
        )
        generation_user = f"""Create a system prompt for:
- Prompt key: {prompt_key}
- Prompt name: {prompt_name}
- Purpose: {prompt_description}
- Persona description: {description}
- Style: {style}

Template baseline:
{template_value}

{f"Current prompt to improve:\n{existing_prompt}\n" if existing_prompt else ""}
Return only the improved system prompt text."""
        if prompt_key == "sd_prompt_system":
            generation_user += (
                "\n\nIMPORTANT: This must be a SYSTEM INSTRUCTION for generating Stable Diffusion prompts, "
                "not an actual image prompt instance."
            )

        response = call_local_llm(
            system_prompt=generation_system,
            user_prompt=generation_user,
            max_length=500,
        ).strip()

        if not response:
            raise HTTPException(status_code=500, detail="Model returned an empty prompt")

        cleaned = clean_system_prompt_text(response, prompt_key)

        return {
            "key": prompt_key,
            "system_prompt": cleaned,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prompt: {str(e)}")


@router.post("/refine-persona-prompt")
async def refine_persona_prompt(request: dict) -> dict:
    """Refine an existing system prompt using user instructions."""
    try:
        from lorebook.llm import call_local_llm

        prompt_key = str(request.get("prompt_key", "")).strip()
        current_prompt = str(request.get("current_prompt", "")).strip()
        template_value = str(request.get("template_value", "")).strip()
        instruction = str(request.get("instruction", "")).strip()
        description = str(request.get("description", "")).strip()
        style = str(request.get("style", "balanced")).strip()

        if prompt_key not in PROMPT_KEYS:
            raise HTTPException(status_code=400, detail=f"Invalid prompt key: {prompt_key}")
        if not instruction:
            raise HTTPException(status_code=400, detail="Instruction is required")

        working_prompt = current_prompt or template_value
        if not working_prompt:
            raise HTTPException(status_code=400, detail="Current prompt is empty")

        prompt_name = PROMPT_LABELS[prompt_key]
        prompt_description = PROMPT_DESCRIPTIONS[prompt_key]

        refine_system = (
            "You are an expert prompt editor. Refine the provided system prompt according to the user's instruction. "
            "Return only the updated system prompt text. No JSON, markdown, labels, or code fences."
        )
        refine_user = f"""Refine this system prompt:
- Prompt key: {prompt_key}
- Prompt name: {prompt_name}
- Purpose: {prompt_description}
- Persona description: {description or "N/A"}
- Style: {style}

Current working prompt:
{working_prompt}

Instruction:
{instruction}

Return only the revised system prompt text."""
        if prompt_key == "sd_prompt_system":
            refine_user += (
                "\n\nIMPORTANT: Keep this as SYSTEM INSTRUCTIONS for generating Stable Diffusion prompts, "
                "not an image prompt instance."
            )

        response = call_local_llm(
            system_prompt=refine_system,
            user_prompt=refine_user,
            max_length=700,
        ).strip()

        if not response:
            raise HTTPException(status_code=500, detail="Model returned an empty prompt")

        cleaned = clean_system_prompt_text(response, prompt_key)
        return {"key": prompt_key, "system_prompt": cleaned}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refine prompt: {str(exc)}")


@router.post("/generate-image")
async def generate_image(request: dict) -> dict:
    """Generate an avatar image for a persona using SD txt2img."""
    prompt = str(request.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Avatar prompt is required")

    sd_config = request.get("sd_config") if isinstance(request.get("sd_config"), dict) else {}
    endpoint = str(sd_config.get("endpoint") or "http://127.0.0.1:7860").rstrip("/")
    steps = int(sd_config.get("steps", 30))
    width = int(sd_config.get("width", 768))
    height = int(sd_config.get("height", 768))
    cfg_scale = float(sd_config.get("cfgScale", 3))
    sampler_name = str(sd_config.get("samplerName", "DPM++ 2M"))
    negative_prompt = str(sd_config.get("negativePrompt", ""))

    try:
        response = requests.post(
            f"{endpoint}/sdapi/v1/txt2img",
            json={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "steps": steps,
                "width": width,
                "height": height,
                "cfg_scale": cfg_scale,
                "sampler_name": sampler_name,
            },
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        images = payload.get("images") if isinstance(payload, dict) else None
        if not isinstance(images, list) or not images or not isinstance(images[0], str):
            raise HTTPException(status_code=500, detail="SD did not return image data")

        encoded = images[0]
        # Validate returned base64.
        base64.b64decode(encoded, validate=True)
        return {
            "avatar": f"data:image/png;base64,{encoded}",
            "prompt": prompt,
        }
    except HTTPException:
        raise
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reach SD endpoint: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(exc)}")


@router.post("/generate-avatar-prompt")
async def generate_avatar_prompt(request: dict) -> dict:
    """Generate an SD avatar prompt from persona context and SD system instructions."""
    from lorebook.llm import call_local_llm

    persona_name = str(request.get("persona_name", "")).strip()
    persona_description = str(request.get("persona_description", "")).strip()
    style = str(request.get("style", "balanced")).strip()
    sd_prompt_system = str(request.get("sd_prompt_system", "")).strip()
    existing_prompt = str(request.get("existing_prompt", "")).strip()

    if not persona_description:
        raise HTTPException(status_code=400, detail="Persona description is required")
    if not sd_prompt_system:
        raise HTTPException(status_code=400, detail="SD prompt system text is required")

    user_prompt = (
        f"Persona name: {persona_name or 'Unnamed persona'}\n"
        f"Persona description: {persona_description}\n"
        f"Style: {style}\n"
        f"{f'Current avatar prompt to refine: {existing_prompt}\n' if existing_prompt else ''}"
        "Create one avatar prompt for this persona."
    )
    try:
        generated = call_local_llm(
            system_prompt=sd_prompt_system,
            user_prompt=user_prompt,
            max_length=220,
        ).strip()
        if not generated:
            raise HTTPException(status_code=500, detail="Model returned an empty avatar prompt")
        return {"prompt": generated.replace("\n", " ").strip()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate avatar prompt: {str(exc)}")
