<script>
  /**
   * PromptEditor - High-quality system prompt editor with fine-tuning
   *
   * Features:
   * - Rich editing experience with character count
   * - Template fallback display with placeholder text
   * - Reset to last-saved value
   * - Live preview mode
   * - Expandable history/versions
   */

  import PromptRefineModal from './PromptRefineModal.svelte'

  let {
    promptKey = '',
    promptName = '',
    value = '',
    savedValue = '',
    templateValue = '',
    description = '',
    personaDescription = '',
    personaStyle = 'balanced',
    onchange = () => {},
    ondirty = () => {},
  } = $props()

  let isExpanded = $state(false)
  let showRefineModal = $state(false)
  let showTemplatePreview = $state(false)
  let editHistory = $state([])
  let characterCount = $derived(value.length)
  let templateCharCount = $derived(templateValue?.length ?? 0)
  let hasUnsavedChanges = $derived(value !== savedValue)
  let usingTemplate = $derived(value.trim().length === 0)

  function handleChange(e) {
    value = e.target.value
    onchange(value)
    ondirty(true)
    
    // Track history
    if (editHistory[editHistory.length - 1]?.text !== value) {
      editHistory = [...editHistory, { text: value, timestamp: Date.now() }]
    }
  }

  function resetToSaved() {
    value = savedValue
    onchange(value)
    ondirty(true)
    editHistory = []
  }

  function toggleExpanded() {
    isExpanded = !isExpanded
  }

  function getDisplayPlaceholder() {
    if (value.trim()) return null
    return templateValue ? templateValue.substring(0, 150) + (templateValue.length > 150 ? '...' : '') : ''
  }

  function applyRefinedPrompt(newPrompt) {
    value = newPrompt
    onchange(value)
    ondirty(true)
  }

  async function requestRefineSuggestion({ instruction, currentValue }) {
    const response = await fetch('/api/experimentation/refine-persona-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt_key: promptKey,
        current_prompt: currentValue,
        template_value: templateValue,
        instruction,
        description: personaDescription,
        style: personaStyle,
      }),
    })

    if (!response.ok) {
      let detail = 'Failed to refine prompt'
      try {
        const payload = await response.json()
        detail = payload?.detail || detail
      } catch {
        // keep default
      }
      throw new Error(detail)
    }

    const payload = await response.json()
    return payload?.system_prompt || ''
  }
</script>

