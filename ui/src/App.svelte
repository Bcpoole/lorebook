<script>
  import { onDestroy, onMount } from 'svelte'
  import RawIdeaForm from './lib/RawIdeaForm.svelte'
  import AgentPanel from './lib/AgentPanel.svelte'
  import TopBar from './lib/TopBar.svelte'
  import Toast from './lib/Toast.svelte'
  import ExperimentationPanel from './lib/ExperimentationPanel.svelte'
  import { DraftSyncController } from './lib/draftSync'
  import { PollingQueue } from './lib/pollingQueue'

  let state = $state({})
  let meta = $state({})
  let running = $state(false)
  let streaming = $state(true)
  let auto = $state(false)
  let showStats = $state(false)
  let activeTab = $state('agents')
  let activeAgentTab = $state('loremaster')
  let graphPanelLoad = $state(null)
  let currentRawIdea = $state('')
  let nextStage = $state(null)

  let pendingSave = $state(null)
  let savedRun = $state(null)
  let filename = $state('')
  let suggesting = $state(false)
  let toastMessage = $state('')
  let toastVisible = $state(false)
  let activeEventSource = $state(null)
  let activeAbortController = $state(null)
  let restoreDone = $state(false)
  let draftSync = null
  let pollingQueue = null
  let restoreToastTimer = null
  let appServerConnected = $state(true)
  let llmConnected = $state(true)
  let restoredDraft = $state(null)
  let outputStale = $state(false)

  // Experimentation state
  let experimentationLive = $state({
    temperature: 0.7,
    topP: 0.9,
    topK: 40,
    repetitionPenalty: 1.1,
    maxLength: 512,
    contextSize: 2048,
    outputFormat: 'markdown',
    multilineReplies: true,
    minP: 0,
    presencePenalty: 0,
    samplerSeed: -1,
  })
  let experimentationSaved = $state(JSON.parse(JSON.stringify(experimentationLive)))
  let experimentationDirty = $state(false)
  let llmCountdown = 10
  let llmCountdownDisplay = $state(10)
  let reconnectCountdownTimer = null
  let appHealthInFlight = false
  let heartbeatInFlight = false
  let perfObserver = null
  let perfDebugEnabled = false
  let perfStats = $state({
    autosaveCount: 0,
    autosaveMaxMs: 0,
    autosaveMaxBytes: 0,
    autosaveMaxSerializeMs: 0,
    longTaskCount: 0,
    longTaskMaxMs: 0,
  })

  const APP_HEALTH_POLL_SECONDS = 5
  const HEALTH_POLL_SECONDS = 20
  const RECONNECT_SECONDS = 10

  function apiReady() {
    return appServerConnected && llmConnected
  }

  function generateDefaultFilename() {
    return crypto.randomUUID().replace(/-/g, '')
  }

  function stageLabel(stage) {
    const labels = {
      loremaster: 'Loremaster',
      character_designer: 'Character Designer',
      editor: 'Editor',
      save_assets: 'Save Assets',
    }
    return labels[stage] ?? 'Next'
  }

  function getNextButtonLabel() {
    if (!nextStage) return 'Next'
    return `Next: ${stageLabel(nextStage)}`
  }

  function freshWorkflowState(rawIdea = '') {
    return {
      raw_idea: rawIdea,
      world_setting: '',
      characters: [],
      critique_notes: '',
      passed_inspection: false,
    }
  }

  function canContinueStage(stage) {
    if (stage === 'loremaster') return Boolean(state.world_setting)
    if (stage === 'character_designer') return Boolean(state.characters?.some((character) => character?.details))
    if (stage === 'editor') return Boolean(state.critique_notes) && state.passed_inspection !== true
    return false
  }

  function getStageFromState(localState, savePending = false) {
    if (savePending) return 'save_assets'
    // On restore, land on the stage where progress exists
    if (localState?.critique_notes) return 'editor'
    if (localState?.characters?.length) return 'character_designer'
    if (localState?.world_setting) return 'loremaster'
    return 'loremaster'
  }

  function applyRestoredPayload(payload, source = 'draft') {
    if (!payload) return false

    currentRawIdea = payload.raw_idea ?? ''
    state = payload.state ?? {}
    meta = payload.meta ?? {}
    pendingSave = payload.save_pending ? { raw_idea: currentRawIdea, state, meta } : null
    savedRun = source === 'run' && payload.run_id ? {
      run_id: payload.run_id,
      run_path: payload.run_path,
      filename: payload.filename ?? payload.run_id,
    } : null
    nextStage = payload.meta?.next_stage ?? null
    activeAgentTab = getStageFromState(state, Boolean(payload.save_pending))
    restoredDraft = source === 'draft' ? payload : null
    outputStale = false
    filename = ''
    return true
  }

  function showRestoreToast(message) {
    toastMessage = message
    toastVisible = true
    if (restoreToastTimer) {
      clearTimeout(restoreToastTimer)
    }
    restoreToastTimer = setTimeout(() => {
      toastVisible = false
      restoreToastTimer = null
    }, 3000)
  }

  async function checkAppHealth() {
    if (appHealthInFlight) return appServerConnected
    appHealthInFlight = true
    try {
      const res = await fetch('/api/health', { cache: 'no-store' })
      const nextConnected = res.ok

      // Batch: only touch state if something actually changed to avoid spurious re-renders
      if (nextConnected !== appServerConnected) {
        const wasConnected = appServerConnected
        appServerConnected = nextConnected

        if (!appServerConnected) {
          llmConnected = false
          stopReconnectCountdown()
        }

        if (wasConnected && !appServerConnected) {
          toastMessage = 'Application server is unreachable. Waiting for reconnect.'
          toastVisible = true
        }

        if (!wasConnected && appServerConnected) {
          toastMessage = 'Application server reconnected.'
          toastVisible = true
        }
      }

      return appServerConnected
    } catch {
      if (appServerConnected) {
        appServerConnected = false
        llmConnected = false
        stopReconnectCountdown()
        toastMessage = 'Application server is unreachable. Waiting for reconnect.'
        toastVisible = true
      }
      return false
    } finally {
      appHealthInFlight = false
    }
  }

  async function checkLlmHealth() {
    if (!appServerConnected) {
      llmConnected = false
      return false
    }

    if (heartbeatInFlight) return llmConnected
    heartbeatInFlight = true
    try {
      const res = await fetch('/api/llm-health', { cache: 'no-store' })
      let nextConnected = false

      if (res.ok) {
        const data = await res.json().catch(() => ({}))
        nextConnected = data?.connected === true
      }

      // Only update state if something changed
      if (nextConnected !== llmConnected) {
        const wasConnected = llmConnected
        llmConnected = nextConnected

        if (!wasConnected && llmConnected) {
          toastMessage = 'LLM connection restored.'
          toastVisible = true
        }
      }

      return llmConnected
    } catch {
      if (llmConnected) {
        llmConnected = false
      }
      return false
    } finally {
      heartbeatInFlight = false
    }
  }

  function stopReconnectCountdown() {
    if (reconnectCountdownTimer) {
      clearInterval(reconnectCountdownTimer)
      reconnectCountdownTimer = null
    }
  }

  function startReconnectCountdown() {
    if (!appServerConnected) return

    stopReconnectCountdown()
    llmCountdown = RECONNECT_SECONDS
    llmCountdownDisplay = RECONNECT_SECONDS

    reconnectCountdownTimer = setInterval(() => {
      if (!appServerConnected) {
        stopReconnectCountdown()
        return
      }

      if (llmConnected) {
        stopReconnectCountdown()
        return
      }

      llmCountdown = Math.max(0, llmCountdown - 1)
      llmCountdownDisplay = llmCountdown
      if (llmCountdown > 0) return
      llmCountdown = RECONNECT_SECONDS
      void checkLlmHealth()
    }, 1000)
  }

  async function appHealthTask() {
    const appConnected = await checkAppHealth()
    if (!appConnected) return
    // If app just reconnected but LLM is still down, ensure countdown is running
    if (!llmConnected && !reconnectCountdownTimer) {
      startReconnectCountdown()
    }
  }

  async function llmHealthTask() {
    if (!appServerConnected) return
    const connected = await checkLlmHealth()
    if (!connected && !reconnectCountdownTimer) {
      startReconnectCountdown()
    }
  }

  function startLlmHeartbeat() {
    if (pollingQueue) {
      pollingQueue.stop()
    }
    pollingQueue = new PollingQueue({ minSpacingMs: 300 })
    pollingQueue
      .register('app-health', APP_HEALTH_POLL_SECONDS * 1000, appHealthTask)
      .register('llm-health', HEALTH_POLL_SECONDS * 1000, llmHealthTask)
      .start()
  }

  function stopLlmHeartbeat() {
    if (pollingQueue) {
      pollingQueue.stop()
      pollingQueue = null
    }
    stopReconnectCountdown()
  }

  function offlineToastMessage() {
    if (!appServerConnected) {
      return 'Application server is offline. Waiting for reconnect.'
    }
    return 'LLM backend is offline. Waiting for reconnect.'
  }

  async function ensureApiReady() {
    if (apiReady()) return true

    toastMessage = offlineToastMessage()
    toastVisible = true

    if (!appServerConnected) {
      await checkAppHealth()
    }

    return apiReady()
  }

  function draftPayload() {
    const isEmpty = !currentRawIdea && !state?.world_setting && !(state?.characters?.length) && !state?.critique_notes
    if (isEmpty) {
      return { clear: true }
    }

    return {
      raw_idea: currentRawIdea,
      state,
      meta,
      save_pending: Boolean(pendingSave),
    }
  }

  function draftChangeKey() {
    const characters = state?.characters ?? []
    let nameLengthTotal = 0
    let detailsLengthTotal = 0
    let imageCount = 0
    for (const character of characters) {
      nameLengthTotal += (character?.name ?? '').length
      detailsLengthTotal += (character?.details ?? '').length
      if (character?.image_path || character?.image_data) {
        imageCount += 1
      }
    }

    const worldLength = (state?.world_setting ?? '').length
    const critiqueLength = (state?.critique_notes ?? '').length
    const rawLength = (currentRawIdea ?? '').length
    const nextStageValue = meta?.next_stage ?? ''
    const stageValue = meta?.stage ?? ''
    const elapsedValue = meta?.elapsed_ms ?? ''

    return [
      rawLength,
      worldLength,
      critiqueLength,
      characters.length,
      nameLengthTotal,
      detailsLengthTotal,
      imageCount,
      state?.passed_inspection ? 1 : 0,
      nextStageValue,
      stageValue,
      elapsedValue,
      pendingSave ? 1 : 0,
    ].join('|')
  }

  function handleDraftSyncStatus(status) {
    if (status?.phase !== 'end') return

    const totalMs = Number(status.totalMs || 0)
    const bodyBytes = Number(status.bodyBytes || 0)
    const serializeMs = Number(status.serializeMs || 0)

    perfStats = {
      ...perfStats,
      autosaveCount: perfStats.autosaveCount + 1,
      autosaveMaxMs: Math.max(perfStats.autosaveMaxMs, totalMs),
      autosaveMaxBytes: Math.max(perfStats.autosaveMaxBytes, bodyBytes),
      autosaveMaxSerializeMs: Math.max(perfStats.autosaveMaxSerializeMs, serializeMs),
    }

    if (perfDebugEnabled && (totalMs >= 25 || serializeMs >= 8 || bodyBytes >= 200_000)) {
      console.debug('[perf][autosave]', {
        reason: status.reason,
        totalMs,
        serializeMs,
        bodyBytes,
      })
    }
  }

  function setupPerfObserver() {
    if (!perfDebugEnabled) return
    if (typeof PerformanceObserver === 'undefined') return

    try {
      perfObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const duration = Number(entry.duration || 0)
          perfStats = {
            ...perfStats,
            longTaskCount: perfStats.longTaskCount + 1,
            longTaskMaxMs: Math.max(perfStats.longTaskMaxMs, duration),
          }
          if (duration >= 50) {
            console.debug('[perf][longtask]', { duration })
          }
        }
      })
      perfObserver.observe({ entryTypes: ['longtask'] })
    } catch {
      perfObserver = null
    }
  }

  async function restoreOnLaunch() {
    try {
      const res = await fetch('/api/restore-latest')
      if (!res.ok) return
      const data = await res.json()
      if (!data?.draft) return

      applyRestoredPayload(data.draft, 'draft')
      showRestoreToast('Restored latest in-progress draft.')
    } catch {
      // Ignore restore failures.
    }
  }

  async function setSmartFilename(rawIdea) {
    try {
      const res = await fetch('/api/suggest-name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_idea: rawIdea }),
      })
      const data = await res.json()
      filename = data.name
    } catch {
      filename = generateDefaultFilename()
    }
  }

  function openGraphTab() {
    activeTab = 'graph'
    if (!graphPanelLoad) {
      graphPanelLoad = import('./lib/GraphPanel.svelte')
    }
  }

  function clearActiveHandles() {
    activeEventSource = null
    activeAbortController = null
  }

  function isAbortError(error) {
    return error?.name === 'AbortError'
  }

  function stopGeneration(showToast = true) {
    if (activeEventSource) {
      activeEventSource.close()
      activeEventSource = null
    }

    if (activeAbortController) {
      activeAbortController.abort()
      activeAbortController = null
    }

    running = false
    if (showToast) {
      toastMessage = 'Generation stopped.'
      toastVisible = true
    }
  }

  function applyStreamingChunk(node, chunk) {
    if (node === 'loremaster') {
      return {
        ...state,
        world_setting: `${state.world_setting ?? ''}${chunk}`,
        _lastNode: node,
      }
    }

    if (node === 'character_designer') {
      const characters = [...(state.characters ?? [])]
      if (characters.length === 0) {
        characters.push({ name: 'Companion 1', details: '' })
      }
      characters[0] = {
        ...characters[0],
        details: `${characters[0].details ?? ''}${chunk}`,
      }

      return {
        ...state,
        characters,
        _lastNode: node,
      }
    }

    if (node === 'editor') {
      return {
        ...state,
        critique_notes: `${state.critique_notes ?? ''}${chunk}`,
        _lastNode: node,
      }
    }

    return {
      ...state,
      _lastNode: node,
    }
  }

  async function saveExperimentation() {
    try {
      const res = await fetch('/api/experimentation/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(experimentationLive),
      })

      if (!res.ok) {
        throw new Error('Failed to save experimentation config')
      }

      experimentationSaved = JSON.parse(JSON.stringify(experimentationLive))
      toastMessage = '⚗️ Experimentation settings saved.'
      toastVisible = true
    } catch (error) {
      toastMessage = `Error saving experimentation: ${error.message}`
      toastVisible = true
    }
  }

  async function cancelExperimentation() {
    experimentationLive = JSON.parse(JSON.stringify(experimentationSaved))
    toastMessage = '⚗️ Experimentation settings reverted.'
    toastVisible = true
  }

  async function loadExperimentation() {
    try {
      const res = await fetch('/api/experimentation/load', { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        experimentationLive = data
        experimentationSaved = JSON.parse(JSON.stringify(data))
      }
    } catch (error) {
      console.warn('Could not load experimentation config:', error)
    }
  }

  async function handleRun({ rawIdea }) {
    if (!(await ensureApiReady())) {
      return
    }

    stopGeneration(false)
    currentRawIdea = rawIdea
    state = freshWorkflowState(rawIdea)
    meta = {}
    pendingSave = null
    savedRun = null
    restoredDraft = null
    outputStale = false
    filename = ''
    nextStage = null
    running = true
    activeAgentTab = 'loremaster'

    if (!auto) {
      await runManualStage('loremaster')
      return
    }

    if (streaming) {
      const params = new URLSearchParams({ 
        raw_idea: rawIdea, 
        auto_save: 'true',
        experimentation_config: JSON.stringify(experimentationLive)
      })
      const es = new EventSource(`/api/stream?${params}`)
      activeEventSource = es

      es.addEventListener('node-start', (e) => {
        const { node } = JSON.parse(e.data)
        state = { ...state, _lastNode: node }
      })

      es.addEventListener('node-token', (e) => {
        const { node, chunk } = JSON.parse(e.data)
        state = applyStreamingChunk(node, chunk)
      })

      es.addEventListener('node-complete', (e) => {
        const { node, output } = JSON.parse(e.data)
        state = { ...state, ...output, _lastNode: node }
        // Auto-switch to the stage that just completed for better UX
        if (node === 'loremaster' || node === 'character_designer' || node === 'editor') {
          activeAgentTab = node
        }
      })

      es.addEventListener('save-pending', (e) => {
        const data = JSON.parse(e.data)
        pendingSave = { raw_idea: rawIdea, state: data.state, meta: data.meta }
        void setSmartFilename(rawIdea)
        toastMessage = 'Save Assets is ready.'
        toastVisible = true
      })

      es.addEventListener('run-complete', (e) => {
        const data = JSON.parse(e.data)
        state = data.state
        meta = data.meta
        savedRun = { run_id: data.run_id, run_path: data.run_path, filename: data.filename }
        pendingSave = null
        toastMessage = `Auto-saved as ${data.filename}`
        toastVisible = true
        running = false
      })

      es.addEventListener('done', () => {
        es.close()
        activeEventSource = null
        running = false
      })

      es.onerror = () => {
        es.close()
        activeEventSource = null
        running = false
      }
    } else {
      const controller = new AbortController()
      activeAbortController = controller
      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ raw_idea: rawIdea, auto_save: true }),
          signal: controller.signal,
        })
        const data = await res.json()
        state = data.state
        meta = data.meta
        if (data.pending_save) {
          pendingSave = { raw_idea: rawIdea, state: data.state, meta: data.meta }
          await setSmartFilename(rawIdea)
          toastMessage = 'Save Assets is ready.'
          toastVisible = true
        } else {
          pendingSave = null
          savedRun = { run_id: data.run_id, run_path: data.run_path, filename: data.filename }
          toastMessage = `Auto-saved as ${data.filename}`
          toastVisible = true
        }
      } catch (error) {
        if (!isAbortError(error)) {
          toastMessage = 'Run failed. Please try again.'
          toastVisible = true
        }
      } finally {
        activeAbortController = null
        running = false
      }
    }
  }

  async function runManualStage(stage, continueOutput = false, directive = '', characterIndex = 0) {
    if (!(await ensureApiReady())) {
      return
    }

    activeAgentTab = stage
    state = { ...state, _lastNode: stage }
    running = true

    if (streaming) {
      await runManualStageStreaming(stage, continueOutput, directive, characterIndex)
      return
    }

    const controller = new AbortController()
    activeAbortController = controller
    try {
      const res = await fetch('/api/step', {
        signal: controller.signal,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_idea: currentRawIdea,
          state,
          stage,
          continue_output: continueOutput,
          directive,
          character_index: characterIndex,
          experimentation_config: experimentationLive,
        }),
      })

      if (!res.ok) {
        toastMessage = `Failed to run ${stageLabel(stage)}.`
        toastVisible = true
        return
      }

      const data = await res.json()
      state = { ...data.state, _lastNode: stage }
      meta = data.meta
      nextStage = data.next_stage ?? null
      
      // Auto-switch to the stage that just ran so output is visible
      activeAgentTab = stage

      if (data.save_pending) {
        pendingSave = { raw_idea: currentRawIdea, state: data.state, meta: data.meta }
        await setSmartFilename(currentRawIdea)
        toastMessage = 'Save Assets is ready.'
        toastVisible = true
      }
    } catch (error) {
      if (!isAbortError(error)) {
        toastMessage = `Failed to run ${stageLabel(stage)}.`
        toastVisible = true
      }
    } finally {
      activeAbortController = null
      running = false
    }
  }

  async function runManualStageStreaming(stage, continueOutput = false, directive = '', characterIndex = 0) {
    const controller = new AbortController()
    activeAbortController = controller
    try {
      const res = await fetch('/api/step-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_idea: currentRawIdea,
          state,
          stage,
          continue_output: continueOutput,
          directive,
          character_index: characterIndex,
          experimentation_config: experimentationLive,
        }),
        signal: controller.signal,
      })

      if (!res.ok || !res.body) {
        toastMessage = `Failed to stream ${stageLabel(stage)}.`
        toastVisible = true
        return
      }

      const decoder = new TextDecoder()
      const reader = res.body.getReader()
      let buffer = ''

      const processEvent = async (rawEvent) => {
        const lines = rawEvent.split('\n')
        let eventName = 'message'
        let data = ''
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventName = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            data += `${line.slice(5).trim()}\n`
          }
        }

        if (!data) return
        const payload = JSON.parse(data.trim())

        if (eventName === 'node-start') {
          state = { ...state, _lastNode: payload.node }
        } else if (eventName === 'node-token') {
          state = applyStreamingChunk(payload.node, payload.chunk)
        } else if (eventName === 'node-complete') {
          state = { ...state, ...payload.output, _lastNode: payload.node }
          // Auto-switch to the stage that just completed for better UX
          if (payload.node === 'loremaster' || payload.node === 'character_designer' || payload.node === 'editor') {
            activeAgentTab = payload.node
          }
        } else if (eventName === 'step-complete') {
          state = { ...payload.state, _lastNode: stage }
          meta = payload.meta ?? {}
          nextStage = payload.next_stage ?? null
          // Auto-switch after manual stage run
          activeAgentTab = stage
          if (payload.save_pending) {
            pendingSave = { raw_idea: currentRawIdea, state: payload.state, meta: payload.meta ?? {} }
            await setSmartFilename(currentRawIdea)
            toastMessage = 'Save Assets is ready.'
            toastVisible = true
          }
        } else if (eventName === 'done') {
          running = false
        }
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r/g, '')

        let splitIndex = buffer.indexOf('\n\n')
        while (splitIndex !== -1) {
          const rawEvent = buffer.slice(0, splitIndex).trim()
          buffer = buffer.slice(splitIndex + 2)
          if (rawEvent) {
            await processEvent(rawEvent)
          }
          splitIndex = buffer.indexOf('\n\n')
        }
      }
    } catch (error) {
      if (!isAbortError(error)) {
        toastMessage = `Failed to stream ${stageLabel(stage)}.`
        toastVisible = true
      }
    } finally {
      activeAbortController = null
      running = false
    }
  }

  async function handleModuleRun({ stage, directive, characterIndex = 0 }) {
    if (running) return
    if (!(await ensureApiReady())) return
    await runManualStage(stage, false, directive ?? '', characterIndex)
  }

  async function handleCharacterImageGenerate({ characterIndex, promptOverride = '' }) {
    if (!(await ensureApiReady())) {
      return
    }

    try {
      const res = await fetch('/api/character-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_idea: currentRawIdea,
          state,
          meta,
          save_pending: Boolean(pendingSave),
          character_index: characterIndex,
          prompt_override: promptOverride,
        }),
      })

      if (!res.ok) {
        const errorPayload = await res.json().catch(() => null)
        toastMessage = errorPayload?.detail || 'Failed to generate character image.'
        toastVisible = true
        return
      }

      const data = await res.json()
      state = { ...data.state }
      toastMessage = 'Character image generated.'
      toastVisible = true
    } catch {
      toastMessage = 'Failed to generate character image.'
      toastVisible = true
    }
  }

  async function handleNextStage() {
    if (!nextStage || running) return

    if (nextStage === 'save_assets') {
      activeAgentTab = 'save_assets'
      nextStage = null
      return
    }

    if (!(await ensureApiReady())) {
      return
    }

    await runManualStage(nextStage)
  }

  async function handleContinue() {
    if (running || !canContinueStage(activeAgentTab)) return
    if (!(await ensureApiReady())) return
    await runManualStage(activeAgentTab, true)
  }

  function handleStopGeneration() {
    stopGeneration(true)
    clearActiveHandles()
  }

  async function handleSave(fname) {
    if (!pendingSave) return
    if (!(await ensureApiReady())) return
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...pendingSave, filename: fname || generateDefaultFilename() }),
    })
    const data = await res.json()
    savedRun = data
    pendingSave = null
    toastMessage = `Saved as ${data.filename}`
    toastVisible = true
  }

  async function handleSuggestName() {
    if (!pendingSave) return
    if (!(await ensureApiReady())) return
    suggesting = true
    try {
      await setSmartFilename(pendingSave.raw_idea)
    } finally {
      suggesting = false
    }
  }

  function handleRandomName() {
    filename = generateDefaultFilename()
  }

  function handleVisibilityChange() {
    if (!draftSync) return
    if (document.visibilityState === 'hidden') {
      void draftSync.flushNow('visibility-hidden')
    }
  }

  function handleBeforeUnload() {
    const payload = draftPayload()
    try {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' })
      navigator.sendBeacon('/api/draft', blob)
    } catch {
      if (draftSync) {
        void draftSync.flushNow('before-unload')
      }
    }
  }

  onMount(async () => {
    try {
      const params = new URLSearchParams(window.location.search)
      perfDebugEnabled = params.get('perf') === '1'
    } catch {
      perfDebugEnabled = false
    }

    draftSync = new DraftSyncController({
      fetchImpl: fetch,
      getPayload: draftPayload,
      getChangeKey: draftChangeKey,
      intervalMs: 1000,
      debounceMs: 200,
      maxWaitMs: 2000,
      onStatusChange: handleDraftSyncStatus,
    })
    draftSync.start()
    setupPerfObserver()

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('beforeunload', handleBeforeUnload)

    await loadExperimentation()
    await restoreOnLaunch()
    restoreDone = true
    startLlmHeartbeat()
  })

  onDestroy(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    window.removeEventListener('beforeunload', handleBeforeUnload)

    if (draftSync) {
      void draftSync.flushNow('destroy')
      draftSync.stop()
      draftSync = null
    }

    if (perfObserver) {
      try {
        perfObserver.disconnect()
      } catch {
        // Ignore observer cleanup failures.
      }
      perfObserver = null
    }

    stopLlmHeartbeat()
  })

  $effect(() => {
    if (!restoreDone) return

    currentRawIdea
    state
    meta
    pendingSave

    if (!draftSync) return
    draftSync.markDirty()
  })
