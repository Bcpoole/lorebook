import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PersonaWizard from './PersonaWizard.svelte'

describe('PersonaWizard integration', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads template prompts, generates persona prompts, and emits create payload', async () => {
    const templatePrompts = [
      { key: 'loremaster_system', name: 'Loremaster System', system_prompt: 'Template lore', description: 'Lore' },
      { key: 'character_system', name: 'Character System', system_prompt: 'Template character', description: 'Character' },
      { key: 'editor_system', name: 'Editor System', system_prompt: 'Template editor', description: 'Editor' },
      { key: 'sd_prompt_system', name: 'SD Prompt System', system_prompt: 'Template sd', description: 'SD' },
      { key: 'review_summary_system', name: 'Review Summary System', system_prompt: 'Template review', description: 'Review' },
      { key: 'character_summary_system', name: 'Character Summary System', system_prompt: 'Template char summary', description: 'Character summary' },
      { key: 'character_related_system', name: 'Character Related System', system_prompt: 'Template related', description: 'Character related' },
    ]

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/api/personas/template')) {
        return {
          ok: true,
          async json() {
            return { prompts: templatePrompts }
          },
        }
      }
      if (url.endsWith('/api/experimentation/load')) {
        return {
          ok: true,
          async json() {
            return { sd: { endpoint: 'http://127.0.0.1:7860' } }
          },
        }
      }
      if (url.endsWith('/api/experimentation/generate-persona-prompt')) {
        const body = JSON.parse(init.body)
        return {
          ok: true,
          async json() {
            return {
              key: body.prompt_key,
              system_prompt: `Generated ${body.prompt_key} prompt`,
            }
          },
        }
      }
      if (url.endsWith('/api/experimentation/generate-image')) {
        return {
          ok: true,
          async json() {
            return { avatar: '' }
          },
        }
      }
      throw new Error(`Unexpected fetch call: ${url}`)
    })

    const oncreate = vi.fn()
    const onclose = vi.fn()
    render(PersonaWizard, { oncreate, onclose })

    await fireEvent.input(screen.getByLabelText(/Persona Description/i), {
      target: { value: 'A scifi story writer' },
    })
    await fireEvent.change(screen.getByLabelText(/Style \/ Tone/i), {
      target: { value: 'creative' },
    })

    await fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByLabelText(/Name/i)).toHaveValue('A Scifi Story Writer')
      expect(screen.getByLabelText(/^ID$/i)).toHaveValue('a-scifi-story-writer')
    })

    const generationCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith('/api/experimentation/generate-persona-prompt')
    )
    expect(generationCall).toBeTruthy()
    const generationBody = JSON.parse(generationCall[1].body)
    expect(generationBody.description).toBe('A scifi story writer')
    expect(generationBody.style).toBe('creative')
    expect(generationBody.prompt_key).toBe('loremaster_system')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /♻️ Regenerate All/i })).toBeEnabled()
      expect(screen.getByRole('button', { name: /^Next/i })).toBeEnabled()
    })

    await fireEvent.click(screen.getByRole('button', { name: /^Next/i }))
    await fireEvent.click(screen.getByRole('button', { name: /Skip/i }))
    await fireEvent.click(screen.getByRole('button', { name: /Create Persona/i }))

    expect(oncreate).toHaveBeenCalledTimes(1)
    const createEvent = oncreate.mock.calls[0][0]
    expect(createEvent.detail.persona.name).toBe('A Scifi Story Writer')
    expect(createEvent.detail.persona.prompts).toHaveLength(7)
    expect(
      createEvent.detail.persona.prompts.find((p) => p.key === 'loremaster_system').system_prompt
    ).toBe('Generated loremaster_system prompt')
    expect(
      createEvent.detail.persona.prompts.find((p) => p.key === 'character_related_system').system_prompt
    ).toBe('Generated character_related_system prompt')
    expect(onclose).toHaveBeenCalledTimes(1)
  })
})
