<script>
  import MarkdownBlock from './MarkdownBlock.svelte'

  let { workflowState = {}, running = false } = $props()

  let activeAgent = $state('loremaster')

  let worldSetting = $derived(workflowState.world_setting ?? '')
  let characters = $derived(workflowState.characters ?? [])
  let critiqueNotes = $derived(workflowState.critique_notes ?? '')
  let passedInspection = $derived(workflowState.passed_inspection ?? null)
  let lastNode = $derived(workflowState._lastNode ?? null)

  const agentLabels = {
    loremaster: 'Loremaster',
    character_designer: 'Character Designer',
    editor: 'Editor',
    save_assets: 'Save Assets',
  }
</script>

<div class="agents">
  <nav class="agent-tabs">
    {#each Object.entries(agentLabels) as [key, label]}
      <button
        class:active={activeAgent === key}
        class:current={lastNode === key && running}
        onclick={() => (activeAgent = key)}
      >
        {label}
        {#if lastNode === key && running}<span class="pulse">●</span>{/if}
      </button>
    {/each}
  </nav>

  <div class="panel">
    {#if activeAgent === 'loremaster'}
      {#if worldSetting}
        <MarkdownBlock source={worldSetting} />
      {:else}
        <p class="empty">{running && lastNode === 'loremaster' ? 'Generating…' : 'No output yet.'}</p>
      {/if}

    {:else if activeAgent === 'character_designer'}
      {#if characters.length > 0}
        {#each characters as char}
          <h3>{char.name}</h3>
          <MarkdownBlock source={char.details} />
        {/each}
      {:else}
        <p class="empty">{running && lastNode === 'character_designer' ? 'Generating…' : 'No output yet.'}</p>
      {/if}

    {:else if activeAgent === 'editor'}
      {#if passedInspection === true}
        <p class="passed">✓ PASSED</p>
      {:else if passedInspection === false && critiqueNotes}
        <p class="failed">✗ Needs revision</p>
        <MarkdownBlock source={critiqueNotes} />
      {:else}
        <p class="empty">{running && lastNode === 'editor' ? 'Reviewing…' : 'No output yet.'}</p>
      {/if}

    {:else if activeAgent === 'save_assets'}
      {#if passedInspection === true}
        <p class="passed">Assets ready to export.</p>
      {:else}
        <p class="empty">Waiting for editor pass.</p>
      {/if}
    {/if}
  </div>
</div>

<style>
  .agent-tabs {
    display: flex;
    gap: 0.4rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
  }

  .agent-tabs button {
    padding: 0.35rem 0.9rem;
    border: 1px solid #cbd5e1;
    border-radius: 20px;
    background: #f8fafc;
    cursor: pointer;
    font-size: 0.875rem;
    color: #475569;
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .agent-tabs button.active {
    background: #1e40af;
    color: #fff;
    border-color: #1e40af;
  }

  .agent-tabs button.current {
    box-shadow: 0 0 0 2px #93c5fd;
  }

  .pulse {
    color: #22c55e;
    animation: blink 1s step-start infinite;
  }

  @keyframes blink {
    50% { opacity: 0; }
  }

  .panel {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    min-height: 200px;
  }

  .empty { color: #94a3b8; font-style: italic; }
  .passed { color: #16a34a; font-weight: 600; }
  .failed { color: #dc2626; font-weight: 600; }
</style>
