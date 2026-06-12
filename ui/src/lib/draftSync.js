export class DraftSyncController {
  constructor({
    fetchImpl,
    getPayload,
    getChangeKey = null,
    saveUrl = '/api/draft',
    intervalMs = 1000,
    debounceMs = 200,
    maxWaitMs = 2000,
    onStatusChange = () => {},
  }) {
    this.fetchImpl = fetchImpl
    this.getPayload = getPayload
    this.getChangeKey = getChangeKey
    this.saveUrl = saveUrl
    this.intervalMs = intervalMs
    this.debounceMs = debounceMs
    this.maxWaitMs = maxWaitMs
    this.onStatusChange = onStatusChange

    this.isRunning = false
    this.isDirty = false
    this.isSaving = false
    this.revision = 0
    this.savingRevision = 0
    this.lastError = null

    this.intervalTimer = null
    this.debounceTimer = null
    this.maxWaitTimer = null
    this.lastObservedChangeKey = null
  }

  _now() {
    if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
      return performance.now()
    }
    return Date.now()
  }

  start() {
    if (this.isRunning) return
    this.isRunning = true

    if (this.getChangeKey) {
      try {
        this.lastObservedChangeKey = this.getChangeKey()
      } catch {
        this.lastObservedChangeKey = null
      }
    }

    this.intervalTimer = setInterval(() => {
      this.observeChanges()
      if (!this.isDirty || this.isSaving) return
      void this.flush('interval')
    }, this.intervalMs)
  }

  stop() {
    this.isRunning = false
    this._clearTimers()
  }

  markDirty() {
    this.revision += 1
    this.isDirty = true

    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer)
    }
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null
      if (!this.isSaving) {
        void this.flush('debounce')
      }
    }, this.debounceMs)

    if (!this.maxWaitTimer) {
      this.maxWaitTimer = setTimeout(() => {
        this.maxWaitTimer = null
        if (!this.isSaving) {
          void this.flush('max-wait')
        }
      }, this.maxWaitMs)
    }
  }

  async flushNow(reason = 'manual') {
    await this.flush(reason)
  }

  async flush(reason = 'scheduled') {
    if (!this.isDirty || this.isSaving) return

    const startAt = this._now()
    const payload = this.getPayload()
    const serializeStart = this._now()
    const body = JSON.stringify(payload)
    const serializeMs = this._now() - serializeStart
    const bodyBytes = typeof TextEncoder !== 'undefined'
      ? new TextEncoder().encode(body).length
      : body.length

    this.savingRevision = this.revision
    this.isSaving = true
    this.lastError = null
    this.onStatusChange({
      dirty: this.isDirty,
      saving: this.isSaving,
      lastError: this.lastError,
      reason,
      phase: 'start',
      bodyBytes,
      serializeMs,
    })

    try {
      const res = await this.fetchImpl(this.saveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      })
      if (!res.ok) {
        throw new Error(`Draft save failed: ${res.status}`)
      }

      if (this.revision === this.savingRevision) {
        this.isDirty = false
        if (this.maxWaitTimer) {
          clearTimeout(this.maxWaitTimer)
          this.maxWaitTimer = null
        }
      }
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : 'Draft save failed'
      this.isDirty = true
    } finally {
      this.isSaving = false
      this.onStatusChange({
        dirty: this.isDirty,
        saving: this.isSaving,
        lastError: this.lastError,
        reason,
        phase: 'end',
        bodyBytes,
        serializeMs,
        totalMs: this._now() - startAt,
      })

      if (this.isDirty && this.isRunning && !this.isSaving) {
        setTimeout(() => {
          if (this.isDirty && !this.isSaving) {
            void this.flush('follow-up')
          }
        }, 0)
      }
    }
  }

  observeChanges() {
    if (!this.getChangeKey) return

    let nextKey = null
    try {
      nextKey = this.getChangeKey()
    } catch {
      return
    }

    if (nextKey === this.lastObservedChangeKey) return
    this.lastObservedChangeKey = nextKey
    this.markDirty()
  }

  _clearTimers() {
    if (this.intervalTimer) {
      clearInterval(this.intervalTimer)
      this.intervalTimer = null
    }

    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer)
      this.debounceTimer = null
    }

    if (this.maxWaitTimer) {
      clearTimeout(this.maxWaitTimer)
      this.maxWaitTimer = null
    }
  }
}
