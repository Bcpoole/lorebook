import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./lib/draftSync', () => {
  class MockDraftSyncController {
    constructor() {}
    start() {}
    stop() {}
    markDirty() {}
    async flushNow() {}
  }

  return { DraftSyncController: MockDraftSyncController }
})

vi.mock('./lib/pollingQueue', () => {
  class MockPollingQueue {
    constructor() {}
    register() {
      return this
    }
    start() {}
    stop() {}
  }

  return { PollingQueue: MockPollingQueue }
})

class MockEventSource {
  static instances = []

  constructor(url) {
    this.url = url
    this.listeners = new Map()
    this.onerror = null
    this.closed = false
    MockEventSource.instances.push(this)
  }

  addEventListener(eventName, callback) {
    const existing = this.listeners.get(eventName) ?? []
    existing.push(callback)
    this.listeners.set(eventName, existing)
  }

  emit(eventName, payload) {
    const callbacks = this.listeners.get(eventName) ?? []
    const event = { data: JSON.stringify(payload) }
    for (const callback of callbacks) {
      callback(event)
    }
  }

  close() {
    this.closed = true
  }
}

function jsonResponse(data, ok = true) {
  return {
    ok,
    async json() {
      return data
    },
  }
}

describe('App stop-generation flow', () => {
  let originalEventSource
  let originalPerformanceObserver

  beforeEach(() => {
    MockEventSource.instances = []

    originalEventSource = globalThis.EventSource
    globalThis.EventSource = MockEventSource

    originalPerformanceObserver = globalThis.PerformanceObserver
    globalThis.PerformanceObserver = undefined

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)

      if (url.includes('/api/sd-styles')) {
        return jsonResponse({ styles: ['balanced'] })
      }

      if (url.includes('/api/experimentation/load')) {
        return jsonResponse({})
      }

      if (url.includes('/api/step-stream')) {
        const encoder = new TextEncoder()
        let readCount = 0
        const signal = init?.signal

        const reader = {
          async read() {
            if (readCount === 0) {
              readCount += 1
              const payload = [
                'event: node-start',
                'data: {"node":"loremaster"}',
                '',
                'event: node-token',
                'data: {"node":"loremaster","chunk":"Partial lore output"}',
                '',
                '',
              ].join('\n')

              return {
                done: false,
                value: encoder.encode(payload),
              }
            }

            await new Promise((resolve, reject) => {
              if (signal?.aborted) {
                const error = new Error('aborted')
                error.name = 'AbortError'
                reject(error)
                return
              }

              signal?.addEventListener(
                'abort',
                () => {
                  const error = new Error('aborted')
                  error.name = 'AbortError'
                  reject(error)
                },
                { once: true }
              )
            })

            return { done: true, value: undefined }
          },
        }

        return {
          ok: true,
          body: {
            getReader() {
              return reader
            },
          },
        }
      }

      if (url.includes('/api/restore-latest')) {
        return jsonResponse({})
      }

      if (url.includes('/api/health')) {
        return jsonResponse({}, true)
      }

      if (url.includes('/api/llm-health')) {
        return jsonResponse({ connected: true })
      }

      if (url.includes('/api/draft')) {
        return jsonResponse({ ok: true })
      }

      return jsonResponse({})
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    globalThis.EventSource = originalEventSource
    globalThis.PerformanceObserver = originalPerformanceObserver
  })

  it('enables Next after stop when streamed output is non-empty', async () => {
    render((await import('./App.svelte')).default)

    const ideaInput = screen.getByPlaceholderText('Describe your world idea…')
    await fireEvent.input(ideaInput, { target: { value: 'A floating archipelago' } })

    const generateButton = screen.getByRole('button', { name: 'Generate' })
    await fireEvent.click(generateButton)

    await screen.findByText(/Partial lore output/i)

    const stopButton = await screen.findByRole('button', { name: 'Running… Click to stop' })
    await fireEvent.click(stopButton)

    const nextButton = await screen.findByRole('button', { name: 'Next: Character Designer' })
    expect(nextButton).toBeEnabled()
  })

  it('resets only the world page state', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render((await import('./App.svelte')).default)

    const storyTab = screen.getByRole('button', { name: /Story/i })
    await fireEvent.click(storyTab)

    const storyInput = screen.getByPlaceholderText('Describe the story concept...')
    await fireEvent.input(storyInput, { target: { value: 'A city built on giant trees' } })

    const worldTab = screen.getByRole('button', { name: /World/i })
    await fireEvent.click(worldTab)

    const worldInput = screen.getByPlaceholderText('Describe your world idea…')
    await fireEvent.input(worldInput, { target: { value: 'A storm-wracked sea kingdom' } })

    const resetButton = screen.getByRole('button', { name: 'Reset' })
    await fireEvent.click(resetButton)

    expect(confirmSpy).toHaveBeenCalled()
    expect(worldInput).toHaveValue('')

    await fireEvent.click(storyTab)
    expect(screen.getByPlaceholderText('Describe the story concept...')).toHaveValue('A city built on giant trees')
  })
})
