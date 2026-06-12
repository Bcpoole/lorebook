import { fireEvent, render, screen } from '@testing-library/svelte'
import { tick } from 'svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Toast from './Toast.svelte'

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('auto-dismisses after the provided duration', async () => {
    render(Toast, { props: { message: 'hello', visible: true, duration: 3000 } })

    expect(screen.getByText('hello')).toBeInTheDocument()
    vi.advanceTimersByTime(3000)
    await tick()
    expect(screen.queryByText('hello')).not.toBeInTheDocument()
  })

  it('pauses dismissal while hovered and resumes on mouse leave', async () => {
    render(Toast, { props: { message: 'hover me', visible: true, duration: 3000 } })

    const toast = screen.getByText('hover me')

    vi.advanceTimersByTime(1500)
    await fireEvent.mouseEnter(toast)

    vi.advanceTimersByTime(5000)
    expect(screen.getByText('hover me')).toBeInTheDocument()

    await fireEvent.mouseLeave(toast)
    vi.advanceTimersByTime(1499)
    await tick()
    expect(screen.getByText('hover me')).toBeInTheDocument()

    vi.advanceTimersByTime(1)
    await tick()
    expect(screen.queryByText('hover me')).not.toBeInTheDocument()
  })
})
