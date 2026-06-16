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
          state: {
            story_artifact: {
              title: 'Skyfall',
              description: 'A compact description.',
              tags: ['sky'],
              opening: 'Once above the storm.',
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
      expect(screen.getByText('Once above the storm.')).toBeInTheDocument()
    })
  })
})
