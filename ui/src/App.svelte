<script>
  import { onDestroy, onMount } from 'svelte'
  import RawIdeaForm from './lib/RawIdeaForm.svelte'
  import AgentPanel from './lib/AgentPanel.svelte'
  import TopBar from './lib/TopBar.svelte'
  import Toast from './lib/Toast.svelte'
  import ExperimentationPanel from './lib/ExperimentationPanel.svelte'
  import StoryPage from './lib/StoryPage.svelte'
  import CharacterPage from './lib/CharacterPage.svelte'
  import GalleryPage from './lib/GalleryPage.svelte'
  import WorldStoryPage from './lib/WorldStoryPage.svelte'
  import LocationPage from './lib/LocationPage.svelte'
  import ObjectPage from './lib/ObjectPage.svelte'
  import PersonaPage from './lib/PersonaPage.svelte'
  import { DraftSyncController } from './lib/draftSync'
  import { PollingQueue } from './lib/pollingQueue'

  let state = $state({})
  let meta = $state({ elapsed_ms: 0 })
  let running = $state(false)
  let streaming = $state(true)
  let auto = $state(false)
  let showStats = $state(false)
  let activeTab = $state('world')
  let activeAgentTab = $state('loremaster')
  let graphPanelLoad = $state(null)
  let graphModalOpen = $state(false)
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
  let reviewPanelOpen = $state(true)
  let outputReview = $state(null)
  let reviewSummaryRequestId = 0
  let sdStyleOptions = $state(['balanced'])
  const FALLBACK_PERSONA_OPTIONS = [{
    id: 'blank',
    name: 'Blank',
    description: 'Unflavoured, direct prompts. No stylistic persona attached.',
    tags: ['neutral', 'direct', 'structured'],
    avatarUrl: '/api/personas/blank/avatar',
  }]
  let personaOptions = $state([...FALLBACK_PERSONA_OPTIONS])
  let imageCompare = $state(null)
  let showRestoreBanner = $state(true)
  let restoreBannerHovered = $state(false)
  let restoreBannerAutoDismissTimer = null
  let leftPanelCollapsed = $state(false)
  let storyPageState = $state({
    rawIdea: '',
    loading: false,
    error: '',
    story: null,
    savedName: '',
    storySetup: {
      protagonist: '',
      opening_preference: '',
      output_format: '',
      tone: '',
      length_target: '',
    },
    storyInstruction: '',
    generationQuality: '',
  })
  let characterPageState = $state({
    rawIdea: '',
    loading: false,
    error: '',
    workflowState: {
      raw_idea: '',
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

  const DEFAULT_EXPERIMENTATION = {
    general: {
      outputFormat: 'markdown',
      multilineReplies: true,
      persona: 'blank',
      addCopyTagOnDuplicate: true,
    },
    experimentation: {
      temperature: 0.7,
      topP: 0.9,
      topK: 40,
      repetitionPenalty: 1.1,
      maxLength: 512,
      contextSize: 2048,
      minP: 0,
      presencePenalty: 0,
      samplerSeed: -1,
    },
    sd: {
      style: 'balanced',
      endpoint: 'http://127.0.0.1:7860',
      steps: 30,
      width: 768,
      height: 768,
      cfgScale: 3,
      samplerName: 'DPM++ 2M',
      negativePrompt: '',
    },
  }

  // Experimentation state
  let experimentationLive = $state(JSON.parse(JSON.stringify(DEFAULT_EXPERIMENTATION)))
  let experimentationSaved = $state(JSON.parse(JSON.stringify(DEFAULT_EXPERIMENTATION)))
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

  function normalizeExperimentationConfig(config) {
    const incoming = config ?? {}
    const flatLooksOld = incoming && !incoming.experimentation && (incoming.temperature !== undefined || incoming.topP !== undefined)

    if (flatLooksOld) {
      return {
        general: {
          outputFormat: incoming.outputFormat ?? DEFAULT_EXPERIMENTATION.general.outputFormat,
          multilineReplies: incoming.multilineReplies ?? DEFAULT_EXPERIMENTATION.general.multilineReplies,
          persona: incoming.persona ?? DEFAULT_EXPERIMENTATION.general.persona,
          addCopyTagOnDuplicate:
            incoming.addCopyTagOnDuplicate ?? DEFAULT_EXPERIMENTATION.general.addCopyTagOnDuplicate,
        },
        experimentation: {
          temperature: incoming.temperature ?? DEFAULT_EXPERIMENTATION.experimentation.temperature,
          topP: incoming.topP ?? DEFAULT_EXPERIMENTATION.experimentation.topP,
          topK: incoming.topK ?? DEFAULT_EXPERIMENTATION.experimentation.topK,
          repetitionPenalty: incoming.repetitionPenalty ?? DEFAULT_EXPERIMENTATION.experimentation.repetitionPenalty,
          maxLength: incoming.maxLength ?? DEFAULT_EXPERIMENTATION.experimentation.maxLength,
          contextSize: incoming.contextSize ?? DEFAULT_EXPERIMENTATION.experimentation.contextSize,
          minP: incoming.minP ?? DEFAULT_EXPERIMENTATION.experimentation.minP,
          presencePenalty: incoming.presencePenalty ?? DEFAULT_EXPERIMENTATION.experimentation.presencePenalty,
          samplerSeed: incoming.samplerSeed ?? DEFAULT_EXPERIMENTATION.experimentation.samplerSeed,
        },
        sd: {
          ...DEFAULT_EXPERIMENTATION.sd,
          ...(incoming.sd ?? {}),
        },
      }
    }

    return {
      general: {
        ...DEFAULT_EXPERIMENTATION.general,
        ...(incoming.general ?? {}),
      },
      experimentation: {
        ...DEFAULT_EXPERIMENTATION.experimentation,
        ...(incoming.experimentation ?? {}),
      },
      sd: {
        ...DEFAULT_EXPERIMENTATION.sd,
        ...(incoming.sd ?? {}),
      },
    }
  }

  const selectedPersona = $derived.by(() => {
    const selectedId = experimentationLive?.general?.persona || 'blank'
    const found = personaOptions.find((persona) => persona.id === selectedId)
    return found || personaOptions[0] || null
  })

  const selectedPersonaTagList = $derived.by(() => {
    if (!selectedPersona?.tags || !Array.isArray(selectedPersona.tags)) return []
    return selectedPersona.tags.slice(0, 8)
  })

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
    const resolvedNextStage = getResolvedNextStage()
    if (!resolvedNextStage) return 'Next'
    return `Next: ${stageLabel(resolvedNextStage)}`
  }

  function hasNonEmptyStageOutput(stage) {
    const output = getStageOutputFromState(state, stage)
    return Boolean(output?.trim())
  }

  function getFallbackNextStage(stage) {
    if (stage === 'loremaster') return 'character_designer'
    if (stage === 'character_designer') return 'editor'
    if (stage === 'editor') return 'save_assets'
    return null
  }

  function getResolvedNextStage() {
    if (nextStage) return nextStage
    if (running) return null
    if (!hasNonEmptyStageOutput(activeAgentTab)) return null
    return getFallbackNextStage(activeAgentTab)
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

  function normalizeMeta(nextMeta, options = {}) {
    const { resetElapsed = false } = options
    const normalized = { ...(nextMeta ?? {}) }
    const elapsed = resetElapsed ? 0 : Number(normalized.elapsed_ms ?? 0)
    normalized.elapsed_ms = Number.isFinite(elapsed) ? elapsed : 0
    return normalized
  }

  function getStageOutputFromState(localState, stage, characterIndex = 0) {
    if (!localState) return ''
    if (stage === 'loremaster') return localState.world_setting ?? ''
    if (stage === 'editor') return localState.critique_notes ?? ''
    if (stage === 'character_designer') {
      const chars = localState.characters ?? []
      return chars[characterIndex]?.details ?? ''
    }
    return ''
  }

  function setStageOutputInState(localState, stage, value, characterIndex = 0) {
    if (!localState) return localState
    if (stage === 'loremaster') {
      return { ...localState, world_setting: value }
    }
    if (stage === 'editor') {
      return { ...localState, critique_notes: value }
    }
    if (stage === 'character_designer') {
      const chars = [...(localState.characters ?? [])]
      while (chars.length <= characterIndex) {
        chars.push({ name: `Companion ${chars.length + 1}`, details: '' })
      }
      chars[characterIndex] = {
        ...chars[characterIndex],
        details: value,
      }
      return { ...localState, characters: chars }
    }
    return localState
  }

  async function generateReviewSummaryWithLlm(stage, originalText, revisedText) {
    if (!revisedText?.trim()) {
      return '- Modified: Waiting for generated output.\n- Added: Waiting for generated output.\n- Removed: Waiting for generated output.'
    }

    const res = await fetch('/api/review-summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stage,
        original: originalText,
        revised: revisedText,
        persona_id: experimentationLive.general?.persona || 'blank',
      }),
    })

    if (!res.ok) {
      throw new Error('Failed to generate summary')
    }

    const data = await res.json()
    return data.summary ?? '- Modified: Unable to summarize.\n- Added: Unable to summarize.\n- Removed: Unable to summarize.'
  }

  function startReview(stage, characterIndex = 0) {
    const original = getStageOutputFromState(state, stage, characterIndex)
    outputReview = {
      stage,
      characterIndex,
      original,
      wip: '',
      summary: '- Modified: Waiting for first generated tokens.\n- Added: Waiting for first generated tokens.\n- Removed: Waiting for first generated tokens.',
      firstSummaryGenerated: false,
      summaryLoading: false,
    }
  }

  function clearReview() {
    reviewSummaryRequestId += 1
    outputReview = null
  }

  function updateReviewWip(nextWip) {
    if (!outputReview) return
    outputReview = {
      ...outputReview,
      wip: nextWip,
    }
  }

  async function requestReviewSummary(force = false) {
    if (!outputReview) return

    if (!force && outputReview.firstSummaryGenerated) return

    const requestId = ++reviewSummaryRequestId
    outputReview = {
      ...outputReview,
      summaryLoading: true,
    }

    try {
      const summary = await generateReviewSummaryWithLlm(outputReview.stage, outputReview.original, outputReview.wip)
      if (!outputReview || reviewSummaryRequestId !== requestId) return
      outputReview = {
        ...outputReview,
        summary,
        firstSummaryGenerated: true,
        summaryLoading: false,
      }
    } catch {
      if (!outputReview || reviewSummaryRequestId !== requestId) return
      outputReview = {
        ...outputReview,
        summary: '- Modified: Unable to generate summary right now.\n- Added: Try again once generation settles.\n- Removed: You can use Regenerate Summary to retry.',
        firstSummaryGenerated: outputReview.firstSummaryGenerated,
        summaryLoading: false,
      }
    }
  }

  function regenerateReviewSummary() {
    void requestReviewSummary(true)
  }

  function handleApproveReview() {
    if (!outputReview) return
    state = setStageOutputInState(state, outputReview.stage, outputReview.wip, outputReview.characterIndex)
    clearReview()
  }

  function handleRejectReview() {
    clearReview()
  }

  function buildStateWithReviewOutput(baseState, stage, characterIndex = 0) {
    if (!outputReview || outputReview.stage !== stage) return baseState
    const candidate = outputReview.wip || outputReview.original
    return setStageOutputInState(baseState, stage, candidate, characterIndex)
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
    meta = normalizeMeta(payload.meta, { resetElapsed: true })
    pendingSave = payload.save_pending ? { raw_idea: currentRawIdea, state, meta: normalizeMeta(payload.meta, { resetElapsed: true }) } : null
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
    showRestoreBanner = true
    restoreBannerHovered = false
    startRestoreBannerAutoDismiss()
    return true
  }

  function applyRestoredStoryDraft(payload) {
    if (!payload?.state?.story_artifact) return false
    const restoredSetup = payload.state?.story_setup && typeof payload.state.story_setup === 'object'
      ? payload.state.story_setup
      : {}
    storyPageState = {
      ...storyPageState,
      rawIdea: payload.raw_idea ?? '',
      loading: false,
      error: '',
      story: payload.state.story_artifact,
      savedName: '',
      storySetup: {
        protagonist: '',
        opening_preference: '',
        output_format: '',
        tone: '',
        length_target: '',
        ...restoredSetup,
      },
      storyInstruction: payload.state?.story_instruction ?? '',
      generationQuality: payload.meta?.story_generation_quality ?? '',
    }
    return true
  }

  function applyRestoredCharacterDraft(payload) {
    if (!payload?.state) return false
    characterPageState = {
      ...characterPageState,
      rawIdea: payload.raw_idea ?? '',
      loading: false,
      error: '',
      workflowState: payload.state,
      activeAgent: 'character_designer',
      pendingSave: null,
      savedRun: null,
      savedName: '',
    }
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

  function startRestoreBannerAutoDismiss() {
    if (restoreBannerAutoDismissTimer) {
      clearTimeout(restoreBannerAutoDismissTimer)
    }
    restoreBannerAutoDismissTimer = setTimeout(() => {
      if (!restoreBannerHovered) {
        showRestoreBanner = false
      }
      restoreBannerAutoDismissTimer = null
    }, 8000)
  }

  function clearRestoreBannerAutoDismiss() {
    if (restoreBannerAutoDismissTimer) {
      clearTimeout(restoreBannerAutoDismissTimer)
      restoreBannerAutoDismissTimer = null
    }
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

    const draftMeta = { ...(meta ?? {}) }
    delete draftMeta.elapsed_ms

    return {
      raw_idea: currentRawIdea,
      state,
      meta: draftMeta,
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
      if (data?.draft) {
        applyRestoredPayload(data.draft, 'draft')
      }
      if (data?.story_draft) {
        applyRestoredStoryDraft(data.story_draft)
      }
      if (data?.character_draft) {
        applyRestoredCharacterDraft(data.character_draft)
      }
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

  function openGraphModal() {
    if (!graphPanelLoad) {
      graphPanelLoad = import('./lib/GraphPanel.svelte')
    }
    graphModalOpen = true
  }

  function closeGraphModal() {
    graphModalOpen = false
  }

  function selectTopTab(tabId) {
    activeTab = tabId
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

  function resetWorldPageState() {
    clearRestoreBannerAutoDismiss()
    stopGeneration(false)
    currentRawIdea = ''
    state = freshWorkflowState('')
    meta = normalizeMeta(null)
    pendingSave = null
    savedRun = null
    filename = ''
    nextStage = null
    activeAgentTab = 'loremaster'
    restoredDraft = null
    outputStale = false
    showRestoreBanner = false
    restoreBannerHovered = false
    clearReview()
  }

  function handleResetWorldPage() {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm('Reset World page and clear its temporary draft?')
      if (!confirmed) return
    }
    resetWorldPageState()
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
        const normalized = normalizeExperimentationConfig(data)
        experimentationLive = normalized
        experimentationSaved = JSON.parse(JSON.stringify(normalized))
      }
    } catch (error) {
      console.warn('Could not load experimentation config:', error)
    }
  }

  async function loadSdStyles() {
    try {
      const res = await fetch('/api/sd-styles', { cache: 'no-store' })
      if (!res.ok) return
      const data = await res.json()
      const styles = Array.isArray(data?.styles) && data.styles.length > 0 ? data.styles : ['balanced']
      sdStyleOptions = styles
      const defaultStyle = data?.default_style || styles[0]
      if (!experimentationLive.sd?.style || !styles.includes(experimentationLive.sd.style)) {
        experimentationLive = {
          ...experimentationLive,
          sd: {
            ...experimentationLive.sd,
            style: defaultStyle,
          },
        }
      }
    } catch {
      // Keep fallback styles.
    }
  }

  async function loadPersonas() {
    try {
      const [listRes, templateRes] = await Promise.all([
        fetch('/api/personas', { cache: 'no-store' }),
        fetch('/api/personas/template', { cache: 'no-store' }),
      ])

      const data = listRes.ok ? await listRes.json() : []
      const list = Array.isArray(data) ? data : []
      const template = templateRes.ok ? await templateRes.json() : null

      if (template?.id) {
        const rest = list.filter((p) => p.id !== template.id)
        rest.sort((a, b) => {
          const aFav = a?.favorite ? 1 : 0
          const bFav = b?.favorite ? 1 : 0
          if (aFav !== bFav) return bFav - aFav
          return String(a?.name || '').localeCompare(String(b?.name || ''))
        })
        personaOptions = [template, ...rest]
      } else {
        personaOptions = list.length > 0 ? list : [...FALLBACK_PERSONA_OPTIONS]
      }

      const selectedId = experimentationLive?.general?.persona || 'blank'
      if (!personaOptions.some((p) => p.id === selectedId)) {
        experimentationLive = {
          ...experimentationLive,
          general: {
            ...experimentationLive.general,
            persona: personaOptions[0].id,
          },
        }
      }
    } catch {
      personaOptions = [...FALLBACK_PERSONA_OPTIONS]
    }
  }

  async function handlePersonaChanged(event) {
    const nextPersona = event?.currentTarget?.value || 'blank'
    experimentationLive = {
      ...experimentationLive,
      general: {
        ...experimentationLive.general,
        persona: nextPersona,
      },
    }
    await saveExperimentation()
  }

  async function handleRun({ rawIdea }) {
    if (!(await ensureApiReady())) {
      return
    }

    stopGeneration(false)
    clearRestoreBannerAutoDismiss()
    currentRawIdea = rawIdea
    state = freshWorkflowState(rawIdea)
    meta = normalizeMeta(null)
    pendingSave = null
    savedRun = null
    restoredDraft = null
    outputStale = false
    filename = ''
    nextStage = null
    showRestoreBanner = true
    restoreBannerHovered = false
    clearReview()
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
        experimentation_config: JSON.stringify(experimentationLive.experimentation),
        persona_id: experimentationLive.general?.persona || 'blank',
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
        meta = normalizeMeta(data.meta)
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
          body: JSON.stringify({
            raw_idea: rawIdea,
            auto_save: true,
            persona_id: experimentationLive.general?.persona || 'blank',
          }),
          signal: controller.signal,
        })
        const data = await res.json()
        state = data.state
        meta = normalizeMeta(data.meta)
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

  async function runManualStage(stage, continueOutput = false, directive = '', characterIndex = 0, options = {}) {
    const { captureToReview = false, requestStateOverride = null } = options
    if (!(await ensureApiReady())) {
      return
    }

    activeAgentTab = stage
    state = { ...state, _lastNode: stage }
    running = true

    if (streaming) {
      await runManualStageStreaming(stage, continueOutput, directive, characterIndex, options)
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
          state: requestStateOverride ?? state,
          stage,
          continue_output: continueOutput,
          directive,
          character_index: characterIndex,
          experimentation_config: experimentationLive.experimentation,
          persona_id: experimentationLive.general?.persona || 'blank',
        }),
      })

      if (!res.ok) {
        toastMessage = `Failed to run ${stageLabel(stage)}.`
        toastVisible = true
        return
      }

      const data = await res.json()
      if (captureToReview && outputReview && outputReview.stage === stage) {
        const nextWip = getStageOutputFromState(data.state, stage, characterIndex)
        updateReviewWip(nextWip)
        const preserved = setStageOutputInState(data.state, stage, outputReview.original, characterIndex)
        state = { ...preserved, _lastNode: stage }
        if (!outputReview.firstSummaryGenerated && nextWip?.trim()) {
          void requestReviewSummary(false)
        }
      } else {
        state = { ...data.state, _lastNode: stage }
      }
      meta = normalizeMeta(data.meta)
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

  async function runManualStageStreaming(stage, continueOutput = false, directive = '', characterIndex = 0, options = {}) {
    const { captureToReview = false, requestStateOverride = null } = options
    const controller = new AbortController()
    activeAbortController = controller
    try {
      const res = await fetch('/api/step-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_idea: currentRawIdea,
          state: requestStateOverride ?? state,
          stage,
          continue_output: continueOutput,
          directive,
          character_index: characterIndex,
          experimentation_config: experimentationLive.experimentation,
          persona_id: experimentationLive.general?.persona || 'blank',
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
          if (captureToReview && payload.node === stage && outputReview && outputReview.stage === stage) {
            updateReviewWip(`${outputReview.wip ?? ''}${payload.chunk ?? ''}`)
          } else {
            state = applyStreamingChunk(payload.node, payload.chunk)
          }
        } else if (eventName === 'node-complete') {
          if (captureToReview && payload.node === stage && outputReview && outputReview.stage === stage) {
            const nextWip = getStageOutputFromState(payload.output ?? {}, stage, characterIndex)
            if (nextWip) {
              updateReviewWip(nextWip)
            }
          } else {
            state = { ...state, ...payload.output, _lastNode: payload.node }
          }
          // Auto-switch to the stage that just completed for better UX
          if (payload.node === 'loremaster' || payload.node === 'character_designer' || payload.node === 'editor') {
            activeAgentTab = payload.node
          }
        } else if (eventName === 'step-complete') {
          if (captureToReview && outputReview && outputReview.stage === stage) {
            const nextWip = getStageOutputFromState(payload.state, stage, characterIndex)
            updateReviewWip(nextWip)
            const preserved = setStageOutputInState(payload.state, stage, outputReview.original, characterIndex)
            state = { ...preserved, _lastNode: stage }
            if (!outputReview.firstSummaryGenerated && nextWip?.trim()) {
              void requestReviewSummary(false)
            }
          } else {
            state = { ...payload.state, _lastNode: stage }
          }
          meta = normalizeMeta(payload.meta)
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

    if (stage === 'save_assets') {
      await runManualStage(stage, false, directive ?? '', characterIndex)
      return
    }

    if (!outputReview || outputReview.stage !== stage || outputReview.characterIndex !== characterIndex) {
      startReview(stage, characterIndex)
    }

    const overrideState = buildStateWithReviewOutput(state, stage, characterIndex)
    await runManualStage(stage, false, directive ?? '', characterIndex, {
      captureToReview: true,
      requestStateOverride: overrideState,
    })
  }

  async function handleCharacterImageGenerate({ characterIndex, promptOverride = '', mode = 'full' }) {
    if (!(await ensureApiReady())) {
      return
    }

    const previousCharacter = state?.characters?.[characterIndex]
    const previousImage = previousCharacter?.image_data || previousCharacter?.image_path || ''

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
          mode,
          style: experimentationLive.sd?.style,
          sd_config: experimentationLive.sd,
          persona_id: experimentationLive.general?.persona || 'blank',
        }),
      })

      if (!res.ok) {
        const errorPayload = await res.json().catch(() => null)
        toastMessage = errorPayload?.detail || 'Failed to generate character image.'
        toastVisible = true
        return
      }

      const data = await res.json()
      const nextCharacter = data?.state?.characters?.[characterIndex]
      const nextImage = nextCharacter?.image_data || nextCharacter?.image_path || ''

      if ((mode === 'image' || mode === 'full') && previousImage && nextImage && previousImage !== nextImage) {
        imageCompare = {
          characterIndex,
          oldCharacter: previousCharacter,
          newCharacter: nextCharacter,
          nextState: data.state,
        }
        toastMessage = 'Choose which image to keep.'
        toastVisible = true
        return
      }

      state = { ...data.state }
      if (mode === 'prompt') {
        toastMessage = 'Image prompt regenerated.'
      } else if (mode === 'image') {
        toastMessage = 'Character image generated from prompt.'
      } else {
        toastMessage = 'Character image generated.'
      }
      toastVisible = true
    } catch {
      toastMessage = 'Failed to generate character image.'
      toastVisible = true
    }
  }

  function keepNewImage() {
    if (!imageCompare) return
    state = { ...imageCompare.nextState }
    imageCompare = null
    toastMessage = 'Kept the new image.'
    toastVisible = true
  }

  function keepOldImage() {
    imageCompare = null
    toastMessage = 'Kept the previous image.'
    toastVisible = true
  }

  async function handleNextStage() {
    const resolvedNextStage = getResolvedNextStage()
    if (!resolvedNextStage || running) return

    if (resolvedNextStage === 'save_assets') {
      activeAgentTab = 'save_assets'
      nextStage = null
      return
    }

    if (!(await ensureApiReady())) {
      return
    }

    await runManualStage(resolvedNextStage)
  }

  async function handleContinue() {
    if (running || !canContinueStage(activeAgentTab)) return
    if (!(await ensureApiReady())) return

    if (outputReview && outputReview.stage === activeAgentTab) {
      const overrideState = buildStateWithReviewOutput(state, activeAgentTab, outputReview.characterIndex)
      await runManualStage(activeAgentTab, true, '', outputReview.characterIndex, {
        captureToReview: true,
        requestStateOverride: overrideState,
      })
      return
    }

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
    await loadPersonas()
    await loadSdStyles()
    await restoreOnLaunch()
    restoreDone = true
    startLlmHeartbeat()
  })

  onDestroy(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    window.removeEventListener('beforeunload', handleBeforeUnload)

    clearRestoreBannerAutoDismiss()

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

<TopBar {meta} {activeTab} {showStats} onselecttab={selectTopTab} />

{#if restoredDraft && !outputStale && showRestoreBanner}
  <div 
    class="restored-card" 
    role="status" 
    aria-live="polite"
    onmouseover={() => { restoreBannerHovered = true }}
    onmouseleave={() => { restoreBannerHovered = false }}
  >
    <div class="restored-card-header">
      <span class="restored-card-label">📋 Restored Draft</span>
    </div>
    <div class="restored-card-idea">
      <strong>{restoredDraft.raw_idea?.substring(0, 80)}{restoredDraft.raw_idea?.length > 80 ? '…' : ''}</strong>
    </div>
    <div class="restored-card-actions">
      <button 
        class="restored-card-action continue-btn"
        title="Continue with restored draft"
        onclick={() => {
          clearRestoreBannerAutoDismiss()
          showRestoreBanner = false
        }}
      >
        ▶
      </button>
      <button 
        class="restored-card-action clear-btn"
        title="Clear draft and start new"
        onclick={() => {
          resetWorldPageState()
          toastMessage = 'Draft cleared. Ready for new run.'
          toastVisible = true
        }}
      >
        🗑
      </button>
    </div>
  </div>
{/if}

{#if imageCompare}
  <div class="image-compare-modal" role="dialog" aria-modal="true" aria-label="Choose image version">
    <div class="image-compare-card">
      <h3>Choose Image Version</h3>
      <div class="image-compare-grid">
        <div class="compare-item">
          <p>Current</p>
          {#if imageCompare.oldCharacter?.image_data || imageCompare.oldCharacter?.image_path}
            <img src={imageCompare.oldCharacter.image_data || imageCompare.oldCharacter.image_path} alt="Current character portrait" />
          {/if}
          <button class="cancel-btn" onclick={keepOldImage}>Keep Current</button>
        </div>
        <div class="compare-item">
          <p>New</p>
          {#if imageCompare.newCharacter?.image_data || imageCompare.newCharacter?.image_path}
            <img src={imageCompare.newCharacter.image_data || imageCompare.newCharacter.image_path} alt="Newly generated character portrait" />
          {/if}
          <button class="confirm-btn" onclick={keepNewImage}>Keep New</button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if graphModalOpen}
  <div
    class="graph-modal"
    role="dialog"
    aria-modal="true"
    aria-label="Workflow graph"
    tabindex="-1"
    onclick={(event) => {
      if (event.target === event.currentTarget) {
        closeGraphModal()
      }
    }}
    onkeydown={(event) => {
      if (event.key === 'Escape') {
        closeGraphModal()
      }
    }}
  >
    <div class="graph-modal-card">
      <div class="graph-modal-header">
        <h3>Workflow Graph</h3>
        <button class="graph-modal-close" aria-label="Close workflow graph" onclick={closeGraphModal}>✕</button>
      </div>
      <div class="graph-modal-body">
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
    </div>
  </div>
{/if}

<Toast bind:visible={toastVisible} message={toastMessage} />

<div class="app-container">
  <div class="left-panel-shell" class:collapsed={leftPanelCollapsed}>
    <ExperimentationPanel
      bind:live={experimentationLive}
      bind:saved={experimentationSaved}
      bind:isDirty={experimentationDirty}
      bind:auto
      bind:streaming
      bind:showStats
      collapsed={leftPanelCollapsed}
      sdStyleOptions={sdStyleOptions}
      onSave={saveExperimentation}
      onCancel={cancelExperimentation}
      onSaveSd={saveExperimentation}
      onCancelSd={cancelExperimentation}
      onOpenGraph={openGraphModal}
      onToggleCollapse={() => (leftPanelCollapsed = true)}
    />
  </div>
  {#if leftPanelCollapsed}
    <button
      class="left-panel-edge-toggle"
      type="button"
      title="Expand settings panel"
      aria-label="Expand settings panel"
      onclick={() => (leftPanelCollapsed = false)}
    >
      ⟩
    </button>
  {/if}

  <div class="workspace-area">
    {#if !appServerConnected}
      <div class="llm-alert" role="alert" aria-live="assertive">
        Application server is down. Waiting for reconnect.
      </div>
    {:else if !llmConnected}
      <div class="llm-alert" role="alert" aria-live="assertive">
        LLM connection is gone. Checking again in {llmCountdownDisplay} second{llmCountdownDisplay === 1 ? '' : 's'}.
      </div>
    {/if}

    <main>
    {#if activeTab === 'world'}
      <div class="page-header">
        <h2>World Builder</h2>
        <button class="page-reset-btn" type="button" onclick={handleResetWorldPage}>Reset</button>
      </div>
      <RawIdeaForm
        {running}
        llmConnected={apiReady()}
        bind:rawIdea={currentRawIdea}
        onrun={handleRun}
        onstop={handleStopGeneration}
      />
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
          nextDisabled={!getResolvedNextStage() || running || (!apiReady() && getResolvedNextStage() !== 'save_assets') || (outputReview && outputReview.stage === activeAgentTab)}
        showContinue={activeAgentTab !== 'save_assets'}
        continueDisabled={!canContinueStage(activeAgentTab) || running || !apiReady()}
        llmConnected={apiReady()}
        reviewState={outputReview}
        reviewPanelOpen={reviewPanelOpen}
        onnext={handleNextStage}
        oncontinue={handleContinue}
        onsave={handleSave}
        onsuggestname={handleSuggestName}
        onrandomname={handleRandomName}
        onrunmodule={handleModuleRun}
        oncharacterimage={handleCharacterImageGenerate}
        onapprovereview={handleApproveReview}
        onrejectreview={handleRejectReview}
        oneditreview={(value) => updateReviewWip(value)}
        onregeneratesummary={regenerateReviewSummary}
        ontogglereviewpanel={() => (reviewPanelOpen = !reviewPanelOpen)}
      />
    {:else if activeTab === 'story'}
      <StoryPage
        llmConnected={apiReady()}
        personaId={experimentationLive.general?.persona || 'blank'}
        experimentationConfig={experimentationLive.experimentation}
        bind:rawIdea={storyPageState.rawIdea}
        bind:loading={storyPageState.loading}
        bind:error={storyPageState.error}
        bind:story={storyPageState.story}
        bind:savedName={storyPageState.savedName}
        bind:storySetup={storyPageState.storySetup}
        bind:storyInstruction={storyPageState.storyInstruction}
        bind:generationQuality={storyPageState.generationQuality}
      />
    {:else if activeTab === 'character'}
      <CharacterPage
        llmConnected={apiReady()}
        personaId={experimentationLive.general?.persona || 'blank'}
        experimentationConfig={experimentationLive.experimentation}
        bind:rawIdea={characterPageState.rawIdea}
        bind:loading={characterPageState.loading}
        bind:error={characterPageState.error}
        bind:workflowState={characterPageState.workflowState}
        bind:activeAgent={characterPageState.activeAgent}
        bind:pendingSave={characterPageState.pendingSave}
        bind:savedRun={characterPageState.savedRun}
        bind:savedName={characterPageState.savedName}
      />
    {:else if activeTab === 'gallery'}
      <GalleryPage />
    {:else if activeTab === 'personas'}
      <PersonaPage
        onpersonaschanged={loadPersonas}
        addCopyTagOnDuplicate={Boolean(experimentationLive?.general?.addCopyTagOnDuplicate)}
      />
    {:else if activeTab === 'world-story'}
      <WorldStoryPage />
    {/if}
    </main>

    <aside class="persona-side-panel">
      <div class="persona-side-header">Agent Persona</div>
      <div class="persona-side-body">
        <div class="control-group">
          <label for="persona-select">Persona</label>
          <select id="persona-select" value={experimentationLive.general?.persona || 'blank'} onchange={handlePersonaChanged}>
            {#each personaOptions as persona}
              <option value={persona.id}>{persona.name}</option>
            {/each}
          </select>
        </div>

        {#if selectedPersona}
          <div class="persona-avatar-wrap">
            {#if selectedPersona.avatarUrl}
              <img class="persona-avatar" src={selectedPersona.avatarUrl} alt={`${selectedPersona.name} avatar`} width="256" height="256" />
            {:else}
              <div class="persona-avatar persona-avatar-placeholder">{selectedPersona.name?.slice(0, 1) || '?'}</div>
            {/if}
          </div>
          <div class="persona-description">{selectedPersona.description}</div>
          <div class="persona-tags">
            {#if selectedPersonaTagList.length > 0}
              {#each selectedPersonaTagList as tag}
                <span class="persona-tag-badge">{tag}</span>
              {/each}
            {:else}
              <span class="persona-tag-empty">No tags</span>
            {/if}
          </div>
        {:else}
          <p class="persona-empty">No persona options available.</p>
        {/if}
      </div>
    </aside>
  </div>
</div>

<style>
  .app-container {
    display: flex;
    height: 100vh;
    position: relative;
  }

  .left-panel-shell {
    width: 300px;
    flex: 0 0 auto;
    transition: width 0.2s ease;
    overflow: hidden;
  }

  .left-panel-shell.collapsed {
    width: 0;
  }

  .left-panel-edge-toggle {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translate(-35%, -50%);
    border: 1px solid #334155;
    background: #0f172a;
    color: #e5e7eb;
    width: 1.95rem;
    height: 3rem;
    border-radius: 999px;
    cursor: pointer;
    z-index: 35;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.25);
  }

  .left-panel-edge-toggle:hover {
    border-color: #60a5fa;
    color: #93c5fd;
  }

  .workspace-area {
    flex: 1;
    min-width: 0;
    display: flex;
    position: relative;
  }

  @media (max-width: 980px) {
    .left-panel-shell {
      width: 260px;
    }
  }

  .llm-alert {
    position: absolute;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    width: min(1080px, calc(100% - 2rem));
    padding: 0.5rem 0.9rem;
    border: 1px solid #dc2626;
    border-left: 4px solid #dc2626;
    border-radius: 8px;
    background: rgba(254, 242, 242, 0.88);
    color: #991b1b;
    font-weight: 700;
    backdrop-filter: blur(2px);
    pointer-events: none;
  }

  main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 1rem;
    font-family: system-ui, sans-serif;
    min-width: 0;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.65rem;
  }

  .page-header h2 {
    margin: 0;
    font-size: 1.2rem;
    color: #0f172a;
  }

  .page-reset-btn {
    border: 1px solid #94a3b8;
    background: #fff;
    color: #334155;
    border-radius: 6px;
    padding: 0.4rem 0.75rem;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
  }

  .page-reset-btn:hover {
    border-color: #64748b;
    background: #f8fafc;
  }

  .persona-side-panel {
    width: 280px;
    border-left: 1px solid #e2e8f0;
    background: #f8fafc;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .persona-side-header {
    padding: 0.75rem 0.9rem;
    border-bottom: 1px solid #e2e8f0;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #475569;
    background: #f1f5f9;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .persona-side-body {
    padding: 0.8rem;
    display: grid;
    gap: 0.55rem;
  }

  .persona-side-body .control-group {
    display: grid;
    gap: 0.3rem;
  }

  .persona-side-body .control-group label {
    font-size: 0.78rem;
    color: #334155;
  }

  .persona-side-body select {
    background: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 0.38rem 0.5rem;
    font-size: 0.82rem;
  }

  .persona-avatar-wrap {
    display: flex;
    justify-content: center;
  }

  .persona-avatar {
    width: 256px;
    height: 256px;
    max-width: 100%;
    border-radius: 10px;
    border: 1px solid #cbd5e1;
    object-fit: cover;
    background: #ffffff;
  }

  .persona-avatar-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.3rem;
    font-weight: 700;
    color: #64748b;
    background: #e2e8f0;
  }

  .persona-description {
    font-size: 0.79rem;
    color: #334155;
    line-height: 1.35;
  }

  .persona-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    border-top: 1px dashed #cbd5e1;
    padding-top: 0.4rem;
  }

  .persona-tag-badge {
    display: inline-block;
    font-size: 0.7rem;
    line-height: 1.1;
    color: #0f766e;
    border: 1px solid #99f6e4;
    background: #ecfeff;
    padding: 0.18rem 0.45rem;
    border-radius: 999px;
  }

  .persona-tag-empty {
    font-size: 0.72rem;
    color: #64748b;
    font-style: italic;
  }

  .persona-empty {
    margin: 0;
    font-size: 0.8rem;
    color: #64748b;
    font-style: italic;
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
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    width: 320px;
    border: 1px solid #7c3aed;
    border-radius: 12px;
    background: #faf5ff;
    color: #5b21b6;
    font-size: 0.9rem;
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem;
    z-index: 40;
    animation: slideInUp 0.3s ease-out;
  }

  @keyframes slideInUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .restored-card {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    width: 320px;
    border: 1px solid #7c3aed;
    border-radius: 12px;
    background: #faf5ff;
    color: #5b21b6;
    font-size: 0.9rem;
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem;
    z-index: 40;
    animation: slideInUp 0.3s ease-out;
  }

  .restored-card-header {
    font-weight: 700;
    font-size: 0.95rem;
  }

  .restored-card-idea {
    font-size: 0.85rem;
    color: #6b21a8;
    line-height: 1.4;
    word-break: break-word;
  }

  .restored-card-actions {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
  }

  .restored-card-action {
    padding: 0.4rem 0.6rem;
    border: 1px solid #d8b4fe;
    border-radius: 6px;
    background: transparent;
    color: #7c3aed;
    cursor: pointer;
    font-size: 1rem;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .restored-card-action:hover {
    background: #f3e8ff;
    border-color: #7c3aed;
    transform: scale(1.05);
  }

  .restored-card-action.continue-btn {
    background: #7c3aed;
    color: #fff;
    border-color: #7c3aed;
    font-size: 0.9rem;
    font-weight: 600;
  }

  .restored-card-action.continue-btn:hover {
    background: #6d28d9;
    border-color: #6d28d9;
    transform: scale(1.08);
  }

  .restored-card-action.clear-btn {
    background: #dc2626;
    color: #fff;
    border-color: #dc2626;
    font-weight: 600;
  }

  .restored-card-action.clear-btn:hover {
    background: #b91c1c;
    border-color: #b91c1c;
    transform: scale(1.08);
  }

  .image-compare-modal {
    position: fixed;
    inset: 0;
    background: rgba(2, 6, 23, 0.72);
    display: grid;
    place-items: center;
    z-index: 50;
    padding: 1rem;
  }

  .graph-modal {
    position: fixed;
    inset: 0;
    background: rgba(2, 6, 23, 0.72);
    display: grid;
    place-items: center;
    z-index: 55;
    padding: 1rem;
  }

  .graph-modal-card {
    width: min(1100px, 100%);
    max-height: min(90vh, 900px);
    background: #fff;
    border-radius: 14px;
    border: 1px solid #cbd5e1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .graph-modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
    padding: 0.8rem 1rem;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
  }

  .graph-modal-header h3 {
    margin: 0;
    color: #0f172a;
    font-size: 1rem;
  }

  .graph-modal-close {
    border: 1px solid #cbd5e1;
    background: #fff;
    color: #475569;
    border-radius: 8px;
    width: 2rem;
    height: 2rem;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
  }

  .graph-modal-close:hover {
    border-color: #94a3b8;
    color: #1e293b;
  }

  .graph-modal-body {
    padding: 1rem;
    overflow: auto;
  }

  .image-compare-card {
    width: min(960px, 100%);
    background: #fff;
    border-radius: 14px;
    border: 1px solid #cbd5e1;
    padding: 1rem;
  }

  .image-compare-card h3 {
    margin: 0 0 0.75rem;
    color: #0f172a;
  }

  .image-compare-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem;
  }

  .compare-item {
    border: 1px solid #dbe2ea;
    border-radius: 10px;
    padding: 0.6rem;
    background: #f8fafc;
    display: grid;
    gap: 0.6rem;
  }

  .compare-item p {
    margin: 0;
    font-weight: 700;
    color: #334155;
  }

  .compare-item img {
    width: 100%;
    max-height: 460px;
    object-fit: contain;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    background: #fff;
  }

  .compare-item .confirm-btn,
  .compare-item .cancel-btn {
    border: none;
    border-radius: 8px;
    padding: 0.45rem 0.7rem;
    font-weight: 700;
    cursor: pointer;
  }

  .compare-item .confirm-btn {
    background: #0369a1;
    color: #fff;
  }

  .compare-item .cancel-btn {
    background: #64748b;
    color: #fff;
  }

  @media (max-width: 900px) {
    .image-compare-grid {
      grid-template-columns: 1fr;
    }

    .restored-card {
      width: 280px;
      bottom: 1rem;
      right: 1rem;
    }
  }

  @media (max-width: 640px) {
    .restored-card {
      width: calc(100% - 2rem);
      bottom: 1rem;
      right: 1rem;
      left: 1rem;
    }
  }
</style>
