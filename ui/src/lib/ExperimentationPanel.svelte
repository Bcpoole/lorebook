<script>
  let {
    live = $bindable({}),
    saved = $bindable({}),
    isDirty = $bindable(false),
    sdStyleOptions = ['balanced'],
    auto = $bindable(false),
    streaming = $bindable(true),
    showStats = $bindable(false),
    onSave = () => {},
    onCancel = () => {},
    onSaveSd = () => {},
    onCancelSd = () => {},
    onOpenGraph = () => {},
  } = $props()

  let activeTab = $state('experiment')
  let lastEditedDimension = $state(null)

  const samplerOptions = [
    'DPM++ 2M',
    'DPM++ 2M Karras',
    'Euler',
    'Euler A',
    'DPM++ SDE',
  ]

  const defaults = {
    general: {
      outputFormat: 'markdown',
      multilineReplies: true,
      auto: false,
      streaming: true,
      showStats: false,
      sdEndpoint: 'http://127.0.0.1:7860',
      persona: 'blank',
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
      steps: 30,
      width: 768,
      height: 768,
      cfgScale: 3,
      samplerName: 'DPM++ 2M',
      negativePromptExtra: '',
    },
  }

  function normalizeConfig(config) {
    return {
      general: {
        ...defaults.general,
        ...(config?.general ?? {}),
      },
      experimentation: {
        ...defaults.experimentation,
        ...(config?.experimentation ?? {}),
      },
      sd: {
        ...defaults.sd,
        ...(config?.sd ?? {}),
      },
    }
  }

  function enforceValidation(config) {
    const normalized = normalizeConfig(config)
    
    // Enforce minimum values
    normalized.sd.steps = Math.max(1, Math.min(60, normalized.sd.steps || 1))
    normalized.sd.width = Math.max(1, normalized.sd.width || 768)
    normalized.sd.height = Math.max(1, normalized.sd.height || 768)
    normalized.sd.cfgScale = Math.max(0.1, Math.min(30, normalized.sd.cfgScale || 3))
    
    return normalized
  }

  function applyAspectRatio(ratio) {
    if (!lastEditedDimension) return
    
    if (lastEditedDimension === 'width') {
      if (ratio === '1:1') {
        live.sd.height = live.sd.width
      } else if (ratio === '3:2') {
        live.sd.height = Math.floor(live.sd.width * 2 / 3)
      } else if (ratio === '2:3') {
        live.sd.height = Math.floor(live.sd.width * 3 / 2)
      }
    } else if (lastEditedDimension === 'height') {
      if (ratio === '1:1') {
        live.sd.width = live.sd.height
      } else if (ratio === '3:2') {
        live.sd.width = Math.floor(live.sd.height * 3 / 2)
      } else if (ratio === '2:3') {
        live.sd.width = Math.floor(live.sd.height * 2 / 3)
      }
    }
  }

  function handleSave() {
    live = enforceValidation(live)
    onSave()
  }

  function handleCancel() {
    onCancel()
  }

  function handleSaveSd() {
    live = enforceValidation(live)
    onSaveSd()
  }

  function handleCancelSd() {
    onCancelSd()
  }

  // Sync top-level checkboxes with general config
  $effect.pre(() => {
    if (live?.general) {
      auto = live.general.auto ?? false
      streaming = live.general.streaming ?? true
      showStats = live.general.showStats ?? false
    }
  })

  $effect.pre(() => {
    if (live?.general) {
      live.general.auto = auto
      live.general.streaming = streaming
      live.general.showStats = showStats
    }
  })

  $effect.pre(() => {
    if (!live || Object.keys(live).length === 0 || !live.experimentation) {
      live = enforceValidation(live)
    }

    if (!saved || Object.keys(saved).length === 0 || !saved.experimentation) {
      saved = enforceValidation(saved)
    }

    isDirty = JSON.stringify(live) !== JSON.stringify(saved)
  })
</script>

