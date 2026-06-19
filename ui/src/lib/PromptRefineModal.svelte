<script>
  let {
    title = 'Refine with AI',
    currentValue = '',
    currentLabel = 'Working Version (Read-only)',
    suggestedLabel = 'Suggested Version',
    instructionLabel = 'How should AI update this?',
    instructionPlaceholder = 'Describe how the AI should transform the current text...',
    requestSuggestion = async () => '',
    onapply = () => {},
    onclose = () => {},
  } = $props()

  let instruction = $state('')
  let suggestedPrompt = $state('')
  let isLoading = $state(false)
  let error = $state('')
  let showCompare = $state(false)

  async function generateSuggestion() {
    const trimmedInstruction = instruction.trim()
    if (!trimmedInstruction) {
      error = 'Please describe how you want the prompt changed.'
      return
    }

    isLoading = true
    error = ''
    try {
      const result = await requestSuggestion({
        instruction: trimmedInstruction,
        currentValue,
      })
      suggestedPrompt = String(result || '').trim()
      if (!suggestedPrompt) {
        throw new Error('No suggestion returned')
      }
      if (!showCompare) showCompare = true
    } catch (err) {
      error = err?.message || 'Failed to generate suggestion'
    } finally {
      isLoading = false
    }
  }

  function applySuggestion() {
    if (!suggestedPrompt.trim()) return
    onapply(suggestedPrompt)
    onclose()
  }

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onclose()
  }

  function handleOverlayKeydown(e) {
    if (e.key === 'Escape') onclose()
  }
</script>

<div
  class="overlay"
  role="button"
  tabindex="0"
  aria-label="Close prompt refine modal"
  onclick={handleOverlayClick}
  onkeydown={handleOverlayKeydown}
>
  <div class="modal">
    <div class="header">
      <h3>✨ {title}</h3>
      <button type="button" class="close-btn" onclick={onclose} aria-label="Close">✕</button>
    </div>

    <div class="body">
      <div class="form-group">
        <label for="refine-instruction">{instructionLabel}</label>
        <textarea
          id="refine-instruction"
          rows={3}
          placeholder={instructionPlaceholder}
          bind:value={instruction}
        ></textarea>
      </div>

      <div class="toolbar">
        <button type="button" class="btn btn-secondary" onclick={() => (showCompare = !showCompare)}>
          {showCompare ? 'Single View' : 'Side-by-Side'}
        </button>
        <button type="button" class="btn btn-primary" onclick={generateSuggestion} disabled={isLoading}>
          {isLoading ? 'Generating...' : 'Generate Suggestion'}
        </button>
      </div>

      {#if error}
        <p class="error">{error}</p>
      {/if}

      {#if showCompare}
        <div class="compare-grid">
          <div class="pane">
            <div class="pane-title">{currentLabel}</div>
            <textarea rows={12} value={currentValue} disabled></textarea>
          </div>
          <div class="pane">
            <div class="pane-title">{suggestedLabel}</div>
            <textarea rows={12} bind:value={suggestedPrompt}></textarea>
          </div>
        </div>
      {:else}
        <div class="form-group">
          <label for="suggested">{suggestedLabel}</label>
          <textarea id="suggested" rows={10} bind:value={suggestedPrompt}></textarea>
        </div>
      {/if}
    </div>

    <div class="footer">
      <button type="button" class="btn btn-secondary" onclick={onclose}>Cancel</button>
      <button type="button" class="btn btn-primary" onclick={applySuggestion} disabled={!suggestedPrompt.trim()}>
        Apply
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(2, 6, 23, 0.72);
    backdrop-filter: blur(3px);
    z-index: 80;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }

  .modal {
    width: min(1100px, 100%);
    max-height: 90vh;
    overflow: auto;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
  }

  .header, .footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid #334155;
  }

  .footer {
    border-top: 1px solid #334155;
    border-bottom: none;
    justify-content: flex-end;
    gap: 0.6rem;
  }

  .header h3 {
    margin: 0;
    color: #f8fafc;
    font-size: 1.05rem;
  }

  .close-btn {
    border: none;
    background: transparent;
    color: #94a3b8;
    font-size: 1.2rem;
    cursor: pointer;
  }

  .body {
    padding: 1rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  label, .pane-title {
    color: #cbd5e1;
    font-size: 0.9rem;
    font-weight: 600;
  }

  textarea {
    width: 100%;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #1e293b;
    color: #e2e8f0;
    padding: 0.65rem 0.75rem;
    font-family: inherit;
    resize: vertical;
  }

  textarea:disabled {
    opacity: 0.85;
    background: #162133;
  }

  .toolbar {
    display: flex;
    gap: 0.6rem;
    justify-content: flex-end;
  }

  .compare-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem;
  }

  .pane {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .btn {
    border-radius: 8px;
    border: 1px solid transparent;
    padding: 0.5rem 0.9rem;
    cursor: pointer;
    font-weight: 600;
  }

  .btn-primary {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: #eff6ff;
    border-color: #1d4ed8;
  }

  .btn-secondary {
    background: rgba(51, 65, 85, 0.4);
    color: #cbd5e1;
    border-color: #334155;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .error {
    margin: 0;
    color: #fca5a5;
    font-size: 0.86rem;
  }

  @media (max-width: 900px) {
    .compare-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
