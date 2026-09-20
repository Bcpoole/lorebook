import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'

import StoryPage from './StoryPage.svelte'

describe('StoryPage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
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
              plot: 'A leads to B and then C.',
              setting: 'Sky archipelago',
              style: 'heroic',
              history: 'The lower islands fell last winter.',
              tags: ['sky'],
              characters_artifact: [],
              locations: [],
              objects: [],
              openings: [{ description: '', messages: [{ role: 'assistant', content: 'Once above the storm.' }] }],
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
      expect(screen.getByLabelText('Story title')).toHaveValue('Skyfall')
      expect(screen.getByLabelText('Story summary')).toHaveValue('A compact description.')
      expect(screen.getByRole('button', { name: 'sky ×' })).toBeInTheDocument()
      expect(screen.getByLabelText('Story plot')).toHaveValue('A leads to B and then C.')
      expect(screen.getByLabelText('Opening 1 message 1')).toHaveValue('Once above the storm.')
      // 'full' quality is nominal — no warning should be shown
      expect(screen.queryByText(/Generation quality/)).not.toBeInTheDocument()
    })
  })

  it('renders progressive Story output from the streaming endpoint', async () => {
    const artifact = {
      title: 'The Glass Current',
      description: 'A courier crosses a city beneath an artificial tide.',
      plot: 'The tide rises.',
      setting: 'Submerged city',
      style: 'speculative',
      history: 'The sea wall failed at midnight.',
      tags: ['tide'],
      characters_artifact: [],
      locations: [],
      objects: [],
      openings: [{ description: '', messages: [{ role: 'assistant', content: 'The waterline climbed the courthouse steps.' }] }],
    }
    const sse = [
      'event: story-stage-start\ndata: {"section":"title","token_budget":80}\n\n',
      `event: story-section-complete\ndata: ${JSON.stringify({ section: 'title', story_artifact: artifact })}\n\n`,
      `event: story-complete\ndata: ${JSON.stringify({ story_artifact: artifact, generation_quality: 'full' })}\n\n`,
      'event: done\ndata: {}\n\n',
    ].join('')
    const responseBody = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sse))
        controller.close()
      },
    })
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      body: responseBody,
    })

    render(StoryPage, {
      rawIdea: 'A city beneath a tide',
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
      expect(fetchMock).toHaveBeenCalledWith('/api/story/stream', expect.any(Object))
      expect(screen.getByLabelText('Story title')).toHaveValue('The Glass Current')
      expect(screen.getByText('Generation progress')).toBeInTheDocument()
      expect(screen.getByText('title')).toBeInTheDocument()
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
              plot: 'A then B then C.',
              setting: '',
              style: 'whimsical',
              history: '',
              tags: [],
              characters_artifact: [],
              locations: [],
              objects: [],
              openings: [],
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
        plot: 'Start, then middle, then end.',
        setting: '',
        style: 'neutral',
        tags: [],
        characters_artifact: [],
        locations: [],
        objects: [],
        history: '',
        openings: [],
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

  it('caches direct module edits without requiring an edit mode', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      async json() {
        return { ok: true }
      },
    })

    render(StoryPage, {
      rawIdea: 'Floating city',
      llmConnected: true,
      story: {
        title: 'Skyfall',
        description: 'A compact description.',
        plot: '',
        setting: '',
        style: '',
        tags: [],
        characters_artifact: [],
        locations: [],
        objects: [],
        history: '',
        openings: [],
      },
      savedName: '',
    })

    await fireEvent.input(screen.getByLabelText('Story title'), { target: { value: 'New Skyfall' } })
    await vi.advanceTimersByTimeAsync(350)

    expect(fetchMock).toHaveBeenCalledWith('/api/draft', expect.any(Object))
    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body).state.story_artifact.title).toBe('New Skyfall')
  })
})
