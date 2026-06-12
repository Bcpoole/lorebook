/**
 * PollingQueue — serialized scheduled task runner.
 *
 * Instead of independent setIntervals that can fire simultaneously,
 * all periodic tasks share one setTimeout chain. A configurable
 * minimum spacing ensures at least `minSpacingMs` passes between
 * any two consecutive task executions, preventing concurrent state
 * writes and back-to-back re-render bursts.
 *
 * Usage:
 *   const queue = new PollingQueue({ minSpacingMs: 300 })
 *   queue
 *     .register('app-health', 5_000, myAppCheckFn)
 *     .register('llm-health', 20_000, myLlmCheckFn)
 *     .start()
 *
 *   // Later, change an interval (e.g. faster retry on disconnect):
 *   queue.register('llm-health', 10_000, myLlmCheckFn)
 *
 *   // Tear down:
 *   queue.stop()
 */
export class PollingQueue {
  constructor({ minSpacingMs = 300 } = {}) {
    this.tasks = new Map()     // id → { id, intervalMs, fn, nextRunAt }
    this.runningIds = new Set()
    this.minSpacingMs = minSpacingMs
    this.tickTimer = null
    this.isRunning = false
    this.lastEndAt = 0
  }

  /**
   * Register (or replace) a recurring task.
   * If the id already exists the interval and fn are updated but
   * the existing nextRunAt is preserved so it doesn't lose its turn.
   */
  register(id, intervalMs, fn) {
    const existing = this.tasks.get(id)
    this.tasks.set(id, {
      id,
      intervalMs,
      fn,
      nextRunAt: existing ? existing.nextRunAt : Date.now(),
    })
    if (this.isRunning) this._scheduleTick()
    return this
  }

  unregister(id) {
    this.tasks.delete(id)
    this.runningIds.delete(id)
    if (this.isRunning) this._scheduleTick()
    return this
  }

  start() {
    if (this.isRunning) return this
    this.isRunning = true
    this._scheduleTick()
    return this
  }

  stop() {
    this.isRunning = false
    if (this.tickTimer !== null) {
      clearTimeout(this.tickTimer)
      this.tickTimer = null
    }
    this.runningIds.clear()
  }

  // --- internal ---

  _nextDue() {
    let earliest = null
    for (const task of this.tasks.values()) {
      if (this.runningIds.has(task.id)) continue
      if (!earliest || task.nextRunAt < earliest.nextRunAt) {
        earliest = task
      }
    }
    return earliest
  }

  _scheduleTick() {
    if (this.tickTimer !== null) {
      clearTimeout(this.tickTimer)
      this.tickTimer = null
    }
    if (!this.isRunning || this.tasks.size === 0) return

    const next = this._nextDue()
    if (!next) return // all tasks currently running

    const now = Date.now()
    // Honour minimum spacing between any two consecutive executions
    const earliestAllowed = this.lastEndAt + this.minSpacingMs
    const runAt = Math.max(next.nextRunAt, earliestAllowed)
    const delay = Math.max(0, runAt - now)

    this.tickTimer = setTimeout(() => {
      this.tickTimer = null
      void this._runTask(next.id)
    }, delay)
  }

  async _runTask(id) {
    if (!this.isRunning) return
    const task = this.tasks.get(id)
    if (!task || this.runningIds.has(id)) return

    this.runningIds.add(id)
    try {
      await task.fn()
    } catch {
      // Each task is responsible for its own error handling.
    } finally {
      this.runningIds.delete(id)
      this.lastEndAt = Date.now()
      // Use the *current* registration in case it was replaced while running
      const current = this.tasks.get(id)
      if (current) {
        current.nextRunAt = this.lastEndAt + current.intervalMs
      }
      this._scheduleTick()
    }
  }
}