<div class="prompt-editor">
  <div class="header">
    <div class="title-area">
      <div class="title-row">
        <h3 class="prompt-name">{promptName}</h3>
        {#if description}
          <button
            type="button"
            class="info-btn"
            title={description}
            aria-label={`Prompt info: ${description}`}
          >
            i
          </button>
        {/if}
      </div>
    </div>

    <div class="controls">
      {#if hasUnsavedChanges}
        <button 
          type="button" 
          class="btn btn-sm btn-secondary"
          onclick={resetToSaved}
          title="Reset to saved value"
        >
          ↻ Reset
        </button>
      {/if}

      <button
        type="button"
        class="btn btn-sm btn-secondary"
        onclick={() => (showRefineModal = true)}
        title="Ask AI to refine this prompt"
      >
        ✨ Refine
      </button>

      <button 
        type="button"
        class="toggle-btn"
        onclick={toggleExpanded}
        title={isExpanded ? 'Collapse' : 'Expand'}
        aria-label={isExpanded ? 'Collapse prompt editor' : 'Expand prompt editor'}
        aria-expanded={isExpanded}
      >
        {isExpanded ? '▴' : '▾'}
      </button>
    </div>
  </div>

  {#if isExpanded}
    <div class="editor-expanded">
      <div class="main-editor">
        <textarea
          class="prompt-input"
          placeholder={getDisplayPlaceholder()}
          value={value}
          onchange={handleChange}
          oninput={handleChange}
          rows={12}
        ></textarea>

        <div class="editor-footer">
          <div class="char-count">
            {characterCount} / {templateCharCount} chars {#if usingTemplate}(using template){/if}
          </div>
        </div>
      </div>

      {#if templateValue && usingTemplate}
        <div class="template-preview">
          <div class="template-header">
            <span class="label">📋 Template Value</span>
            {#if !value}
              <span class="hint">Currently using this template (empty custom value)</span>
            {/if}
          </div>
          <div class="template-text">{templateValue}</div>
        </div>
      {/if}

      {#if editHistory.length > 1}
        <div class="history-panel">
          <button 
            type="button"
            class="btn btn-xs btn-secondary"
            onclick={() => { showTemplatePreview = !showTemplatePreview }}
          >
            {showTemplatePreview ? 'Hide' : 'Show'} History ({editHistory.length} versions)
          </button>

          {#if showTemplatePreview}
            <div class="history-list">
              {#each editHistory.slice(-5) as entry, idx}
                <div class="history-entry">
                  <span class="history-time">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  <span class="history-preview">{entry.text.substring(0, 80)}...</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>

      {/if}
    </div>
  {:else}
    <div class="editor-compact">
      <div class="compact-display">
        <textarea
          class="prompt-input prompt-input-compact"
          placeholder={getDisplayPlaceholder()}
          value={value}
          onchange={handleChange}
          oninput={handleChange}
          rows={3}
        ></textarea>
        <div class="compact-footer">
          <span class="char-count-sm">{characterCount} chars</span>
        </div>
      </div>
    </div>
  {/if}
</div>

{#if showRefineModal}
  <PromptRefineModal
    title={`Refine — ${promptName}`}
    currentValue={value}
    currentLabel="Working Version (Read-only)"
    suggestedLabel="Suggested Version"
    instructionLabel="How should AI update this prompt?"
    instructionPlaceholder="Example: Make this more concise and stricter about output format."
    requestSuggestion={requestRefineSuggestion}
    onapply={applyRefinedPrompt}
    onclose={() => (showRefineModal = false)}
  />
{/if}

<style>
  .prompt-editor {
    border: 1px solid #334155;
    border-radius: 8px;
    background: #0f172a;
    overflow: hidden;
    transition: all 0.2s ease;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid #334155;
    gap: 1rem;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  }

  .title-area {
    flex: 1;
    min-width: 0;
  }

  .prompt-name {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    color: #f8fafc;
    letter-spacing: 0.02em;
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;
  }

  .controls {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
    align-items: center;
  }

  /* Buttons */
  .btn {
    padding: 0.5rem 0.9rem;
    border: 1px solid transparent;
    border-radius: 6px;
    background: transparent;
    color: #cbd5e1;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }

  .btn:hover {
    background: rgba(71, 85, 105, 0.3);
    border-color: #475569;
  }

  .btn:active {
    transform: scale(0.98);
  }

  .btn-sm {
    padding: 0.35rem 0.7rem;
    font-size: 0.78rem;
  }

  .btn-xs {
    padding: 0.25rem 0.5rem;
    font-size: 0.7rem;
  }

  .btn-secondary {
    border-color: #334155;
    background: rgba(51, 65, 85, 0.4);
  }

  .btn-secondary:hover {
    background: rgba(71, 85, 105, 0.5);
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .info-btn {
    width: 1.1rem;
    height: 1.1rem;
    border-radius: 999px;
    border: 1px solid #475569;
    background: rgba(51, 65, 85, 0.45);
    color: #cbd5e1;
    font-size: 0.72rem;
    line-height: 1;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: help;
    flex-shrink: 0;
  }

  .toggle-btn {
    width: 1.8rem;
    height: 1.8rem;
    border-radius: 999px;
    border: 1px solid #334155;
    background: rgba(30, 41, 59, 0.35);
    color: #94a3b8;
    font-size: 0.95rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .toggle-btn:hover {
    color: #e2e8f0;
    border-color: #475569;
    background: rgba(51, 65, 85, 0.45);
  }

  /* Editor modes */
  .editor-expanded,
  .editor-compact {
    padding: 1.25rem;
  }

  .main-editor {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .prompt-input {
    width: 100%;
    padding: 0.85rem;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #e2e8f0;
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 0.95rem;
    line-height: 1.5;
    resize: vertical;
    transition: all 0.15s ease;
  }

  .prompt-input:focus {
    outline: none;
    border-color: #0ea5e9;
    background: #1a2332;
    box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
  }

  .prompt-input::placeholder {
    color: #64748b;
  }

  .prompt-input-compact {
    resize: none;
  }

  .editor-footer,
  .compact-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
    color: #94a3b8;
  }

  .char-count,
  .char-count-sm {
    font-variant-numeric: tabular-nums;
  }

  .char-count-sm {
    color: #64748b;
  }

  /* Template preview */
  .template-preview {
    border: 1px solid #334155;
    border-radius: 6px;
    background: rgba(6, 182, 212, 0.05);
    padding: 1rem;
    margin-top: 1.5rem;
  }

  .template-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
    font-size: 0.85rem;
    font-weight: 500;
    color: #67e8f9;
  }

  .label {
    font-weight: 600;
  }

  .hint {
    font-size: 0.8rem;
    color: #64748b;
    font-weight: 400;
  }

  .template-text {
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 0.9rem;
    line-height: 1.5;
    color: #cbd5e1;
    white-space: pre-wrap;
    word-break: break-word;
  }

  /* History panel */
  .history-panel {
    border-top: 1px solid #334155;
    margin-top: 1.5rem;
    padding-top: 1rem;
  }

  .history-list {
    margin-top: 0.75rem;
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid #334155;
    border-radius: 4px;
    background: rgba(15, 23, 42, 0.5);
  }

  .history-entry {
    display: flex;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #334155;
    font-size: 0.8rem;
  }

  .history-entry:last-child {
    border-bottom: none;
  }

  .history-time {
    color: #94a3b8;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .history-preview {
    color: #cbd5e1;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Compact display */
  .compact-display {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

</style>