</script>

<TopBar bind:showStats bind:streaming bind:auto {meta} ongraph={openGraphTab} />

{#if !appServerConnected}
  <div class="llm-alert" role="alert" aria-live="assertive">
    Application server is down. Waiting for reconnect.
  </div>
{:else if !llmConnected}
  <div class="llm-alert" role="alert" aria-live="assertive">
    LLM connection is gone. Checking again in {llmCountdownDisplay} second{llmCountdownDisplay === 1 ? '' : 's'}.
  </div>
{/if}

{#if restoredDraft && !outputStale}
  <div class="restored-banner" role="status" aria-live="polite">
    <div class="restored-content">
      <span class="restored-label">📋 Restored Draft</span>
      <span class="restored-summary">
        Idea: <strong>{restoredDraft.raw_idea?.substring(0, 60)}{restoredDraft.raw_idea?.length > 60 ? '…' : ''}</strong>
      </span>
      <button 
        class="restored-clear-btn"
        onclick={() => {
          restoredDraft = null
          outputStale = false
          state = {}
          meta = {}
          currentRawIdea = ''
          pendingSave = null
          savedRun = null
          activeAgentTab = 'loremaster'
          toastMessage = 'Draft cleared. Ready for new run.'
          toastVisible = true
        }}
      >
        ✕ Clear & Start New
      </button>
    </div>
  </div>
{/if}

<Toast bind:visible={toastVisible} message={toastMessage} />

<div class="app-container">
  <ExperimentationPanel
    bind:live={experimentationLive}
    bind:saved={experimentationSaved}
    bind:isDirty={experimentationDirty}
    onSave={saveExperimentation}
    onCancel={cancelExperimentation}
  />

  <main>
    <RawIdeaForm {running} llmConnected={apiReady()} bind:rawIdea={currentRawIdea} onrun={handleRun} />

    {#if activeTab === 'agents'}
      <AgentPanel
        bind:workflowState={state}
        {running}
        bind:activeAgent={activeAgentTab}
        {pendingSave}
        {savedRun}
        bind:filename
        {suggesting}
        showNext={!auto}
        nextLabel={getNextButtonLabel()}
        nextDisabled={!nextStage || running || (!apiReady() && nextStage !== 'save_assets')}
        showStop={running}
        showContinue={activeAgentTab !== 'save_assets'}
        continueDisabled={!canContinueStage(activeAgentTab) || running || !apiReady()}
        llmConnected={apiReady()}
        onnext={handleNextStage}
        onstop={handleStopGeneration}
        oncontinue={handleContinue}
        onsave={handleSave}
        onsuggestname={handleSuggestName}
        onrandomname={handleRandomName}
        onrunmodule={handleModuleRun}
        oncharacterimage={handleCharacterImageGenerate}
      />
    {:else if activeTab === 'graph'}
      <div class="graph-section">
        <button class="back-btn" onclick={() => (activeTab = 'agents')}>← Back</button>
        {#if graphPanelLoad}
          {#await graphPanelLoad}
            <p class="loading">Loading graph…</p>
          {:then module}
            {@const GraphPanel = module.default}
            <GraphPanel />
          {:catch error}
            <p class="error">Failed to load graph: {error.message}</p>
          {/await}
        {:else}
          <p class="loading">Loading graph…</p>
        {/if}
      </div>
    {/if}
  </main>
</div>

<style>
  .app-container {
    display: flex;
    height: 100vh;
  }

  .llm-alert {
    max-width: 1080px;
    margin: 0.75rem auto 0;
    padding: 0.55rem 0.9rem;
    border: 1px solid #dc2626;
    border-left: 6px solid #dc2626;
    border-radius: 8px;
    background: #fef2f2;
    color: #991b1b;
    font-weight: 700;
  }

  main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    max-width: 1080px;
    margin: 0 auto;
    padding: 1rem;
    font-family: system-ui, sans-serif;
    width: 100%;
  }

  .graph-section {
    margin-top: 1rem;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.35rem 0.9rem;
    margin-bottom: 0.75rem;
    background: transparent;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #475569;
    font-size: 0.875rem;
    cursor: pointer;
  }

  .back-btn:hover {
    border-color: #94a3b8;
    color: #1e293b;
  }

  .loading,
  .error {
    color: #64748b;
    font-style: italic;
  }

  .error {
    color: #dc2626;
  }

  .restored-banner {
    max-width: 1080px;
    margin: 0.75rem auto 0;
    padding: 0.75rem 1rem;
    border: 1px solid #7c3aed;
    border-left: 6px solid #7c3aed;
    border-radius: 8px;
    background: #faf5ff;
    color: #5b21b6;
    font-size: 0.9rem;
  }

  .restored-content {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .restored-label {
    font-weight: 700;
    flex: 0 0 auto;
  }

  .restored-summary {
    flex: 1 1 auto;
    min-width: 200px;
    color: #6b21a8;
  }

  .restored-clear-btn {
    flex: 0 0 auto;
    padding: 0.35rem 0.8rem;
    background: #7c3aed;
    color: #fff;
    border: none;
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 600;
  }

  .restored-clear-btn:hover {
    background: #6d28d9;
  }
</style>
