import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'

import StoryPage from './StoryPage.svelte'

describe('StoryPage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders story artifact when API returns state.story_artifact', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      async json() {
        return {
          generation_quality: 'full',
          state: {
            story_artifact: {
              title: 'Skyfall',
              description: 'A compact description.',
              plot: ['A', 'B', 'C'],
              setting: 'Sky archipelago',
              style: 'heroic',
              tags: ['sky'],
              characters_artifact: [],
              locations: [],
              objects: [],
              opening: 'Once above the storm.',
              examples: [],
            },
          },
        }
      },
    })

    render(StoryPage, {
      rawIdea: 'Floating city',
      llmConnected: true,
      personaId: 'blank',
      experimentationConfig: {},
      loading: false,
      error: '',
      story: null,
      savedName: '',
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Generate Story' }))

    await waitFor(() => {
      expect(screen.getByText('Skyfall')).toBeInTheDocument()
      expect(screen.getByText('A compact description.')).toBeInTheDocument()
      expect(screen.getByText('sky')).toBeInTheDocument()
      expect(screen.getByText(/Plot Beats/)).toBeInTheDocument()
      expect(screen.getByText('Once above the storm.')).toBeInTheDocument()
      // 'full' quality is nominal — no warning should be shown
      expect(screen.queryByText(/Generation quality/)).not.toBeInTheDocument()
    })
  })

  it('sends setup, instruction, and action for assistant actions', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      async json() {
        return {
          generation_quality: 'repaired',
          story_setup: { tone: 'whimsical' },
          state: {
            story_artifact: {
              title: 'Skyfall',
              description: 'A compact description.',
              plot: ['A', 'B', 'C'],
              setting: '',
              style: 'whimsical',
              tags: [],
              characters_artifact: [],
              locations: [],
              objects: [],
              opening: '',
              examples: [],
            },
          },
        }
      },
    })

    render(StoryPage, {
      rawIdea: 'Floating city',
      llmConnected: true,
      personaId: 'blank',
      experimentationConfig: {},
      loading: false,
      error: '',
      story: {
        title: 'Existing',
        description: 'Existing summary.',
        plot: ['Start', 'Middle', 'End'],
        setting: '',
        style: 'neutral',
        tags: [],
        characters_artifact: [],
        locations: [],
        objects: [],
        opening: '',
        examples: [],
      },
      savedName: '',
      storySetup: {
        protagonist: '',
        opening_preference: '',
        output_format: '',
        tone: 'whimsical',
        length_target: '',
      },
      storyInstruction: 'Raise tension in the next beat.',
      generationQuality: '',
    })

    await fireEvent.click(screen.getByRole('button', { name: '+ Suggest Next Beat' }))

    expect(fetchMock).toHaveBeenCalled()
    const [, request] = fetchMock.mock.calls[0]
    const body = JSON.parse(request.body)
    expect(body.action).toBe('suggest_next_beat')
    expect(body.story_setup.tone).toBe('whimsical')
    expect(body.instruction).toBe('Raise tension in the next beat.')
  })
})
