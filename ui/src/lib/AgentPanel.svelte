<script>
  import MarkdownBlock from './MarkdownBlock.svelte'

  let {
    workflowState = $bindable({}),
    running = false,
    activeAgent = $bindable('loremaster'),
    pendingSave = null,
    savedRun = null,
    filename = $bindable(''),
    suggesting = false,
    onsave = () => {},
    onsuggestname = () => {},
  } = $props()

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

  // Edit state
  let editingLoremaster = $state(false)
  let editingCharacter = $state(false)
  let loremasterDraft = $state('')
  let characterDraft = $state('')

  function startEditLoremaster() {
    loremasterDraft = worldSetting
    editingLoremaster = true
  }

  function confirmEditLoremaster() {
    workflowState = { ...workflowState, world_setting: loremasterDraft }
    editingLoremaster = false
  }

  function startEditCharacter() {
    characterDraft = characters[0]?.details ?? ''
    editingCharacter = true
  }

  function confirmEditCharacter() {
    workflowState = {
      ...workflowState,
      characters: [{ ...(characters[0] ?? { name: 'Companion' }), details: characterDraft }],
    }
    editingCharacter = false
  }
</script>

<div class="agents">
  <nav class="agent-tabs" aria-label="Workflow order">
    {#each Object.entries(agentLabels) as [key, label], index}
      <button
        class="agent-step"
        class:active={activeAgent === key}
        class:current={lastNode === key && running}
        class:done={savedRun && key === 'save_assets'}
        onclick={() => (activeAgent = key)}
      >
        <span class="step-index">{index + 1}</span>
        <span class="step-label">{label}</span>
        {#if key === 'save_assets' && pendingSave !== null && !savedRun}
          <span class="ready-dot" aria-label="Save ready" title="Save Assets is ready">●</span>
        {/if}
        {#if key === 'save_assets' && savedRun}
          <span class="check">✅</span>
        {/if}
        {#if lastNode === key && running}<span class="pulse">●</span>{/if}
      </button>
    {/each}
  </nav>

  <div class="panel">
    {#if activeAgent === 'loremaster'}
      {#if worldSetting}
        <div class="panel-header">
          {#if !editingLoremaster}
            <button class="edit-btn" onclick={startEditLoremaster} disabled={running}>✎ Edit</button>
          {:else}
            <button class="confirm-btn" onclick={confirmEditLoremaster}>✔ Done</button>
            <button class="cancel-btn" onclick={() => (editingLoremaster = false)}>✕</button>
          {/if}
        </div>
        {#if editingLoremaster}
          <textarea class="edit-area" bind:value={loremasterDraft}></textarea>
        {:else}
          <MarkdownBlock source={worldSetting} />
        {/if}
      {:else}
        <p class="empty">{running && lastNode === 'loremaster' ? 'Generating…' : 'No output yet.'}</p>
      {/if}

    {:else if activeAgent === 'character_designer'}
      {#if characters.length > 0}
        {#each characters as char}
          <div class="panel-header">
            <h3 class="char-name">{char.name}</h3>
            {#if !editingCharacter}
              <button class="edit-btn" onclick={startEditCharacter} disabled={running}>✎ Edit</button>
            {:else}
              <button class="confirm-btn" onclick={confirmEditCharacter}>✔ Done</button>
              <button class="cancel-btn" onclick={() => (editingCharacter = false)}>✕</button>
            {/if}
          </div>
          {#if editingCharacter}
            <textarea class="edit-area" bind:value={characterDraft}></textarea>
          {:else}
            <MarkdownBlock source={char.details} />
          {/if}
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
      {#if savedRun}
        <p class="saved-name">✅ Saved as <strong>{savedRun.filename}</strong></p>
        <p class="run-path">{savedRun.run_path}</p>
      {:else if pendingSave !== null}
        <div class="save-form">
          <label class="field-label">
            Filename
            <div class="filename-row">
              <input
                class="filename-input"
                type="text"
                bind:value={filename}
                placeholder="my_lorebook_run"
              />
              <button class="suggest-btn" onclick={onsuggestname} disabled={suggesting}>
                {suggesting ? '…' : '✨ Smart Name'}
              </button>
            </div>
          </label>
          <button class="save-btn" onclick={() => onsave(filename)}>Save</button>
        </div>
      {:else}
        <p class="empty">Waiting for editor pass.</p>
      {/if}
    {/if}
  </div>
</div>

<style>
  .agent-tabs {
    display: flex;
    gap: 1.3rem;
    margin-bottom: 0.75rem;
    overflow-x: auto;
    padding: 0.25rem 0.15rem 0.4rem;
    scrollbar-width: thin;
  }

  .agent-step {
    position: relative;
    flex: 0 0 auto;
    padding: 0.45rem 0.95rem;
    border: 1px solid #cbd5e1;
    border-radius: 999px;
    background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
    cursor: pointer;
    font-size: 0.875rem;
    color: #334155;
    display: flex;
    align-items: center;
    gap: 0.45rem;
    transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
  }

  .agent-step:hover {
    transform: translateY(-1px);
    border-color: #94a3b8;
    box-shadow: 0 8px 18px -14px rgba(15, 23, 42, 0.75);
  }

  .agent-step::after {
    content: '➜';
    position: absolute;
    right: -1.03rem;
    top: 50%;
    transform: translateY(-50%);
    color: #94a3b8;
    font-size: 0.9rem;
    pointer-events: none;
  }

  .agent-step:last-child::after {
    content: '';
  }

  .step-index {
    width: 1.3rem;
    height: 1.3rem;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #dbeafe;
    color: #1e3a8a;
    font-size: 0.72rem;
    font-weight: 700;
    border: 1px solid #bfdbfe;
  }

  .step-label {
    white-space: nowrap;
    font-weight: 600;
    letter-spacing: 0.01em;
  }

  .agent-step.active {
    background: #1e40af;
    color: #fff;
    border-color: #1e40af;
    box-shadow: 0 8px 20px -14px rgba(30, 64, 175, 1);
  }

  .agent-step.active .step-index {
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.35);
    color: #fff;
  }

  .agent-step.current {
    box-shadow: 0 0 0 2px #93c5fd;
  }

  .agent-step.done {
    border-color: #16a34a;
  }

  .pulse {
    color: #22c55e;
    animation: blink 1s step-start infinite;
  }

  .ready-dot {
    color: #f59e0b;
    font-size: 0.8rem;
    line-height: 1;
    text-shadow: 0 0 10px rgba(245, 158, 11, 0.5);
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

  .panel-header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.6rem;
  }

  .char-name {
    margin: 0;
    flex: 1;
  }

  .edit-btn {
    margin-left: auto;
    padding: 0.2rem 0.65rem;
    background: transparent;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    color: #64748b;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .edit-btn:hover:not(:disabled) { border-color: #94a3b8; color: #1e293b; }
  .edit-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .confirm-btn {
    padding: 0.2rem 0.65rem;
    background: #16a34a;
    border: none;
    border-radius: 5px;
    color: #fff;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .confirm-btn:hover { background: #15803d; }

  .cancel-btn {
    padding: 0.2rem 0.55rem;
    background: transparent;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    color: #64748b;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .cancel-btn:hover { border-color: #94a3b8; color: #dc2626; }

  .edit-area {
    width: 100%;
    min-height: 300px;
    padding: 0.65rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-family: ui-monospace, Menlo, Consolas, monospace;
    font-size: 0.875rem;
    line-height: 1.6;
    resize: vertical;
    box-sizing: border-box;
    background: #fff;
  }

  @media (max-width: 720px) {
    .agent-tabs {
      gap: 1rem;
    }

    .agent-step {
      padding: 0.4rem 0.8rem;
    }

    .agent-step::after {
      right: -0.86rem;
      font-size: 0.8rem;
    }
  }
</style>
