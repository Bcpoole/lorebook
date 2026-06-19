<script>
  /**
   * PersonaWizard - Multi-step wizard for creating personas
   *
   * Steps:
   * 1. High-level description input
   * 2. Generate/edit all system prompts
   * 3. Build avatar prompt and image
   * 4. Review and save
   */

  import { onMount } from 'svelte'
  import PromptRefineModal from './PromptRefineModal.svelte'

  let {
    onclose = () => {},
    oncreate = () => {},
  } = $props()

  const DEFAULT_PROMPTS = [
    { key: 'loremaster_system', name: 'Loremaster System', description: 'Prompt for world-building and setting generation' },
    { key: 'character_system', name: 'Character System', description: 'Prompt for character design' },
    { key: 'editor_system', name: 'Editor System', description: 'Prompt for quality review and critique' },
    { key: 'sd_prompt_system', name: 'SD Prompt System', description: 'Prompt for generating Stable Diffusion image prompts' },
    { key: 'review_summary_system', name: 'Review Summary System', description: 'Prompt for summarizing review changes' },
    { key: 'character_summary_system', name: 'Character Summary System', description: 'Prompt for generating one-line character summaries' },
    { key: 'character_related_system', name: 'Character Related System', description: 'Prompt for generating related characters' },
  ]

  const STEPS = ['Describe', 'Prompts', 'Avatar', 'Review']
  let currentStep = $state(0)
  let isLoading = $state(false)
  let loadingMessage = $state('')

  // Step 1: Description
  let personaDescription = $state('')
  let personaStyle = $state('balanced')

  // Step 2-5: Generated data
  let generatedPersona = $state({
    id: '',
    name: '',
    description: '',
    tags: [],
    avatar: '',
    prompts: DEFAULT_PROMPTS.map(p => ({ ...p, system_prompt: '' })),
  })

  let templatePrompts = $state([])
  let promptStateByKey = $state({})
  let avatarPrompt = $state('')
  let avatarSource = $state('')
  let sdConfig = $state({})
  let refinePromptKey = $state('')

  const currentStepLabel = $derived(STEPS[currentStep])
  const isFirstStep = $derived(currentStep === 0)
  const isLastStep = $derived(currentStep === STEPS.length - 1)
  const anyPromptGenerating = $derived(
    generatedPersona.prompts.some(p => promptStateByKey[p.key]?.status === 'generating')
  )
  const allPromptsReady = $derived(
    generatedPersona.prompts.every(p => p.system_prompt.trim().length > 0)
  )

  onMount(async () => {
    // Load template prompts
    try {
      const response = await fetch('/api/personas/template')
      if (response.ok) {
        const template = await response.json()
        templatePrompts = template.prompts
        const sourcePrompts = template.prompts?.length ? template.prompts : DEFAULT_PROMPTS
        generatedPersona.prompts = sourcePrompts.map(p => ({
          key: p.key,
          name: p.name,
          system_prompt: '',
          description: p.description,
        }))
        promptStateByKey = buildPromptState(generatedPersona.prompts)
      }
    } catch (err) {
      console.error('Failed to load template:', err)
    }

    try {
      const response = await fetch('/api/experimentation/load')
      if (response.ok) {
        const data = await response.json()
        sdConfig = data?.sd || {}
      }
    } catch (err) {
      console.error('Failed to load experimentation config:', err)
    }
  })

  function buildPromptState(prompts) {
    const state = {}
    for (const prompt of prompts) {
      state[prompt.key] = {
        status: 'pending',
        progress: 0,
        error: '',
        editing: false,
      }
    }
    return state
  }

  function generatePersonaId(name) {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .substring(0, 50)
  }

  function toTitleCase(text) {
    return text
      .trim()
      .split(/\s+/)
      .slice(0, 4)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ')
  }

  function initializePersonaMetaFromDescription() {
    const derivedName = toTitleCase(personaDescription) || 'New Persona'
    generatedPersona.name = derivedName
    generatedPersona.description = personaDescription.trim()
    generatedPersona.tags = [personaStyle, 'custom']
    generatedPersona.id = generatePersonaId(derivedName)
  }

  async function handleNext() {
    if (currentStep === 0) {
      if (!personaDescription.trim()) {
        alert('Please describe your persona')
        return
      }
      await generateAllPrompts()
      return
    }

    if (currentStep === 1 && !allPromptsReady) {
      alert('Please generate all prompts or fill remaining ones manually before continuing.')
      return
    } else if (currentStep < STEPS.length - 1) {
      currentStep++
    }
  }

  function handlePrev() {
    if (currentStep > 0) {
      currentStep--
    }
  }

  async function generatePrompt(promptKey, regenerate = false) {
    const prompt = generatedPersona.prompts.find(p => p.key === promptKey)
    if (!prompt) return

    promptStateByKey[promptKey] = {
      ...promptStateByKey[promptKey],
      status: 'generating',
      progress: 30,
      error: '',
    }

    try {
      const response = await fetch('/api/experimentation/generate-persona-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: personaDescription,
          style: personaStyle,
          prompt_key: prompt.key,
          template_value: getTemplateValue(prompt.key),
          existing_prompt: regenerate ? prompt.system_prompt : '',
        }),
      })

      if (!response.ok) {
        let detail = `Failed to generate ${prompt.name}`
        try {
          const errData = await response.json()
          detail = errData?.detail || detail
        } catch {
          // keep default
        }
        throw new Error(detail)
      }

      const data = await response.json()
      handlePromptChange(prompt.key, data.system_prompt || '')
      promptStateByKey[promptKey] = {
        ...promptStateByKey[promptKey],
        status: 'done',
        progress: 100,
        error: '',
      }
    } catch (err) {
      promptStateByKey[promptKey] = {
        ...promptStateByKey[promptKey],
        status: 'error',
        progress: 0,
        error: err?.message || 'Generation failed',
      }
    }
  }

  async function regeneratePrompt(promptKey) {
    await generatePrompt(promptKey, true)
  }

  function togglePromptEdit(promptKey) {
    const current = promptStateByKey[promptKey] || {}
    promptStateByKey[promptKey] = {
      ...current,
      editing: !current.editing,
    }
  }

  function openRefinePrompt(promptKey) {
    refinePromptKey = promptKey
  }

  function closeRefinePrompt() {
    refinePromptKey = ''
  }

  function applyRefinedPrompt(newPrompt) {
    if (!refinePromptKey) return
    handlePromptChange(refinePromptKey, newPrompt)
    promptStateByKey[refinePromptKey] = {
      ...promptStateByKey[refinePromptKey],
      status: 'done',
      error: '',
      editing: true,
    }
    closeRefinePrompt()
  }

  async function requestWizardRefineSuggestion({ instruction, currentValue }) {
    if (!refinePromptKey) {
      throw new Error('No active prompt selected')
    }
    const activePrompt = generatedPersona.prompts.find((p) => p.key === refinePromptKey)
    if (!activePrompt) {
      throw new Error('Prompt not found')
    }

    const response = await fetch('/api/experimentation/refine-persona-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt_key: activePrompt.key,
        current_prompt: currentValue,
        template_value: getTemplateValue(activePrompt.key),
        instruction,
        description: generatedPersona.description || personaDescription,
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

  async function generateAllPrompts() {
    isLoading = true
    loadingMessage = 'Generating system prompts...'
    currentStep = 1
    initializePersonaMetaFromDescription()
    promptStateByKey = buildPromptState(generatedPersona.prompts)

    try {
      for (const prompt of generatedPersona.prompts) {
        await generatePrompt(prompt.key)
      }
      avatarPrompt = ''
    } finally {
      isLoading = false
      loadingMessage = ''
    }
  }

  function getSdSystemPrompt() {
    return generatedPersona.prompts.find((p) => p.key === 'sd_prompt_system')?.system_prompt || ''
  }

  async function generateAvatarPrompt(regenerate = false) {
    isLoading = true
    loadingMessage = 'Generating avatar prompt...'
    try {
      const response = await fetch('/api/experimentation/generate-avatar-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          persona_name: generatedPersona.name,
          persona_description: generatedPersona.description || personaDescription,
          style: personaStyle,
          sd_prompt_system: getSdSystemPrompt(),
          existing_prompt: regenerate ? avatarPrompt : '',
        }),
      })
      if (!response.ok) {
        let detail = 'Failed to generate avatar prompt'
        try {
          const errData = await response.json()
          detail = errData?.detail || detail
        } catch {}
        throw new Error(detail)
      }
      const data = await response.json()
      avatarPrompt = data.prompt || ''
    } catch (err) {
      alert('Avatar prompt generation failed: ' + err.message)
    } finally {
      isLoading = false
      loadingMessage = ''
    }
  }

  async function generateImage() {
    isLoading = true
    loadingMessage = 'Generating avatar image...'

    try {
      const response = await fetch('/api/experimentation/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: avatarPrompt,
          sd_config: sdConfig,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to generate image')
      }

      const data = await response.json()
      generatedPersona.avatar = data.avatar || ''
      avatarSource = generatedPersona.avatar ? 'generated' : avatarSource
    } catch (err) {
      alert('Avatar generation failed: ' + err.message)
    } finally {
      isLoading = false
      loadingMessage = ''
    }
  }

  function handleAvatarUpload(event) {
    const file = event?.target?.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file.')
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      generatedPersona.avatar = typeof reader.result === 'string' ? reader.result : ''
      avatarSource = generatedPersona.avatar ? 'uploaded' : avatarSource
    }
    reader.onerror = () => {
      alert('Failed to read uploaded image.')
    }
    reader.readAsDataURL(file)
  }

  function handlePromptChange(promptKey, newValue) {
    const idx = generatedPersona.prompts.findIndex(p => p.key === promptKey)
    if (idx >= 0) {
      generatedPersona.prompts[idx].system_prompt = newValue
      if (newValue.trim().length > 0 && promptStateByKey[promptKey]?.status !== 'generating') {
        promptStateByKey[promptKey] = {
          ...promptStateByKey[promptKey],
          status: 'done',
          progress: 100,
          error: '',
        }
      }
    }
  }

  function getTemplateValue(promptKey) {
    const prompt = templatePrompts.find(p => p.key === promptKey)
    return prompt?.system_prompt ?? ''
  }

  async function handleFinish() {
    isLoading = true
    loadingMessage = 'Creating persona...'

    try {
      oncreate(new CustomEvent('create', {
        detail: {
          persona: {
            id: generatedPersona.id,
            name: generatedPersona.name,
            description: generatedPersona.description,
            tags: generatedPersona.tags,
            avatar: generatedPersona.avatar,
            prompts: generatedPersona.prompts.map(p => ({
              key: p.key,
              name: p.name,
              system_prompt: p.system_prompt,
              description: p.description,
            })),
          },
        },
      }))
      onclose()
    } finally {
      isLoading = false
    }
  }

  function handleClickOutside(e) {
    if (e.target.classList.contains('wizard-overlay')) {
      onclose()
    }
  }
