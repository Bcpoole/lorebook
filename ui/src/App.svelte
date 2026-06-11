<script>
  import RawIdeaForm from './lib/RawIdeaForm.svelte'
  import AgentPanel from './lib/AgentPanel.svelte'
  import TopBar from './lib/TopBar.svelte'

  let state = $state({})
  let meta = $state({})
  let running = $state(false)
  let streaming = $state(true)
  let showStats = $state(false)
  let activeTab = $state('agents')
  let graphPanelLoad = $state(null)
  let lastRun = $state(null)

  function openGraphTab() {
    activeTab = 'graph'
    if (!graphPanelLoad) {
      graphPanelLoad = import('./lib/GraphPanel.svelte')
    }
  }

  async function handleRun({ rawIdea }) {
    state = {}
    meta = {}
    lastRun = null
    running = true

    if (streaming) {
      const params = new URLSearchParams({ raw_idea: rawIdea })
      const es = new EventSource(`/api/stream?${params}`)

      es.addEventListener('node', (e) => {
        const { node, output } = JSON.parse(e.data)
        state = { ...state, ...output, _lastNode: node }
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
        body: JSON.stringify({ raw_idea: rawIdea }),
      })
      const data = await res.json()
      state = data.state
      meta = data.meta
      lastRun = { runId: data.run_id, runPath: data.run_path }
      running = false
    }
  }
</script>

<TopBar bind:showStats bind:streaming {meta} />

<main>
  <RawIdeaForm {running} onrun={handleRun} />

  {#if lastRun}
    <p class="saved-run">Saved run {lastRun.runId} → {lastRun.runPath}</p>
  {/if}

  <nav class="tabs">
    <button class:active={activeTab === 'agents'} onclick={() => (activeTab = 'agents')}>Agents</button>
    <button class:active={activeTab === 'graph'} onclick={openGraphTab}>Graph</button>
  </nav>

  {#if activeTab === 'agents'}
    <AgentPanel workflowState={state} {running} />
  {:else if activeTab === 'graph'}
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
  {/if}
</main>

<style>
  main {
    max-width: 960px;
    margin: 0 auto;
    padding: 1rem;
    font-family: system-ui, sans-serif;
  }

  .tabs {
    display: flex;
    gap: 0.5rem;
    margin: 1rem 0;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 0.25rem;
  }

  .tabs button {
    padding: 0.4rem 1rem;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 0.95rem;
    color: #64748b;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
  }

  .tabs button.active {
    color: #1e40af;
    border-bottom-color: #1e40af;
    font-weight: 600;
  }

  .saved-run {
    margin: 0.75rem 0 0;
    color: #64748b;
    font-size: 0.85rem;
    word-break: break-all;
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
