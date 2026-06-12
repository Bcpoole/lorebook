<script>
  let {
    live = $bindable({}),
    saved = $bindable({}),
    isDirty = $bindable(false),
    onSave = () => {},
    onCancel = () => {},
  } = $props()

  let expanded = $state({
    sampler: true,
    length: false,
    format: false,
    advanced: false,
  })

  function toggleSection(section) {
    expanded[section] = !expanded[section]
  }

  function handleSave() {
    onSave()
  }

  function handleCancel() {
    onCancel()
  }

  function resetToSaved() {
    if (saved) {
      live = JSON.parse(JSON.stringify(saved))
    }
  }

  $effect.pre(() => {
    // Compute dirty flag whenever live changes
    isDirty = JSON.stringify(live) !== JSON.stringify(saved)
  })

  // Initialize defaults if empty
  $effect.pre(() => {
    if (!live || Object.keys(live).length === 0) {
      live = {
        temperature: 0.7,
        topP: 0.9,
        topK: 40,
        repetitionPenalty: 1.1,
        maxLength: 512,
        contextSize: 2048,
        outputFormat: "markdown",
        multilineReplies: true,
        minP: 0,
        presencePenalty: 0,
        samplerSeed: -1,
      }
    }
  })
</script>

<div class="experimentation-panel">
  <div class="panel-header">
    <h3>⚗️ Experimentation</h3>
    {#if isDirty}
      <span class="dirty-indicator">●</span>
    {/if}
  </div>

  <div class="panel-content">
    <!-- Sampler Settings Section -->
    <div class="section">
      <div class="section-header" onclick={() => toggleSection('sampler')}>
        <span class="toggle-icon">{expanded.sampler ? '▼' : '▶'}</span>
        <span>Sampler</span>
      </div>
      {#if expanded.sampler}
        <div class="section-body">
          <div class="control-group">
            <label for="temp">Temperature</label>
            <div class="input-row">
              <input
                id="temp"
                type="range"
                min="0.1"
                max="2"
                step="0.05"
                bind:value={live.temperature}
              />
              <input
                type="number"
                min="0.1"
                max="2"
                step="0.05"
                bind:value={live.temperature}
                class="number-input"
              />
            </div>
            <div class="help-text">Randomness of sampling. Higher = more creative.</div>
          </div>

          <div class="control-group">
            <label for="top-p">Top-P (Nucleus)</label>
            <div class="input-row">
              <input id="top-p" type="range" min="0" max="1" step="0.01" bind:value={live.topP} />
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                bind:value={live.topP}
                class="number-input"
              />
            </div>
            <div class="help-text">Discard unlikely tokens. 1.0 = disabled.</div>
          </div>

          <div class="control-group">
            <label for="top-k">Top-K</label>
            <div class="input-row">
              <input id="top-k" type="range" min="0" max="100" step="1" bind:value={live.topK} />
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                bind:value={live.topK}
                class="number-input"
              />
            </div>
            <div class="help-text">Only consider K most likely tokens. 0 = disabled.</div>
          </div>

          <div class="control-group">
            <label for="rep-pen">Repetition Penalty</label>
            <div class="input-row">
              <input
                id="rep-pen"
                type="range"
                min="1"
                max="2"
                step="0.01"
                bind:value={live.repetitionPenalty}
              />
              <input
                type="number"
                min="1"
                max="2"
                step="0.01"
                bind:value={live.repetitionPenalty}
                class="number-input"
              />
            </div>
            <div class="help-text">Penalize repeated words. Higher = less repetition.</div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Length Settings Section -->
    <div class="section">
      <div class="section-header" onclick={() => toggleSection('length')}>
        <span class="toggle-icon">{expanded.length ? '▼' : '▶'}</span>
        <span>Length</span>
      </div>
      {#if expanded.length}
        <div class="section-body">
          <div class="control-group">
            <label for="max-len">Max Output Tokens</label>
            <div class="input-row">
              <input
                id="max-len"
                type="range"
                min="16"
                max="2048"
                step="16"
                bind:value={live.maxLength}
              />
              <input
                type="number"
                min="16"
                max="2048"
                step="16"
                bind:value={live.maxLength}
                class="number-input"
              />
            </div>
            <div class="help-text">Maximum tokens per generation.</div>
          </div>

          <div class="control-group">
            <label for="ctx-size">Context Size</label>
            <div class="input-row">
              <input
                id="ctx-size"
                type="range"
                min="512"
                max="8192"
                step="256"
                bind:value={live.contextSize}
              />
              <input
                type="number"
                min="512"
                max="8192"
                step="256"
                bind:value={live.contextSize}
                class="number-input"
              />
            </div>
            <div class="help-text">Context window size in tokens.</div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Format Settings Section -->
    <div class="section">
      <div class="section-header" onclick={() => toggleSection('format')}>
        <span class="toggle-icon">{expanded.format ? '▼' : '▶'}</span>
        <span>Format</span>
      </div>
      {#if expanded.format}
        <div class="section-body">
          <div class="control-group">
            <label for="format-mode">Output Format</label>
            <select id="format-mode" bind:value={live.outputFormat}>
              <option value="markdown">Markdown</option>
              <option value="plain">Plain Text</option>
              <option value="json">JSON</option>
            </select>
            <div class="help-text">Output formatting preference.</div>
          </div>

          <div class="control-group">
            <label for="multiline">
              <input type="checkbox" id="multiline" bind:checked={live.multilineReplies} />
              Allow Multiline Replies
            </label>
            <div class="help-text">Allow multiple lines in responses.</div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Advanced Settings Section -->
    <div class="section">
      <div class="section-header" onclick={() => toggleSection('advanced')}>
        <span class="toggle-icon">{expanded.advanced ? '▼' : '▶'}</span>
        <span>Advanced</span>
      </div>
      {#if expanded.advanced}
        <div class="section-body">
          <div class="control-group">
            <label for="min-p">Min-P Sampling</label>
            <div class="input-row">
              <input
                id="min-p"
                type="range"
                min="0"
                max="1"
                step="0.01"
                bind:value={live.minP}
              />
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                bind:value={live.minP}
                class="number-input"
              />
            </div>
            <div class="help-text">Minimum token probability. 0 = disabled.</div>
          </div>

          <div class="control-group">
            <label for="presence-pen">Presence Penalty</label>
            <div class="input-row">
              <input
                id="presence-pen"
                type="range"
                min="-2"
                max="2"
                step="0.1"
                bind:value={live.presencePenalty}
              />
              <input
                type="number"
                min="-2"
                max="2"
                step="0.1"
                bind:value={live.presencePenalty}
                class="number-input"
              />
            </div>
            <div class="help-text">Penalize tokens already in context.</div>
          </div>

          <div class="control-group">
            <label for="sampler-seed">Sampler Seed</label>
            <div class="input-row">
              <input
                id="sampler-seed"
                type="number"
                min="-1"
                bind:value={live.samplerSeed}
                class="number-input"
              />
            </div>
            <div class="help-text">-1 to disable, any integer for reproducibility.</div>
          </div>
        </div>
      {/if}
    </div>
  </div>

  <div class="panel-footer">
    <button class="btn btn-save" onclick={handleSave} disabled={!isDirty}>
      💾 Save
    </button>
    <button class="btn btn-cancel" onclick={handleCancel} disabled={!isDirty}>
      ✕ Cancel
    </button>
  </div>
</div>

<style>
  .experimentation-panel {
    display: flex;
    flex-direction: column;
    background: #1a1a2e;
    border-right: 1px solid #16213e;
    color: #eaeaea;
    font-size: 12px;
    font-family: system-ui, -apple-system, sans-serif;
    height: 100vh;
    width: 280px;
    overflow-y: auto;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.3);
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid #16213e;
    background: #0f3460;
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .panel-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    flex: 1;
  }

  .dirty-indicator {
    color: #e74c3c;
    font-size: 16px;
    animation: pulse 1s infinite;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  .panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
  }

  .section {
    border-bottom: 1px solid #16213e;
  }

  .section-header {
    display: flex;
    align-items: center;
    padding: 10px 16px;
    cursor: pointer;
    user-select: none;
    transition: background 0.2s;
    background: #151a3f;
  }

  .section-header:hover {
    background: #1f2851;
  }

  .toggle-icon {
    margin-right: 8px;
    font-size: 11px;
    color: #888;
  }

  .section-header span:last-child {
    font-weight: 500;
    font-size: 13px;
  }

  .section-body {
    padding: 12px 16px;
    background: #16213e;
  }

  .control-group {
    margin-bottom: 14px;
  }

  .control-group:last-child {
    margin-bottom: 0;
  }

  label {
    display: block;
    margin-bottom: 6px;
    font-weight: 500;
    color: #d4d4d4;
    font-size: 12px;
  }

  label[for*='line'] {
    display: flex;
    align-items: center;
    margin-bottom: 4px;
  }

  label input[type='checkbox'] {
    margin-right: 6px;
  }

  .input-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  input[type='range'] {
    flex: 1;
    height: 5px;
    border-radius: 2px;
    background: #0f3460;
    outline: none;
    cursor: pointer;
    -webkit-appearance: none;
    appearance: none;
  }

  input[type='range']::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #3498db;
    cursor: pointer;
    border: 1px solid #2980b9;
  }

  input[type='range']::-moz-range-thumb {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #3498db;
    cursor: pointer;
    border: 1px solid #2980b9;
  }

  .number-input {
    width: 60px;
    padding: 4px 8px;
    background: #0f3460;
    border: 1px solid #16213e;
    border-radius: 3px;
    color: #eaeaea;
    font-size: 11px;
    text-align: center;
  }

  .number-input:focus {
    outline: none;
    border-color: #3498db;
    box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.1);
  }

  select {
    width: 100%;
    padding: 6px 8px;
    background: #0f3460;
    border: 1px solid #16213e;
    border-radius: 3px;
    color: #eaeaea;
    font-size: 12px;
  }

  select:focus {
    outline: none;
    border-color: #3498db;
  }

  select option {
    background: #1a1a2e;
    color: #eaeaea;
  }

  input[type='checkbox'] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    accent-color: #3498db;
  }

  .help-text {
    font-size: 11px;
    color: #888;
    margin-top: 4px;
    line-height: 1.3;
  }

  .panel-footer {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid #16213e;
    background: #0f3460;
    position: sticky;
    bottom: 0;
    z-index: 10;
  }

  .btn {
    flex: 1;
    padding: 8px 12px;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-save {
    background: #27ae60;
    color: white;
  }

  .btn-save:hover:not(:disabled) {
    background: #229954;
  }

  .btn-cancel {
    background: #e74c3c;
    color: white;
  }

  .btn-cancel:hover:not(:disabled) {
    background: #c0392b;
  }
</style>