</script>

<div class="wizard-overlay" onclick={handleClickOutside}>
  <div class="wizard" onclick={(e) => e.stopPropagation()}>
    <div class="wizard-header">
      <h2>✨ Create Persona with Wizard</h2>
      <button
        type="button"
        class="close-btn"
        onclick={onclose}
        aria-label="Close"
        disabled={isLoading}
      >
        ✕
      </button>
    </div>

    <div class="progress-bar">
      {#each STEPS as step, idx}
        <div
          class="step"
          class:active={idx === currentStep}
          class:completed={idx < currentStep}
        >
          <div class="step-number">{idx + 1}</div>
          <div class="step-label">{step}</div>
        </div>
        {#if idx < STEPS.length - 1}
          <div class="step-connector" class:active={idx < currentStep}></div>
        {/if}
      {/each}
    </div>

    <div class="wizard-content">
      {#if currentStep === 0}
        <!-- Step 1: Describe -->
        <div class="step-content">
          <h3>Describe Your Persona</h3>
          <p>
            Tell us about the persona you want to create. This will be used to generate custom prompts.
          </p>

          <div class="form-group">
            <label for="description">Persona Description *</label>
            <textarea
              id="description"
              class="input-large"
              placeholder="Example: A mystical worldbuilder who creates dark fantasy settings with emphasis on politics, intrigue, and moral ambiguity..."
              bind:value={personaDescription}
              rows={6}
            ></textarea>
          </div>

          <div class="form-group">
            <label for="style">Style / Tone</label>
            <select id="style" bind:value={personaStyle}>
              <option value="balanced">Balanced</option>
              <option value="creative">Creative & Imaginative</option>
              <option value="analytical">Analytical & Structured</option>
              <option value="whimsical">Whimsical & Playful</option>
              <option value="dark">Dark & Serious</option>
            </select>
          </div>
        </div>
      {:else if currentStep === 1}
        <!-- Step 2: Generation -->
        <div class="step-content">
          <h3>Generate Persona Prompts</h3>
          <p>Each prompt is generated independently. You can regenerate ♻️ or edit ✏️ each one.</p>

          <div class="form-group">
            <label for="name">Name</label>
            <input
              id="name"
              type="text"
              placeholder="Persona name"
              bind:value={generatedPersona.name}
              onchange={() => {
                generatedPersona.id = generatePersonaId(generatedPersona.name)
              }}
            />
          </div>

          <div class="form-group">
            <label for="persona-id">ID</label>
            <input
              id="persona-id"
              type="text"
              placeholder="persona-id"
              bind:value={generatedPersona.id}
            />
          </div>

          <div class="form-group">
            <label for="desc">Description</label>
            <textarea
              id="desc"
              placeholder="Persona description"
              bind:value={generatedPersona.description}
              rows={3}
            ></textarea>
          </div>

          <div class="form-group">
            <label for="tags">Tags</label>
            <input
              id="tags"
              type="text"
              placeholder="tag1, tag2, tag3"
              value={generatedPersona.tags.join(', ')}
              onchange={(e) => {
                generatedPersona.tags = e.target.value
                  .split(',')
                  .map(t => t.trim())
                  .filter(t => t)
              }}
            />
          </div>

          <div class="prompt-generation-list">
            {#each generatedPersona.prompts as prompt (prompt.key)}
              {@const pState = promptStateByKey[prompt.key] || { status: 'pending', progress: 0, error: '', editing: false }}
              <div class="prompt-generation-item">
                <div class="prompt-generation-header">
                  <div>
                    <h4>{prompt.name}</h4>
                    <p>{prompt.description}</p>
                  </div>
                  <div class="prompt-generation-actions">
                    <button
                      type="button"
                      class="mini-btn"
                      onclick={() => togglePromptEdit(prompt.key)}
                      disabled={pState.status === 'generating'}
                      title="Toggle edit mode"
                    >
                      ✏️
                    </button>
                    <button
                      type="button"
                      class="mini-btn"
                      onclick={() => regeneratePrompt(prompt.key)}
                      disabled={pState.status === 'generating'}
                      title="Regenerate prompt"
                    >
                      ♻️
                    </button>
                    <button
                      type="button"
                      class="mini-btn"
                      onclick={() => openRefinePrompt(prompt.key)}
                      disabled={pState.status === 'generating'}
                      title="Ask AI to refine"
                    >
                      ✨
                    </button>
                  </div>
                </div>

                <div class="prompt-progress">
                  <div
                    class="prompt-progress-fill"
                    class:generating={pState.status === 'generating'}
                    style={`width: ${pState.status === 'done' ? 100 : pState.status === 'generating' ? 70 : 0}%`}
                  ></div>
                </div>

                {#if pState.error}
                  <p class="prompt-error">{pState.error}</p>
                {/if}

                <textarea
                  class="prompt-preview"
                  rows={4}
                  value={prompt.system_prompt}
                  placeholder={getTemplateValue(prompt.key)}
                  disabled={pState.status === 'generating' || !pState.editing}
                  onchange={(e) => handlePromptChange(prompt.key, e.target.value)}
                ></textarea>
              </div>
            {/each}
          </div>

          <div class="generation-footer-actions">
            <button
              type="button"
              class="btn btn-secondary"
              onclick={generateAllPrompts}
              disabled={isLoading || anyPromptGenerating}
            >
              ♻️ Regenerate All
            </button>
          </div>
        </div>
      {:else if currentStep === 2}
        <!-- Step 3: Avatar -->
        <div class="step-content">
          <h3>Avatar</h3>
          <p>Create an avatar prompt first, tweak it, then generate an image or upload one.</p>

          <div class="avatar-layout">
            <div class="avatar-controls">
              <div class="form-group">
                <label for="avatar-prompt">Avatar Prompt</label>
                <textarea
                  id="avatar-prompt"
                  rows={6}
                  placeholder="Generate an avatar prompt, then refine it here..."
                  bind:value={avatarPrompt}
                ></textarea>
              </div>

              <div class="avatar-actions">
                <button
                  type="button"
                  class="btn btn-secondary"
                  onclick={() => generateAvatarPrompt(false)}
                  disabled={isLoading}
                >
                  ✨ Generate Avatar Prompt
                </button>
                <button
                  type="button"
                  class="btn btn-secondary"
                  onclick={() => generateAvatarPrompt(true)}
                  disabled={isLoading || !avatarPrompt.trim()}
                >
                  ♻️ Regenerate Prompt
                </button>
                <button
                  type="button"
                  class="btn btn-primary"
                  onclick={generateImage}
                  disabled={isLoading || !avatarPrompt.trim()}
                >
                  🎨 Generate Avatar Image
                </button>
              </div>

              <div class="form-group">
                <label for="avatar-upload">Upload Avatar (overrides current avatar)</label>
                <input id="avatar-upload" type="file" accept="image/*" onchange={handleAvatarUpload} />
              </div>
            </div>

            <div class="avatar-preview-panel">
              <div class="image-preview">
                {#if generatedPersona.avatar}
                  <img src={generatedPersona.avatar} alt="Avatar preview" />
                {:else}
                  <div class="placeholder">
                    <span>📷 No image yet</span>
                  </div>
                {/if}
              </div>

              {#if generatedPersona.avatar}
                <p class="avatar-source-note">
                  Current avatar source: <strong>{avatarSource || 'manual'}</strong>. Generating or uploading replaces it.
                </p>
              {/if}
            </div>
          </div>

          {#if isLoading}
            <div class="loading-state">
              <div class="spinner"></div>
              <p>{loadingMessage}</p>
            </div>
          {/if}
        </div>
      {:else if currentStep === 3}
        <!-- Step 4: Review -->
        <div class="step-content">
          <h3>Review & Finish</h3>
          <div class="review-section">
            <div class="review-item">
              <strong>Name:</strong> {generatedPersona.name}
            </div>
            <div class="review-item">
              <strong>ID:</strong> {generatedPersona.id}
            </div>
            <div class="review-item">
              <strong>Description:</strong> {generatedPersona.description}
            </div>
            <div class="review-item">
              <strong>Tags:</strong> {generatedPersona.tags.join(', ') || 'None'}
            </div>
            <div class="review-item">
              <strong>Prompts:</strong> {generatedPersona.prompts.length} custom prompts
            </div>
          </div>
          {#if isLoading}
            <div class="loading-state">
              <div class="spinner"></div>
              <p>{loadingMessage}</p>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <div class="wizard-footer">
      <button
        type="button"
        class="btn btn-secondary"
        onclick={handlePrev}
        disabled={isFirstStep || isLoading}
      >
        ← Back
      </button>

      {#if isLastStep}
        <button
          type="button"
          class="btn btn-primary"
          onclick={handleFinish}
          disabled={isLoading}
        >
          {isLoading ? '💾 Creating...' : '✓ Create Persona'}
        </button>
      {:else}
        <button
          type="button"
          class="btn btn-primary"
          onclick={handleNext}
          disabled={
            isLoading ||
            (currentStep === 0 && !personaDescription.trim()) ||
            (currentStep === 1 && (!allPromptsReady || anyPromptGenerating))
          }
        >
          {isLoading ? '⏳ Generating...' : currentStep === 2 ? (generatedPersona.avatar ? 'Next →' : 'Skip →') : 'Next →'}
        </button>
      {/if}
    </div>
  </div>
</div>

{#if refinePromptKey}
  {@const activePrompt = generatedPersona.prompts.find((p) => p.key === refinePromptKey)}
  {#if activePrompt}
    <PromptRefineModal
      title={`Refine — ${activePrompt.name}`}
      currentValue={activePrompt.system_prompt}
      currentLabel="Working Version (Read-only)"
      suggestedLabel="Suggested Version"
      instructionLabel="How should AI update this prompt?"
      instructionPlaceholder="Example: Keep intent but make it shorter and more directive."
      requestSuggestion={requestWizardRefineSuggestion}
      onapply={applyRefinedPrompt}
      onclose={closeRefinePrompt}
    />
  {/if}
{/if}

<style>
  .wizard-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(2, 6, 23, 0.8);
    backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    padding: 1rem;
  }

  .wizard {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 16px;
    box-shadow: 0 25px 60px rgba(2, 6, 23, 0.6);
    display: flex;
    flex-direction: column;
    max-width: 980px;
    width: 100%;
    max-height: 85vh;
  }

  .wizard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #334155;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  }

  .wizard-header h2 {
    margin: 0;
    font-size: 1.35rem;
    color: #f8fafc;
    letter-spacing: 0.02em;
  }

  .close-btn {
    padding: 0.5rem;
    background: transparent;
    border: 1px solid transparent;
    color: #94a3b8;
    font-size: 1.5rem;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.15s ease;
  }

  .close-btn:hover:not(:disabled) {
    color: #f8fafc;
    background: rgba(71, 85, 105, 0.2);
  }

  .progress-bar {
    display: flex;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #334155;
    background: rgba(6, 182, 212, 0.05);
    gap: 0.5rem;
  }

  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    flex: 1;
    position: relative;
  }

  .step-number {
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: rgba(51, 65, 85, 0.5);
    border: 2px solid #334155;
    color: #cbd5e1;
    font-weight: 600;
    font-size: 0.9rem;
    transition: all 0.2s ease;
  }

  .step.active .step-number {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    border-color: #1d4ed8;
    color: #eff6ff;
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
  }

  .step.completed .step-number {
    background: rgba(34, 197, 94, 0.15);
    border-color: #22c55e;
    color: #86efac;
  }

  .step-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .step.active .step-label {
    color: #0ea5e9;
  }

  .step-connector {
    position: absolute;
    top: 1.25rem;
    left: 50%;
    right: -50%;
    height: 2px;
    background: #334155;
    transform: translateX(50%);
    z-index: -1;
    width: 100%;
  }

  .step-connector.active {
    background: #22c55e;
  }

  .wizard-content {
    flex: 1;
    overflow-y: auto;
    padding: 2rem;
  }

  .step-content {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .step-content h3 {
    margin: 0;
    font-size: 1.2rem;
    color: #f8fafc;
    font-weight: 600;
  }

  .step-content p {
    margin: 0;
    color: #94a3b8;
    font-size: 0.95rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .form-group label {
    font-weight: 600;
    color: #cbd5e1;
    font-size: 0.9rem;
  }

  .form-group input,
  .form-group textarea,
  .form-group select {
    padding: 0.75rem 1rem;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #1e293b;
    color: #e2e8f0;
    font-size: 0.95rem;
    font-family: inherit;
    transition: all 0.15s ease;
  }

  .form-group input:focus,
  .form-group textarea:focus,
  .form-group select:focus {
    outline: none;
    border-color: #0ea5e9;
    background: #1a2332;
    box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
  }

  .input-large {
    resize: vertical;
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 2rem;
    color: #94a3b8;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #334155;
    border-top-color: #2563eb;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .image-preview {
    border: 2px dashed #334155;
    border-radius: 8px;
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: rgba(6, 182, 212, 0.05);
  }

  .image-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
    font-size: 2rem;
  }

  .prompt-generation-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .prompt-generation-item {
    border: 1px solid #334155;
    border-radius: 10px;
    background: rgba(15, 23, 42, 0.6);
    padding: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }

  .prompt-generation-header {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .prompt-generation-header h4 {
    margin: 0;
    color: #e2e8f0;
    font-size: 0.95rem;
  }

  .prompt-generation-header p {
    margin: 0.25rem 0 0 0;
    color: #94a3b8;
    font-size: 0.8rem;
  }

  .prompt-generation-actions {
    display: flex;
    gap: 0.4rem;
  }

  .mini-btn {
    border: 1px solid #334155;
    background: rgba(30, 41, 59, 0.8);
    color: #cbd5e1;
    border-radius: 6px;
    padding: 0.35rem 0.55rem;
    cursor: pointer;
  }

  .mini-btn:hover:not(:disabled) {
    background: rgba(51, 65, 85, 0.8);
  }

  .mini-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .prompt-progress {
    width: 100%;
    height: 7px;
    border-radius: 999px;
    background: rgba(51, 65, 85, 0.45);
    overflow: hidden;
  }

  .prompt-progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #0ea5e9, #2563eb);
    transition: width 0.25s ease;
  }

  .prompt-progress-fill.generating {
    background: linear-gradient(
      90deg,
      #0ea5e9 0%,
      #38bdf8 25%,
      #2563eb 50%,
      #38bdf8 75%,
      #0ea5e9 100%
    );
    background-size: 200% 100%;
    animation: loadingBar 1s linear infinite;
  }

  @keyframes loadingBar {
    from {
      background-position: 200% 0;
    }
    to {
      background-position: 0 0;
    }
  }

  .prompt-preview {
    width: 100%;
    background: #0b1220;
    border: 1px solid #334155;
    color: #dbeafe;
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
    font-size: 0.85rem;
    line-height: 1.4;
    resize: vertical;
    font-family: inherit;
  }

  .prompt-preview:disabled {
    color: #93c5fd;
    opacity: 0.8;
  }

  .prompt-error {
    margin: 0;
    color: #fca5a5;
    font-size: 0.82rem;
    font-weight: 600;
  }

  .generation-footer-actions {
    display: flex;
    justify-content: flex-end;
  }

  .avatar-actions {
    display: flex;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .avatar-layout {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 1.2rem;
    align-items: start;
  }

  .avatar-controls {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }

  .avatar-preview-panel {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .avatar-source-note {
    margin: 0;
    color: #93c5fd;
    font-size: 0.85rem;
    background: rgba(37, 99, 235, 0.12);
    border: 1px solid rgba(37, 99, 235, 0.3);
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
  }

  .review-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.5rem;
    background: rgba(6, 182, 212, 0.05);
    border: 1px solid #334155;
    border-radius: 8px;
  }

  .review-item {
    display: flex;
    gap: 0.5rem;
    color: #cbd5e1;
    font-size: 0.95rem;
  }

  .review-item strong {
    color: #f8fafc;
    min-width: 8rem;
  }

  .wizard-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.5rem;
    border-top: 1px solid #334155;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  }

  .btn {
    padding: 0.7rem 1.4rem;
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }

  .btn-primary {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: #eff6ff;
    border-color: #1d4ed8;
  }

  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #1d4ed8, #1e40af);
    box-shadow: 0 8px 16px rgba(37, 99, 235, 0.3);
  }

  .btn-secondary {
    background: rgba(51, 65, 85, 0.4);
    color: #cbd5e1;
    border-color: #334155;
  }

  .btn-secondary:hover:not(:disabled) {
    background: rgba(71, 85, 105, 0.5);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 600px) {
    .wizard {
      max-width: 100%;
      max-height: 100vh;
      border-radius: 0;
    }

    .progress-bar {
      padding: 1rem;
      gap: 0.25rem;
    }

    .step-label {
      display: none;
    }

    .wizard-content {
      padding: 1.5rem;
      max-height: calc(100vh - 220px);
    }
  }

  @media (max-width: 900px) {
    .avatar-layout {
      grid-template-columns: 1fr;
    }
  }
</style>
