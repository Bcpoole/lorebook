<script>
  let {
    live = $bindable({}),
    saved = $bindable({}),
    isDirty = $bindable(false),
    sdStyleOptions = ['balanced'],
    onSave = () => {},
    onCancel = () => {},
  } = $props()

  let activeTab = $state('experiment')

  const defaults = {
    general: {
      outputFormat: 'markdown',
      multilineReplies: true,
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
      endpoint: 'http://127.0.0.1:7860',
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

  function handleSave() {
    onSave()
  }

  function handleCancel() {
    onCancel()
  }

  $effect.pre(() => {
    if (!live || Object.keys(live).length === 0 || !live.experimentation) {
      live = normalizeConfig(live)
    }

    if (!saved || Object.keys(saved).length === 0 || !saved.experimentation) {
      saved = normalizeConfig(saved)
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

        <div class="control-group">
          <label for="sd-endpoint">SD Endpoint</label>
          <input id="sd-endpoint" type="text" bind:value={live.sd.endpoint} class="wide" />
        </div>

        <div class="control-grid two-col">
          <div class="control-group">
            <label for="sd-steps">Steps</label>
            <input id="sd-steps" type="number" min="1" max="150" bind:value={live.sd.steps} class="number-input wide" />
          </div>
          <div class="control-group">
            <label for="sd-cfg">CFG Scale</label>
            <input id="sd-cfg" type="number" min="1" max="20" step="0.5" bind:value={live.sd.cfgScale} class="number-input wide" />
          </div>
        </div>

        <div class="control-grid two-col">
          <div class="control-group">
            <label for="sd-width">Width</label>
            <input id="sd-width" type="number" min="256" step="64" bind:value={live.sd.width} class="number-input wide" />
          </div>
          <div class="control-group">
            <label for="sd-height">Height</label>
            <input id="sd-height" type="number" min="256" step="64" bind:value={live.sd.height} class="number-input wide" />
          </div>
        </div>

        <div class="control-group">
          <label for="sd-sampler">Sampler Name</label>
          <input id="sd-sampler" type="text" bind:value={live.sd.samplerName} class="wide" />
        </div>

        <div class="control-group">
          <label for="sd-neg-extra">Negative Prompt Extra</label>
          <textarea id="sd-neg-extra" rows="3" bind:value={live.sd.negativePromptExtra} placeholder="Extra negatives appended after style template"></textarea>
        </div>
      </section>
    {/if}
  </div>

  <div class="panel-footer">
    <button class="btn btn-save" onclick={handleSave} disabled={!isDirty}>💾 Save</button>
    <button class="btn btn-cancel" onclick={handleCancel} disabled={!isDirty}>✕ Cancel</button>
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
    overflow-y: auto;
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

  .panel-footer {
    display: flex;
    gap: 0.45rem;
    padding: 0.65rem;
    border-top: 1px solid #1f2937;
    background: #0b1220;
    position: sticky;
    bottom: 0;
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

  @media (max-width: 980px) {
    .experimentation-panel {
      width: 260px;
    }
  }
</style>
