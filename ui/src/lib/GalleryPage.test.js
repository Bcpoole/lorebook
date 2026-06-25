import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'

import GalleryPage from './GalleryPage.svelte'

function galleryResponse(items) {
  return {
    ok: true,
    async json() {
      return { items, total: items.length, limit: 50, offset: 0 }
    },
  }
}

function mockGalleryFetchByArtifactType() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname !== '/api/gallery') {
      return galleryResponse([])
    }

    const artifactType = url.searchParams.get('artifact_type') || ''
    const item = {
      run_id: `run_${artifactType || 'none'}`,
      artifact_type: artifactType || 'character',
      title: `${artifactType || 'character'} card`,
      avatar_name: `${artifactType || 'character'} card`,
      avatar_data: '',
      tags: [],
      favorite: false,
    }
    return galleryResponse([item])
  })
}

describe('GalleryPage artifact tab filtering', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sends selected Character/Location/Object artifact_type to /api/gallery', async () => {
    const fetchMock = mockGalleryFetchByArtifactType()
    render(GalleryPage)

    await screen.findByRole('button', { name: 'Open character card' })
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('artifact_type=character')

    await fireEvent.click(screen.getByRole('tab', { name: 'Location' }))
    await screen.findByRole('button', { name: 'Open location card' })
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('artifact_type=location')

    await fireEvent.click(screen.getByRole('tab', { name: 'Object' }))
    await screen.findByRole('button', { name: 'Open object card' })
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('artifact_type=object')
  })

  it('honors custom Lore tabs (World/Story) and requests matching artifact_type', async () => {
    const fetchMock = mockGalleryFetchByArtifactType()
    render(GalleryPage, {
      title: 'Lore',
      tabs: [
        { id: 'world', label: 'World', artifactType: 'world' },
        { id: 'story', label: 'Story', artifactType: 'story' },
      ],
      initialTab: 'world',
      enableCharacterModal: false,
    })

    await screen.findByRole('button', { name: 'Open world card' })
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('artifact_type=world')

    await fireEvent.click(screen.getByRole('tab', { name: 'Story' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Open story card' })).toBeInTheDocument())
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('artifact_type=story')
  })
})
