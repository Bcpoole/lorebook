<script>
  import { onMount } from 'svelte'
  import RawIdeaForm from './lib/RawIdeaForm.svelte'
  import AgentPanel from './lib/AgentPanel.svelte'
  import TopBar from './lib/TopBar.svelte'
  import Toast from './lib/Toast.svelte'

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
  let draftPersistTimer = null
  let restoreToastTimer = null

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
    // On restore, keep navigation predictable by landing on Loremaster.
    // Users can still switch tabs manually.
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

  function scheduleDraftPersist() {
    if (!restoreDone) return
    if (draftPersistTimer) {
      clearTimeout(draftPersistTimer)
    }

    draftPersistTimer = setTimeout(async () => {
      if (!currentRawIdea && !state?.world_setting && !(state?.characters?.length) && !state?.critique_notes) {
        return
      }
      try {
        await fetch('/api/draft', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            raw_idea: currentRawIdea,
            state,
            meta,
            save_pending: Boolean(pendingSave),
          }),
        })
      } catch {
        // Best-effort draft sync should not interrupt the UI.
      }
    }, 300)
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

  async function handleRun({ rawIdea }) {
    stopGeneration(false)
    currentRawIdea = rawIdea
    state = freshWorkflowState(rawIdea)
    meta = {}
    pendingSave = null
    savedRun = null
    filename = ''
    nextStage = null
    running = true
    activeAgentTab = 'loremaster'

    if (!auto) {
      await runManualStage('loremaster')
      return
    }

    if (streaming) {
      const params = new URLSearchParams({ raw_idea: rawIdea, auto_save: 'true' })
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
        } else if (eventName === 'step-complete') {
          state = { ...payload.state, _lastNode: stage }
          meta = payload.meta ?? {}
          nextStage = payload.next_stage ?? null
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
    await runManualStage(stage, false, directive ?? '', characterIndex)
  }

  async function handleCharacterImageGenerate({ characterIndex, promptOverride = '' }) {
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

    await runManualStage(nextStage)
  }

  async function handleContinue() {
    if (running || !canContinueStage(activeAgentTab)) return
    await runManualStage(activeAgentTab, true)
  }

  function handleStopGeneration() {
    stopGeneration(true)
    clearActiveHandles()
  }

  async function handleSave(fname) {
    if (!pendingSave) return
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

  onMount(async () => {
    await restoreOnLaunch()
    restoreDone = true
  })

  $effect(() => {
    if (!restoreDone) return
    scheduleDraftPersist()
  })
</script>

<TopBar bind:showStats bind:streaming bind:auto {meta} ongraph={openGraphTab} />

<Toast bind:visible={toastVisible} message={toastMessage} />

<main>
  <RawIdeaForm {running} bind:rawIdea={currentRawIdea} onrun={handleRun} />

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
      nextDisabled={!nextStage || running}
      showStop={running}
      showContinue={activeAgentTab !== 'save_assets'}
      continueDisabled={!canContinueStage(activeAgentTab) || running}
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

<style>
  main {
    max-width: 1080px;
    margin: 0 auto;
    padding: 1rem;
    font-family: system-ui, sans-serif;
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
</style>
