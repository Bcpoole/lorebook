<script>
  let {
    live = $bindable({}),
    saved = $bindable({}),
    isDirty = $bindable(false),
    sdStyleOptions = ['balanced'],
    sdStyleData = {},
    auto = $bindable(false),
    streaming = $bindable(true),
    showStats = $bindable(false),
    collapsed = false,
    onSave = () => {},
    onCancel = () => {},
    onSaveSd = () => {},
    onCancelSd = () => {},
    onOpenGraph = () => {},
    onToggleCollapse = () => {},
  } = $props()

  let activeTab = $state('experiment')
  let lastEditedDimension = $state(null)

  let selectedStyleData = $derived(sdStyleData[live?.sd?.style] ?? null)
  let uiShellToneOpen = $state(false)
  let bgImageUploading = $state(false)
  let bgImageUploadError = $state('')

  const samplerOptions = [
    'DPM++ 2M',
    'DPM++ 2M Karras',
    'Euler',
    'Euler A',
    'DPM++ SDE',
  ]

  const uiShellToneOptions = [
    { value: 'deep-slate', label: 'Deep Slate', hex: '#1E2D31' },
    { value: 'teal-slate', label: 'Teal Slate', hex: '#22363B' },
    { value: 'ocean-gray', label: 'Ocean Gray', hex: '#274046' },
    { value: 'misty-teal', label: 'Misty Teal', hex: '#2B454B' },
  ]

  let selectedUiShellToneOption = $derived.by(() => {
    const selectedValue = live?.general?.uiShellTone ?? defaults.general.uiShellTone
    return (
      uiShellToneOptions.find((option) => option.value === selectedValue)
      ?? uiShellToneOptions[0]
    )
  })

  const defaults = {
    general: {
      outputFormat: 'markdown',
      multilineReplies: true,
      auto: false,
      streaming: true,
      showStats: false,
      llmEndpoint: 'http://localhost:5001',
      sdEndpoint: 'http://127.0.0.1:7860',
      persona: 'blank',
      addCopyTagOnDuplicate: true,
      uiShellTone: 'teal-slate',
      uiShellImage: '',
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
      negativePrompt: '',
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

  function chooseUiShellTone(value) {
    live.general.uiShellTone = value
    uiShellToneOpen = false
  }

  async function uploadBackgroundImage(event) {
    const file = event.target.files?.[0]
    if (!file) return
    bgImageUploadError = ''
    bgImageUploading = true
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/user-assets/upload/background', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail ?? `Upload failed (${res.status})`)
      }
      const { url } = await res.json()
      live.general.uiShellImage = url
    } catch (e) {
      bgImageUploadError = e.message ?? 'Upload failed'
    } finally {
      bgImageUploading = false
      event.target.value = ''
    }
  }

  function clearBackgroundImage() {
    live.general.uiShellImage = ''
    bgImageUploadError = ''
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

<div class="experimentation-panel" class:collapsed>
  {#if !collapsed}
    <div class="panel-header">
      <div class="header-main">
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
      <button class="collapse-toggle-btn" type="button" title="Collapse settings panel" aria-label="Collapse settings panel" onclick={onToggleCollapse}>
        ⟨
      </button>
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

        <div class="control-group">
          <label for="ui-shell-tone">UI Shell Tone</label>
          <div class="ui-shell-tone-row">
            <details class="tone-dropdown" bind:open={uiShellToneOpen}>
              <summary class="tone-dropdown-trigger" id="ui-shell-tone" aria-label="UI shell tone">
                <span class="tone-dropdown-trigger-left">
                  <span class="tone-preview-swatch" style={`background:${selectedUiShellToneOption.hex}`}></span>
                  <span>{selectedUiShellToneOption.label} ({selectedUiShellToneOption.hex})</span>
                </span>
                <span class="tone-dropdown-caret" aria-hidden="true">▾</span>
              </summary>
              <div class="tone-dropdown-menu" role="listbox" aria-label="UI shell tone options">
                {#each uiShellToneOptions as option}
                  <button
                    type="button"
                    class="tone-option-btn"
                    class:active={live.general.uiShellTone === option.value}
                    onclick={() => chooseUiShellTone(option.value)}
                    role="option"
                    aria-selected={live.general.uiShellTone === option.value}
                  >
                    <span class="tone-preview-swatch" style={`background:${option.hex}`}></span>
                    <span class="tone-option-label">{option.label} ({option.hex})</span>
                  </button>
                {/each}
              </div>
            </details>
          </div>
        </div>

        <div class="control-group">
          <label for="bg-image-upload">Background Image</label>
          <div class="bg-image-row">
            {#if live.general?.uiShellImage}
              <div class="bg-image-preview-row">
                <img class="bg-image-thumb" src={live.general.uiShellImage} alt="Background preview" />
                <button type="button" class="bg-image-clear-btn" onclick={clearBackgroundImage} title="Remove background image">✕</button>
              </div>
            {:else}
              <label class="bg-image-upload-label" for="bg-image-upload">
                {bgImageUploading ? 'Uploading…' : 'Choose image…'}
              </label>
              <input
                id="bg-image-upload"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                class="bg-image-file-input"
                onchange={uploadBackgroundImage}
                disabled={bgImageUploading}
              />
            {/if}
            {#if bgImageUploadError}
              <p class="bg-image-error">{bgImageUploadError}</p>
            {/if}
          </div>
        </div>

        <div class="control-group checkbox-row">
          <label for="multiline-replies">Allow Multiline Replies</label>
          <label class="toggle-switch" for="multiline-replies">
            <input class="toggle-switch-input" type="checkbox" id="multiline-replies" bind:checked={live.general.multilineReplies} />
            <span class="toggle-switch-slider" aria-hidden="true"></span>
          </label>
        </div>

        <div class="control-group checkbox-row">
          <label for="duplicate-copy-tag">Duplicate adds "copy" tag</label>
          <label class="toggle-switch" for="duplicate-copy-tag">
            <input class="toggle-switch-input" type="checkbox" id="duplicate-copy-tag" bind:checked={live.general.addCopyTagOnDuplicate} />
            <span class="toggle-switch-slider" aria-hidden="true"></span>
          </label>
        </div>

        <hr class="divider" />

        <div class="subsection-label">Workflow</div>

        <div class="control-group checkbox-row">
          <label for="workflow-auto">Auto Mode</label>
          <label class="toggle-switch" for="workflow-auto">
            <input class="toggle-switch-input" type="checkbox" id="workflow-auto" bind:checked={auto} />
            <span class="toggle-switch-slider" aria-hidden="true"></span>
          </label>
        </div>

        <div class="control-group checkbox-row">
          <label for="workflow-streaming">Streaming</label>
          <label class="toggle-switch" for="workflow-streaming">
            <input class="toggle-switch-input" type="checkbox" id="workflow-streaming" bind:checked={streaming} />
            <span class="toggle-switch-slider" aria-hidden="true"></span>
          </label>
        </div>

        <div class="control-group checkbox-row">
          <label for="workflow-stats">Show Stats</label>
          <label class="toggle-switch" for="workflow-stats">
            <input class="toggle-switch-input" type="checkbox" id="workflow-stats" bind:checked={showStats} />
            <span class="toggle-switch-slider" aria-hidden="true"></span>
          </label>
        </div>

        <hr class="divider" />

        <div class="subsection-label">APIs</div>

        <div class="control-group">
          <label for="llm-endpoint">LLM Endpoint</label>
          <input id="llm-endpoint" type="text" bind:value={live.general.llmEndpoint} class="wide" />
        </div>

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

        {#if selectedStyleData}
          <div class="control-group">
            <label>Style Prompt</label>
            <textarea class="style-preview" readonly rows="3">{selectedStyleData.prompt}</textarea>
          </div>
          <div class="control-group">
            <label>Style Negative Prompt</label>
            <textarea class="style-preview" readonly rows="3">{selectedStyleData.negative_prompt}</textarea>
          </div>
        {/if}

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
          <label for="sd-neg-prompt">Negative Prompt</label>
          <textarea
            id="sd-neg-prompt"
            rows="3"
            bind:value={live.sd.negativePrompt}
            placeholder="Appended into the style preset's negative prompt template"
          ></textarea>
        </div>
      </section>
    {/if}
    </div>
  {/if}
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
    width: 100%;
    overflow: hidden;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.25);
    transition: width 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    min-width: 0;
  }

  .experimentation-panel.collapsed {
    width: 0;
    border-right-color: transparent;
    box-shadow: none;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 10px 12px;
    border-bottom: 1px solid #1f2937;
    background: #0b1220;
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .header-main {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;
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

  .collapse-toggle-btn {
    border: 1px solid #334155;
    background: #0f172a;
    color: #e5e7eb;
    width: 1.95rem;
    height: 1.95rem;
    border-radius: 8px;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    flex: 0 0 auto;
  }

  .collapse-toggle-btn:hover {
    border-color: #60a5fa;
    color: #93c5fd;
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

  .ui-shell-tone-row {
    display: block;
  }

  .tone-dropdown {
    flex: 1;
    position: relative;
  }

  .tone-dropdown-trigger {
    list-style: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.45rem;
    background: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 0.35rem 0.45rem;
    font-size: 0.78rem;
    cursor: pointer;
    user-select: none;
  }

  .tone-dropdown-trigger::-webkit-details-marker {
    display: none;
  }

  .tone-dropdown-trigger-left {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-width: 0;
  }

  .tone-dropdown-caret {
    color: #94a3b8;
    font-size: 0.75rem;
    transition: transform 0.16s ease;
  }

  .tone-dropdown[open] .tone-dropdown-caret {
    transform: rotate(180deg);
  }

  .tone-dropdown-menu {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    display: grid;
    gap: 0.2rem;
    border: 1px solid #374151;
    border-radius: 8px;
    background: #0f172a;
    padding: 0.25rem;
    z-index: 15;
    box-shadow: 0 10px 24px rgba(2, 6, 23, 0.45);
  }

  .tone-option-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    width: 100%;
    border: 1px solid transparent;
    border-radius: 6px;
    background: rgba(30, 41, 59, 0.45);
    color: #e2e8f0;
    padding: 0.32rem 0.4rem;
    font-size: 0.76rem;
    text-align: left;
    cursor: pointer;
  }

  .tone-option-btn:hover {
    border-color: #475569;
    background: rgba(51, 65, 85, 0.55);
  }

  .tone-option-btn.active {
    border-color: #3b82f6;
    background: rgba(37, 99, 235, 0.25);
  }

  .tone-option-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tone-preview-swatch {
    width: 0.9rem;
    height: 0.9rem;
    border-radius: 4px;
    border: 1px solid rgba(148, 163, 184, 0.45);
    flex: 0 0 auto;
  }

  input[type='range'] {
    flex: 1;
  }

  /* Background image upload control */
  .bg-image-row {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .bg-image-upload-label {
    display: inline-block;
    background: #111827;
    color: #94a3b8;
    border: 1px dashed #374151;
    border-radius: 6px;
    padding: 0.35rem 0.6rem;
    font-size: 0.78rem;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }

  .bg-image-upload-label:hover {
    border-color: #60a5fa;
    color: #93c5fd;
  }

  .bg-image-file-input {
    display: none;
  }

  .bg-image-preview-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .bg-image-thumb {
    width: 64px;
    height: 36px;
    object-fit: cover;
    border-radius: 5px;
    border: 1px solid #334155;
  }

  .bg-image-clear-btn {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 5px;
    padding: 0.2rem 0.45rem;
    font-size: 0.7rem;
    cursor: pointer;
    line-height: 1;
  }

  .bg-image-clear-btn:hover {
    background: rgba(239, 68, 68, 0.3);
    border-color: #f87171;
  }

  .bg-image-error {
    color: #f87171;
    font-size: 0.72rem;
    margin: 0;
  }

  input:not([type='checkbox']),
  select,
  textarea {
    background: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 0.35rem 0.45rem;
    font-size: 0.78rem;
  }

  .style-preview {
    width: 100%;
    box-sizing: border-box;
    resize: none;
    cursor: default;
    opacity: 0.75;
    font-family: monospace;
    font-size: 0.72rem;
    line-height: 1.4;
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

  .toggle-switch {
    position: relative;
    display: inline-flex;
    width: 42px;
    height: 24px;
    cursor: pointer;
  }

  .toggle-switch-input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
  }

  .toggle-switch-slider {
    width: 100%;
    height: 100%;
    background: #334155;
    border: 1px solid #475569;
    border-radius: 9999px;
    transition: background-color 0.2s ease, border-color 0.2s ease;
    box-sizing: border-box;
    position: relative;
  }

  .toggle-switch-slider::before {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #e2e8f0;
    transition: transform 0.2s ease;
  }

  .toggle-switch-input:checked + .toggle-switch-slider {
    background: #2563eb;
    border-color: #3b82f6;
  }

  .toggle-switch-input:checked + .toggle-switch-slider::before {
    transform: translateX(18px);
  }

  .toggle-switch-input:focus-visible + .toggle-switch-slider {
    outline: 2px solid #93c5fd;
    outline-offset: 2px;
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
      width: 100%;
    }
  }
</style>
