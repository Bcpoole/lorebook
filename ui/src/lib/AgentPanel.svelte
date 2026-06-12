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
    showNext = false,
    nextLabel = 'Next',
    nextDisabled = true,
    showStop = false,
    showContinue = false,
    continueDisabled = true,
    onnext = () => {},
    onstop = () => {},
    oncontinue = () => {},
    onsave = () => {},
    onsuggestname = () => {},
    onrandomname = () => {},
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
  <div class="workflow-header">
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

    <div class="header-actions">
      {#if showStop}
        <button class="stop-btn" onclick={onstop} title="Stop generation" aria-label="Stop generation">
          <span class="stop-sign">STOP</span>
        </button>
      {/if}

      {#if showContinue}
        <button class="continue-btn" onclick={oncontinue} disabled={continueDisabled}>
          Continue
        </button>
      {/if}

      {#if showNext}
        <button class="next-btn" onclick={onnext} disabled={nextDisabled}>
          {nextLabel}
        </button>
      {/if}
    </div>
  </div>

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
        {#if critiqueNotes}
          <MarkdownBlock source={critiqueNotes} />
        {/if}
      {:else if passedInspection === false && critiqueNotes}
        <p class="failed">✗ Needs revision</p>
        <MarkdownBlock source={critiqueNotes} />
      {:else}
        <p class="empty">{running && lastNode === 'editor' ? 'Reviewing…' : 'No output yet.'}</p>
      {/if}

    {:else if activeAgent === 'save_assets'}
      {#if savedRun}
        <div class="save-card success">
          <p class="saved-name">✅ Saved as <strong>{savedRun.filename}</strong></p>
          <p class="run-path">{savedRun.run_path}</p>
        </div>
      {:else if pendingSave !== null}
        <div class="save-card">
          <h3 class="save-title">Save Assets</h3>
          <p class="save-subtitle">Choose a filename and store this run in outputs/runs.</p>

          <div class="save-form">
            <label class="field-label" for="filename-input">Filename</label>
            <div class="filename-row">
              <input
                id="filename-input"
                class="filename-input"
                type="text"
                bind:value={filename}
                placeholder="my_lorebook_run"
              />
            </div>

            <div class="name-actions">
              <button class="suggest-btn" onclick={onsuggestname} disabled={suggesting}>
                {suggesting ? '…' : '✨ Smart Name'}
              </button>
              <button class="random-btn" onclick={onrandomname}>🎲 Random ID</button>
            </div>

            <button class="save-btn" onclick={() => onsave(filename)}>Save Run</button>
          </div>
        </div>
      {:else}
        <p class="empty">Waiting for editor pass.</p>
      {/if}
    {/if}
  </div>
</div>

<style>
  .workflow-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
    margin-bottom: 0.75rem;
  }

  .agent-tabs {
    display: flex;
    gap: 1.3rem;
    overflow-x: auto;
    padding: 0.25rem 0.15rem 0.25rem;
    scrollbar-width: thin;
    flex: 1;
  }

  .next-btn {
    flex: 0 0 auto;
    border: 1px solid #2563eb;
    background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
    color: #fff;
    border-radius: 999px;
    padding: 0.45rem 1rem;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    cursor: pointer;
    transition: transform 120ms ease, filter 120ms ease;
  }

  .next-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    filter: brightness(1.05);
  }

  .next-btn:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  .header-actions {
    display: flex;
    gap: 0.45rem;
    flex: 0 0 auto;
  }

  .stop-btn {
    border: none;
    background: transparent;
    padding: 0;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .stop-sign {
    width: 2.2rem;
    height: 2.2rem;
    clip-path: polygon(30% 0, 70% 0, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0 70%, 0 30%);
    background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%);
    border: 2px solid #7f1d1d;
    color: #fff;
    font-size: 0.52rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 16px -10px rgba(127, 29, 29, 0.95);
  }

  .stop-btn:hover .stop-sign {
    filter: brightness(1.06);
    transform: translateY(-1px);
  }

  .continue-btn {
    border: 1px solid #6366f1;
    background: linear-gradient(180deg, #818cf8 0%, #6366f1 100%);
    color: #fff;
    border-radius: 999px;
    padding: 0.45rem 0.95rem;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    cursor: pointer;
    transition: transform 120ms ease, filter 120ms ease;
  }

  .continue-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    filter: brightness(1.05);
  }

  .continue-btn:disabled {
    cursor: not-allowed;
    opacity: 0.45;
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

  .save-card {
    border: 1px solid #dbeafe;
    border-radius: 12px;
    background: linear-gradient(160deg, #eff6ff 0%, #f8fafc 55%, #ffffff 100%);
    padding: 1rem;
    box-shadow: 0 14px 30px -28px rgba(30, 64, 175, 0.95);
  }

  .save-card.success {
    border-color: #86efac;
    background: linear-gradient(160deg, #ecfdf3 0%, #f8fafc 60%, #ffffff 100%);
  }

  .save-title {
    margin: 0;
    font-size: 1rem;
    color: #1e3a8a;
  }

  .save-subtitle {
    margin: 0.35rem 0 0.85rem;
    color: #475569;
    font-size: 0.9rem;
  }

  .save-form {
    display: grid;
    gap: 0.75rem;
  }

  .field-label {
    font-size: 0.82rem;
    color: #334155;
    font-weight: 600;
  }

  .filename-row {
    margin-top: 0.3rem;
  }

  .filename-input {
    width: 100%;
    border: 1px solid #cbd5e1;
    border-radius: 9px;
    padding: 0.6rem 0.7rem;
    font-size: 0.9rem;
    background: #fff;
    box-sizing: border-box;
  }

  .filename-input:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
  }

  .name-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .suggest-btn,
  .random-btn {
    border-radius: 999px;
    border: 1px solid #bfdbfe;
    background: #eff6ff;
    color: #1d4ed8;
    padding: 0.38rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }

  .suggest-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .save-btn {
    justify-self: start;
    border-radius: 10px;
    border: 1px solid #16a34a;
    background: linear-gradient(180deg, #22c55e 0%, #16a34a 100%);
    color: #fff;
    font-size: 0.88rem;
    font-weight: 700;
    padding: 0.5rem 0.95rem;
    cursor: pointer;
  }

  .saved-name {
    margin: 0 0 0.4rem;
    color: #166534;
  }

  .run-path {
    margin: 0;
    color: #475569;
    font-size: 0.86rem;
    word-break: break-all;
  }

  @media (max-width: 720px) {
    .workflow-header {
      flex-direction: column;
      align-items: stretch;
    }

    .agent-tabs {
      gap: 1rem;
    }

    .next-btn {
      width: 100%;
    }

    .header-actions {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr;
    }

    .continue-btn {
      width: 100%;
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
