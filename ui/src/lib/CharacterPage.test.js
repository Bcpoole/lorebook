import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import CharacterPage from './CharacterPage.svelte'

const STORAGE_KEY = 'lorebook.characterPageDraft.v1'

describe('CharacterPage draft persistence', () => {
  beforeEach(() => {
    const backing = new Map()
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem(key) {
          return backing.has(key) ? backing.get(key) : null
        },
        setItem(key, value) {
          backing.set(key, String(value))
        },
        removeItem(key) {
          backing.delete(key)
        },
        clear() {
          backing.clear()
        },
      },
    })
  })

  afterEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  it('restores character page draft from localStorage', async () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        rawIdea: 'A brooding ranger with a cursed blade',
        loading: false,
        error: '',
        workflowState: {
          raw_idea: 'A brooding ranger with a cursed blade',
          world_setting: '',
          characters: [],
          critique_notes: '',
          passed_inspection: false,
        },
        activeAgent: 'character_designer',
        pendingSave: null,
        savedRun: null,
        savedName: '',
      })
    )

    render(CharacterPage)

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Describe the character concept...')).toHaveValue('A brooding ranger with a cursed blade')
    })
  })

  it('resets page after confirmation', async () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        rawIdea: 'An arcane detective',
        loading: false,
        error: 'Previous error',
        workflowState: {
          raw_idea: 'An arcane detective',
          world_setting: '',
          characters: [{ name: 'Mira', details: 'Investigator' }],
          critique_notes: '',
          passed_inspection: false,
        },
        activeAgent: 'character_designer',
        pendingSave: null,
        savedRun: null,
        savedName: 'old.json',
      })
    )

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(CharacterPage)

    await fireEvent.click(screen.getByRole('button', { name: 'Reset' }))

    expect(confirmSpy).toHaveBeenCalled()
    expect(screen.getByPlaceholderText('Describe the character concept...')).toHaveValue('')
    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    })
  })
})
