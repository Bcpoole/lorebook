<script>
  import RawIdeaForm from './lib/RawIdeaForm.svelte'
  import AgentPanel from './lib/AgentPanel.svelte'
  import TopBar from './lib/TopBar.svelte'
  import Toast from './lib/Toast.svelte'

  let state = $state({})
  let meta = $state({})
  let running = $state(false)
  let streaming = $state(true)
  let autoSave = $state(false)
  let showStats = $state(false)
  let activeTab = $state('agents')
  let activeAgentTab = $state('loremaster')
  let graphPanelLoad = $state(null)

  let pendingSave = $state(null)
  let savedRun = $state(null)
  let filename = $state('')
  let suggesting = $state(false)
  let toastMessage = $state('')
  let toastVisible = $state(false)

  function generateDefaultFilename() {
    return crypto.randomUUID().replace(/-/g, '')
  }

  function openGraphTab() {
    activeTab = 'graph'
    if (!graphPanelLoad) {
      graphPanelLoad = import('./lib/GraphPanel.svelte')
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
        characters.push({ name: 'Companion', details: '' })
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
    state = {}
    meta = {}
    pendingSave = null
    savedRun = null
    filename = ''
    running = true
    activeAgentTab = 'loremaster'

    if (streaming) {
      const params = new URLSearchParams({ raw_idea: rawIdea, auto_save: String(autoSave) })
      const es = new EventSource(`/api/stream?${params}`)

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
        filename = generateDefaultFilename()
        toastMessage = 'Save Assets is ready.'
        toastVisible = true
      })

      es.addEventListener('run-complete', (e) => {
        const data = JSON.parse(e.data)
        state = data.state
        meta = data.meta
        savedRun = { run_id: data.run_id, run_path: data.run_path, filename: data.filename }
        toastMessage = `Auto-saved as ${data.filename}`
        toastVisible = true
        running = false
      })

      es.addEventListener('done', () => {
        es.close()
        running = false
      })

      es.onerror = () => {
        es.close()
        running = false
      }
    } else {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_idea: rawIdea, auto_save: autoSave }),
      })
      const data = await res.json()
      state = data.state
      meta = data.meta
      if (data.pending_save) {
        pendingSave = { raw_idea: rawIdea, state: data.state, meta: data.meta }
        filename = generateDefaultFilename()
        toastMessage = 'Save Assets is ready.'
        toastVisible = true
      } else {
        savedRun = { run_id: data.run_id, run_path: data.run_path, filename: data.filename }
        toastMessage = `Auto-saved as ${data.filename}`
        toastVisible = true
      }
      running = false
    }
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
    toastMessage = `Saved as ${data.filename}`
    toastVisible = true
  }

  async function handleSuggestName() {
    if (!pendingSave) return
    suggesting = true
    try {
      const res = await fetch('/api/suggest-name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_idea: pendingSave.raw_idea }),
      })
      const data = await res.json()
      filename = data.name
    } finally {
      suggesting = false
    }
  }
</script>

<TopBar bind:showStats bind:streaming bind:autoSave {meta} ongraph={openGraphTab} />

<Toast bind:visible={toastVisible} message={toastMessage} />

<main>
  <RawIdeaForm {running} onrun={handleRun} />

  {#if activeTab === 'agents'}
    <AgentPanel
      workflowState={state}
      {running}
      bind:activeAgent={activeAgentTab}
      {pendingSave}
      {savedRun}
      bind:filename
      {suggesting}
      onsave={handleSave}
      onsuggestname={handleSuggestName}
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
    max-width: 960px;
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
