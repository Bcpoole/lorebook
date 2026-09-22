import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PageAgentPanel from './PageAgentPanel.svelte'

describe('PageAgentPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('stages proposed changes on the active page without rendering raw JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      async json() {
        return {
          reply: 'I tightened the story summary.',
          changes: [
            {
              field: 'description',
              label: 'Story summary',
              before: 'Old summary',
              after: 'New summary',
            },
          ],
        }
      },
    })
    const onproposals = vi.fn()

    render(PageAgentPanel, {
      props: {
        page: 'story',
        pageLabel: 'Story',
        context: { editable: { description: 'Old summary' } },
        personaOptions: [{ id: 'blank', name: 'Blank' }],
        selectedPersona: { id: 'blank', name: 'Blank', description: 'Neutral' },
        selectedPersonaId: 'blank',
        connected: true,
        onproposals,
      },
    })

    expect(screen.queryByText(/Chat about this story/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Message page orchestrator')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Send' })).toBeVisible()

    await fireEvent.input(screen.getByLabelText('Message page orchestrator'), {
      target: { value: 'Tighten the summary' },
    })
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await screen.findByText('Story summary')
    await waitFor(() => {
      expect(onproposals).toHaveBeenCalledWith({
        page: 'story',
        changes: [
          {
            field: 'description',
            label: 'Story summary',
            before: 'Old summary',
            after: 'New summary',
          },
        ],
      })
    })
    expect(screen.getByText('Review New / Old in Story')).toBeInTheDocument()
    expect(screen.queryByText('New summary')).not.toBeInTheDocument()
    expect(screen.queryByText('Old summary')).not.toBeInTheDocument()
  })
})