<div class="experimentation-panel">
  <div class="panel-header">
    <div class="tab-strip" role="tablist" aria-label="Settings tabs">
      <button
        class="tab-btn"
        class:active={activeTab === 'general'}
        role="tab"
        aria-selected={activeTab === 'general'}
        title="General settings"
        aria-label="General settings"
        onclick={() => (activeTab = 'general')}
      >
        ⚙️
      </button>
      <button
        class="tab-btn"
        class:active={activeTab === 'experiment'}
        role="tab"
        aria-selected={activeTab === 'experiment'}
        title="Experimentation settings"
        aria-label="Experimentation settings"
        onclick={() => (activeTab = 'experiment')}
      >
        🔬
      </button>
      <button
        class="tab-btn"
        class:active={activeTab === 'sd'}
        role="tab"
        aria-selected={activeTab === 'sd'}
        title="Stable Diffusion settings"
        aria-label="Stable Diffusion settings"
        onclick={() => (activeTab = 'sd')}
      >
        🖌️
      </button>
    </div>

    {#if isDirty}
      <span class="dirty-indicator" title="Unsaved changes">●</span>
    {/if}
  </div>

  <div class="panel-actions">
    <button class="btn btn-save" onclick={handleSave} disabled={!isDirty}>💾 Save</button>
    <button class="btn btn-cancel" onclick={handleCancel} disabled={!isDirty}>✕ Cancel</button>
  </div>

  <div class="panel-content">
    {#if activeTab === 'general'}
      <section class="section-body">
        <div class="control-group">
          <label for="output-format">Output Format</label>
          <select id="output-format" bind:value={live.general.outputFormat}>
            <option value="markdown">Markdown</option>
            <option value="plain">Plain Text</option>
            <option value="json">JSON</option>
          </select>
        </div>

        <div class="control-group checkbox-row">
          <label for="multiline-replies">Allow Multiline Replies</label>
          <input type="checkbox" id="multiline-replies" bind:checked={live.general.multilineReplies} />
        </div>

        <hr class="divider" />

        <div class="subsection-label">Workflow</div>

        <div class="control-group checkbox-row">
          <label for="workflow-auto">Auto Mode</label>
          <input type="checkbox" id="workflow-auto" bind:checked={auto} />
        </div>

        <div class="control-group checkbox-row">
          <label for="workflow-streaming">Streaming</label>
          <input type="checkbox" id="workflow-streaming" bind:checked={streaming} />
        </div>

        <div class="control-group checkbox-row">
          <label for="workflow-stats">Show Stats</label>
          <input type="checkbox" id="workflow-stats" bind:checked={showStats} />
        </div>

        <hr class="divider" />

        <div class="subsection-label">Stable Diffusion</div>

        <div class="control-group">
          <label for="sd-endpoint">SD Endpoint</label>
          <input id="sd-endpoint" type="text" bind:value={live.general.sdEndpoint} class="wide" />
        </div>

        <hr class="divider" />

        <button class="graph-btn" onclick={onOpenGraph}>Graph</button>
      </section>
    {/if}

    {#if activeTab === 'experiment'}
      <section class="section-body">
        <div class="control-group">
          <label for="temp">Temperature</label>
          <div class="input-row">
            <input id="temp" type="range" min="0.1" max="2" step="0.05" bind:value={live.experimentation.temperature} />
            <input type="number" min="0.1" max="2" step="0.05" bind:value={live.experimentation.temperature} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="top-p">Top-P</label>
          <div class="input-row">
            <input id="top-p" type="range" min="0" max="1" step="0.01" bind:value={live.experimentation.topP} />
            <input type="number" min="0" max="1" step="0.01" bind:value={live.experimentation.topP} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="top-k">Top-K</label>
          <div class="input-row">
            <input id="top-k" type="range" min="0" max="100" step="1" bind:value={live.experimentation.topK} />
            <input type="number" min="0" max="100" step="1" bind:value={live.experimentation.topK} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="rep-pen">Repetition Penalty</label>
          <div class="input-row">
            <input id="rep-pen" type="range" min="1" max="2" step="0.01" bind:value={live.experimentation.repetitionPenalty} />
            <input type="number" min="1" max="2" step="0.01" bind:value={live.experimentation.repetitionPenalty} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="max-len">Max Output Tokens</label>
          <div class="input-row">
            <input id="max-len" type="range" min="16" max="2048" step="16" bind:value={live.experimentation.maxLength} />
            <input type="number" min="16" max="2048" step="16" bind:value={live.experimentation.maxLength} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="ctx-size">Context Size</label>
          <div class="input-row">
            <input id="ctx-size" type="range" min="512" max="8192" step="256" bind:value={live.experimentation.contextSize} />
            <input type="number" min="512" max="8192" step="256" bind:value={live.experimentation.contextSize} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="min-p">Min-P</label>
          <div class="input-row">
            <input id="min-p" type="range" min="0" max="1" step="0.01" bind:value={live.experimentation.minP} />
            <input type="number" min="0" max="1" step="0.01" bind:value={live.experimentation.minP} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="presence-pen">Presence Penalty</label>
          <div class="input-row">
            <input id="presence-pen" type="range" min="-2" max="2" step="0.1" bind:value={live.experimentation.presencePenalty} />
            <input type="number" min="-2" max="2" step="0.1" bind:value={live.experimentation.presencePenalty} class="number-input" />
          </div>
        </div>

        <div class="control-group">
          <label for="sampler-seed">Sampler Seed</label>
          <input id="sampler-seed" type="number" min="-1" bind:value={live.experimentation.samplerSeed} class="number-input wide" />
        </div>
      </section>
    {/if}

    {#if activeTab === 'sd'}
      <section class="section-body">
        <div class="control-group">
          <label for="sd-style">Style Preset</label>
          <select id="sd-style" bind:value={live.sd.style}>
            {#each sdStyleOptions as styleName}
              <option value={styleName}>{styleName}</option>
            {/each}
          </select>
        </div>

        <div class="control-grid two-col">
          <div class="control-group">
            <label for="sd-steps">Steps (1-60)</label>
            <input 
              id="sd-steps" 
              type="number" 
              min="1" 
              max="60" 
              bind:value={live.sd.steps}
              oninput={(e) => { live.sd.steps = Math.max(1, Math.min(60, e.target.value)); }}
              class="number-input wide" 
            />
          </div>
          <div class="control-group">
            <label for="sd-cfg">CFG Scale (0.1-30)</label>
            <input 
              id="sd-cfg" 
              type="number" 
              min="0.1" 
              max="30" 
              step="0.5" 
              bind:value={live.sd.cfgScale}
              oninput={(e) => { live.sd.cfgScale = Math.max(0.1, Math.min(30, e.target.value)); }}
              class="number-input wide" 
            />
          </div>
        </div>

        <div class="control-grid two-col">
          <div class="control-group">
            <label for="sd-width">Width (>0)</label>
            <input 
              id="sd-width" 
              type="number" 
              min="1" 
              step="64" 
              bind:value={live.sd.width}
              oninput={(e) => { live.sd.width = Math.max(1, e.target.value); lastEditedDimension = 'width'; }}
              class="number-input wide" 
            />
          </div>
          <div class="control-group">
            <label for="sd-height">Height (>0)</label>
            <input 
              id="sd-height" 
              type="number" 
              min="1" 
              step="64" 
              bind:value={live.sd.height}
              oninput={(e) => { live.sd.height = Math.max(1, e.target.value); lastEditedDimension = 'height'; }}
              class="number-input wide" 
            />
          </div>
        </div>

        <div class="aspect-ratio-row">
          <button class="ratio-btn" onclick={() => applyAspectRatio('1:1')}>1:1</button>
          <button class="ratio-btn" onclick={() => applyAspectRatio('3:2')}>3:2</button>
          <button class="ratio-btn" onclick={() => applyAspectRatio('2:3')}>2:3</button>
        </div>

        <div class="control-group">
          <label for="sd-sampler">Sampler Name</label>
          <select id="sd-sampler" bind:value={live.sd.samplerName}>
            {#each samplerOptions as sampler}
              <option value={sampler}>{sampler}</option>
            {/each}
          </select>
        </div>

        <div class="control-group">
          <label for="sd-neg-extra">Negative Prompt Extra</label>
          <textarea id="sd-neg-extra" rows="3" bind:value={live.sd.negativePromptExtra} placeholder="Extra negatives appended after style template"></textarea>
        </div>
      </section>
    {/if}
  </div>

</div>

<style>
  .experimentation-panel {
    display: flex;
    flex-direction: column;
    background: #111827;
    border-right: 1px solid #1f2937;
    color: #e5e7eb;
    font-size: 12px;
    font-family: system-ui, -apple-system, sans-serif;
    height: 100vh;
    width: 300px;
    overflow: hidden;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.25);
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-bottom: 1px solid #1f2937;
    background: #0b1220;
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .tab-strip {
    display: flex;
    gap: 0.35rem;
  }

  .tab-btn {
    width: 2rem;
    height: 2rem;
    border-radius: 8px;
    border: 1px solid #334155;
    background: #0f172a;
    color: #e5e7eb;
    cursor: pointer;
    font-size: 1rem;
  }

  .tab-btn.active {
    border-color: #60a5fa;
    background: #1e3a8a;
  }

  .dirty-indicator {
    color: #ef4444;
    font-size: 16px;
  }

  .panel-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0.6rem;
  }

  .section-body {
    display: grid;
    gap: 0.65rem;
    background: #0f172a;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 0.7rem;
  }

  .control-grid.two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.55rem;
  }

  .control-group {
    display: grid;
    gap: 0.3rem;
  }

  .control-group label {
    font-size: 0.78rem;
    color: #cbd5e1;
  }

  .input-row {
    display: flex;
    gap: 0.35rem;
    align-items: center;
  }

  input[type='range'] {
    flex: 1;
  }

  input,
  select,
  textarea {
    background: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 0.35rem 0.45rem;
    font-size: 0.78rem;
  }

  .number-input {
    width: 74px;
    text-align: right;
  }

  .wide {
    width: 100%;
    box-sizing: border-box;
  }

  .checkbox-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .panel-actions {
    display: flex;
    gap: 0.45rem;
    padding: 0.5rem 0.65rem;
    border-bottom: 1px solid #1f2937;
    background: #0b1220;
    flex-shrink: 0;
  }

  .btn {
    flex: 1;
    border: 1px solid #3b82f6;
    background: #1d4ed8;
    color: #fff;
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    font-size: 0.78rem;
    cursor: pointer;
    font-weight: 600;
  }

  .btn-cancel {
    border-color: #64748b;
    background: #334155;
  }

  .btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .divider {
    border: none;
    border-top: 1px solid #374151;
    margin: 0.3rem 0;
  }

  .subsection-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.3rem;
    padding-top: 0.3rem;
  }

  .aspect-ratio-row {
    display: flex;
    gap: 0.4rem;
  }

  .ratio-btn {
    flex: 1;
    border: 1px solid #475569;
    background: #1e293b;
    color: #cbd5e1;
    border-radius: 6px;
    padding: 0.3rem 0.4rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }

  .ratio-btn:hover {
    border-color: #60a5fa;
    background: #0f172a;
    color: #93c5fd;
  }

  .graph-btn {
    width: 100%;
    border: 1px solid #475569;
    background: #1e293b;
    color: #cbd5e1;
    border-radius: 6px;
    padding: 0.45rem 0.6rem;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }

  .graph-btn:hover {
    border-color: #94a3b8;
    color: #f1f5f9;
  }

  @media (max-width: 980px) {
    .experimentation-panel {
      width: 260px;
    }
  }
</style>
