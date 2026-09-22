<script>
  import { onDestroy } from 'svelte'

  import MarkdownBlock from './MarkdownBlock.svelte'
  import AgentReviewControls from './AgentReviewControls.svelte'
  import StoryOpeningsModule from './StoryOpeningsModule.svelte'
  import StorySectionModule from './StorySectionModule.svelte'

  const STORY_IMAGE_SECTIONS = ['characters_artifact', 'locations', 'objects']
  const STORY_FIELD_TOOLTIPS = {
    plot: 'The central premise and major events. Use prose, bullets, or a scene outline—the story agents treat it as the narrative roadmap.',
    setting: 'The world and conditions surrounding the story, such as place, era, atmosphere, technology, magic, and social expectations.',
    style: 'How the story should read, including viewpoint, tone, vocabulary, pacing, detail level, and the balance of narration and dialogue.',
    history: 'Relevant events that occurred before the opening. Use it to carry forward prior chapters or explain the circumstances that start this story.',
    characters: 'The people or beings the story agents should portray consistently. Capture their appearance, personality, motives, relationships, and narrative role.',
    locations: 'Places whose details should remain consistent. Add locations when their atmosphere, layout, history, or rules matter to scenes.',
    objects: 'Items that need stable identities or behavior, especially tools, clues, artifacts, or possessions with plot significance.',
    openings: 'Alternative starting points for the story. Each opening can explain when it fits and contain one or more role-based messages that establish the first scene.',
  }

  const SETUP_FIELDS = [
    {
      key: 'protagonist',
      label: 'Protagonist seed',
      placeholder: 'Name, archetype, POV...',
      tooltip:
        'Describes who the main character is — their name, personality archetype, or point of view. The LLM anchors the story around this perspective.',
    },
    {
      key: 'opening_preference',
      label: 'Opening preference',
      placeholder: 'Cold open, dialogue-first...',
      tooltip:
        'How the story should begin. "Cold open" jumps straight into action. "Dialogue-first" starts mid-conversation. "In medias res" drops into the middle of an event.',
    },
    {
      key: 'output_format',
      label: 'Output format',
      placeholder: 'Novel prose, beat sheet...',
      tooltip:
        'The structural style of the output. "Novel prose" gives flowing narrative text. "Beat sheet" produces numbered story beats. "Script" gives screenplay-style dialogue.',
    },
    {
      key: 'tone',
      label: 'Tone',
      placeholder: 'Whimsical, grimdark, noir...',
      tooltip:
        'The emotional atmosphere of the story. "Whimsical" is light and fantastical. "Grimdark" is brutal and serious. "Noir" is moody and cynical. "Hopeful" is optimistic.',
    },
    {
      key: 'length_target',
      label: 'Length target',
      placeholder: 'Short scene, chapter...',
      tooltip:
        'How long the output should be. "Short scene" gives a few paragraphs. "Full chapter" targets 1000–3000 words. "Beat outline" gives concise bullet points.',
    },
  ]

  function defaultStorySetup() {
    return {
      protagonist: '',
      opening_preference: '',
      output_format: '',
      tone: '',
      length_target: '',
    }
  }

  let {
    llmConnected = true,
    personaId = 'blank',
    experimentationConfig = {},
    rawIdea = $bindable(''),
    loading = $bindable(false),
    error = $bindable(''),
    story = $bindable(null),
    savedName = $bindable(''),
    storySetup = $bindable(defaultStorySetup()),
    storyInstruction = $bindable(''),
    generationQuality = $bindable(''),
    agentReviews = [],
    onagentreview = () => {},
    onagentsaved = () => {},
  } = $props()

  let activeAbortController = $state(null)
  let activeGenerationId = $state(0)
  let generationProgress = $state({ activeSection: '', completedSections: [], error: '' })
  let draftSaveTimer = null
  let draftSaveState = $state('saved')
  let lastSavedSignature = $state('')
  let savingStory = $state(false)
  let itemActionKey = $state('')
  let editingItemKey = $state('')
  let editingItemDraft = $state(null)
  let editingOverview = $state(false)
  let editingOpening = $state(false)
  let editingPlot = $state(false)
  let overviewDraft = $state({ title: '', description: '', tagsText: '' })
  let openingDraft = $state('')
  let plotDraft = $state([])
  let storyDirty = $derived(Boolean(story) && storySignature() !== lastSavedSignature)

  function storySignature() {
    if (!story) return ''
    return JSON.stringify({
      rawIdea,
      story,
      storySetup,
      storyInstruction,
    })
  }

  /** Detect if a value is a raw JSON dump (backend parse failure) rather than human-readable text. */
  function looksLikeJson(value) {
    if (typeof value !== 'string') return false
    const t = value.trimStart()
    return (t.startsWith('{') || t.startsWith('[')) && t.includes('"')
  }

  function isAbortError(error) {
    return error?.name === 'AbortError'
  }

  function itemKey(section, index) {
    return `${section}:${index}`
  }

  function agentFieldReview(field) {
    return agentReviews.find((review) => review.field === field && !Number.isInteger(review.entity_index))
  }

  function agentFieldValue(field) {
    const review = agentFieldReview(field)
    return review?.view === 'old' ? review.before : story?.[field]
  }

  function handleAgentReview(event) {
    onagentreview({ page: 'story', ...event })
  }

  function mergeStoryArtifactPreservingImages(previousStory, nextStory) {
    if (!previousStory || typeof previousStory !== 'object') return nextStory
    if (!nextStory || typeof nextStory !== 'object') return previousStory
    const merged = { ...nextStory }
    for (const section of STORY_IMAGE_SECTIONS) {
      const prevItems = Array.isArray(previousStory?.[section]) ? previousStory[section] : []
      const nextItems = Array.isArray(nextStory?.[section]) ? nextStory[section] : []
      if (!nextItems.length) continue
      merged[section] = nextItems.map((item, index) => {
        if (!item || typeof item !== 'object') return item
        const previous = prevItems[index]
        if (!previous || typeof previous !== 'object') return item
        if (item.image_data || item.image_name) return item
        if (!previous.image_data && !previous.image_name) return item
        return {
          ...item,
          image_data: previous.image_data ?? item.image_data,
          image_name: previous.image_name ?? item.image_name,
          image_prompt: previous.image_prompt ?? item.image_prompt,
        }
      })
    }
    return merged
  }

  function scheduleStoryDraftSave() {
    if (!story) return
    draftSaveState = 'saving'
    if (draftSaveTimer) clearTimeout(draftSaveTimer)
    draftSaveTimer = setTimeout(() => {
      draftSaveTimer = null
      void persistStoryDraft()
    }, 350)
  }

  async function persistStoryDraft() {
    if (!story) return
    try {
      const res = await fetch('/api/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          artifact_type: 'story',
          raw_idea: rawIdea,
          state: {
            story_artifact: story,
            story_setup: storySetup,
            story_instruction: storyInstruction,
          },
          meta: { mode: 'story', source: 'story-editor' },
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        throw new Error(payload?.detail || 'Failed to save Story draft.')
      }
      draftSaveState = 'saved'
    } catch (saveError) {
      draftSaveState = 'error'
      error = saveError instanceof Error ? saveError.message : 'Failed to save Story draft.'
    }
  }

  function updateStoryField(key, value) {
    if (!story) return
    story = { ...story, [key]: value }
    scheduleStoryDraftSave()
  }

  function updateStoryTags(value) {
    updateStoryField(
      'tags',
      value
        .split(',')
        .map((tag) => tag.trim().toLowerCase())
        .filter(Boolean),
    )
  }

  function addStoryTag(value) {
    const tag = value.trim().toLowerCase()
    if (!tag || story?.tags?.includes(tag)) return
    updateStoryField('tags', [...(story?.tags ?? []), tag])
  }

  function removeStoryTag(tag) {
    updateStoryField('tags', (story?.tags ?? []).filter((entry) => entry !== tag))
  }

  function handleTagKeydown(event) {
    if (event.key !== 'Enter' && event.key !== ',') return
    event.preventDefault()
    addStoryTag(event.currentTarget.value)
    event.currentTarget.value = ''
  }

  function updatePlotBeatDirect(index, value) {
    if (!story) return
    story = {
      ...story,
      plot: (story.plot ?? []).map((beat, beatIndex) => (beatIndex === index ? value : beat)),
    }
    scheduleStoryDraftSave()
  }

  function addPlotBeatDirect() {
    if (!story) return
    story = { ...story, plot: [...(story.plot ?? []), ''] }
    scheduleStoryDraftSave()
  }

  function removePlotBeatDirect(index) {
    if (!story) return
    story = { ...story, plot: (story.plot ?? []).filter((_, beatIndex) => beatIndex !== index) }
    scheduleStoryDraftSave()
  }

  function updateStoryModuleItem(section, index, item) {
    if (!story) return
    const entries = [...(story[section] ?? [])]
    entries[index] = item
    story = { ...story, [section]: entries }
    scheduleStoryDraftSave()
  }

  function addStoryModuleItem(section) {
    if (!story) return
    const defaults = {
      characters_artifact: { name: '', role: '', summary: '', tags: [] },
      locations: { name: '', description: '', tags: [] },
      objects: { name: '', description: '', tags: [] },
      openings: { description: '', messages: [{ role: 'assistant', content: '' }] },
    }
    story = { ...story, [section]: [...(story[section] ?? []), defaults[section]] }
    scheduleStoryDraftSave()
  }

  function removeStoryModuleItem(section, index) {
    if (!story) return
    story = { ...story, [section]: (story[section] ?? []).filter((_, itemIndex) => itemIndex !== index) }
    scheduleStoryDraftSave()
  }

  function beginEditItem(section, index, item) {
    editingItemKey = itemKey(section, index)
    editingItemDraft = { ...(item ?? {}) }
  }

  function cancelEditItem() {
    editingItemKey = ''
    editingItemDraft = null
  }

  function updateEditingField(key, value) {
    editingItemDraft = {
      ...(editingItemDraft ?? {}),
      [key]: value,
    }
  }

  function updateEditingTags(value) {
    const tags = value
      .split(',')
      .map((entry) => entry.trim().toLowerCase())
      .filter(Boolean)
    updateEditingField('tags', tags)
  }

  function beginOverviewEdit() {
    if (!story) return
    overviewDraft = {
      title: String(story.title ?? ''),
      description: String(story.description ?? ''),
      tagsText: Array.isArray(story.tags) ? story.tags.join(', ') : '',
    }
    editingOverview = true
  }

  function saveOverviewEdit() {
    if (!story) return
    const nextTags = overviewDraft.tagsText
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean)
    story = {
      ...story,
      title: overviewDraft.title.trim(),
      description: overviewDraft.description,
      tags: nextTags,
    }
    editingOverview = false
  }

  function beginOpeningEdit() {
    if (!story) return
    openingDraft = String(story.opening ?? '')
    editingOpening = true
  }

  function saveOpeningEdit() {
    if (!story) return
    story = { ...story, opening: openingDraft }
    editingOpening = false
  }

  function beginPlotEdit() {
    if (!story) return
    plotDraft = Array.isArray(story.plot) ? [...story.plot] : []
    editingPlot = true
  }

  function updatePlotBeat(index, value) {
    plotDraft = plotDraft.map((beat, beatIndex) => (beatIndex === index ? value : beat))
  }

  function removePlotBeat(index) {
    plotDraft = plotDraft.filter((_, beatIndex) => beatIndex !== index)
  }

  function addPlotBeat() {
    plotDraft = [...plotDraft, '']
  }

  function savePlotEdit() {
    if (!story) return
    story = {
      ...story,
      plot: plotDraft.map((beat) => String(beat ?? '').trim()).filter(Boolean),
    }
    editingPlot = false
  }

  async function applyStoryItemOperation(section, itemIndex, operation, extra = {}) {
    if (!story) return null
    const opKey = `${operation}:${section}:${itemIndex}`
    itemActionKey = opKey
    error = ''
    try {
      const res = await fetch('/api/story-item', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_idea: rawIdea,
          section,
          item_index: itemIndex,
          operation,
          state: { story_artifact: story, story_setup: storySetup, story_instruction: storyInstruction },
          persona_id: personaId,
          sd_config: experimentationConfig?.sd ?? {},
          style: experimentationConfig?.sd?.style,
          ...extra,
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        error = payload?.detail || 'Failed to update story item.'
        return null
      }
      const payload = await res.json()
      const nextStory = payload.story_artifact ?? payload.state?.story_artifact ?? story
      story = mergeStoryArtifactPreservingImages(story, nextStory)
      return payload
    } catch {
      error = 'Failed to update story item.'
      return null
    } finally {
      if (itemActionKey === opKey) {
        itemActionKey = ''
      }
    }
  }

  async function saveItemEdit(section, itemIndex) {
    if (!editingItemDraft) return
    const payload = await applyStoryItemOperation(section, itemIndex, 'update', { item: editingItemDraft })
    if (payload) cancelEditItem()
  }

  async function deleteItem(section, itemIndex) {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm('Delete this item?')
      if (!confirmed) return
    }
    await applyStoryItemOperation(section, itemIndex, 'delete')
  }

  async function generateItemImage(section, itemIndex) {
    await applyStoryItemOperation(section, itemIndex, 'image', { mode: 'full' })
  }

  function updateStorySetup(key, value) {
    storySetup = {
      ...defaultStorySetup(),
      ...(storySetup ?? {}),
      [key]: value,
    }
  }

  function stopStoryGeneration() {
    activeGenerationId += 1
    if (activeAbortController) {
      activeAbortController.abort()
      activeAbortController = null
    }
    loading = false
  }

  function handleGenerateClick() {
    if (loading) {
      stopStoryGeneration()
      return
    }
    void generateStory('generate')
  }

  async function generateStory(action = 'generate') {
    if (!rawIdea.trim() || loading || !llmConnected) return
    const isInitialGeneration = action === 'generate' && !story
    const generationId = ++activeGenerationId
    const controller = new AbortController()
    activeAbortController = controller
    loading = true
    error = ''
    if (isInitialGeneration) {
      savedName = ''
      lastSavedSignature = ''
    }
    generationProgress = { activeSection: '', completedSections: [], error: '' }
    try {
      const res = await fetch(isInitialGeneration ? '/api/story/stream' : '/api/story', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          raw_idea: rawIdea,
          persona_id: personaId,
          experimentation_config: experimentationConfig,
          instruction: storyInstruction,
          story_setup: storySetup,
          action,
          state: story ? { story_artifact: story, story_setup: storySetup, story_instruction: storyInstruction } : undefined,
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        error = payload?.detail || 'Failed to generate story.'
        return
      }

      if (isInitialGeneration && res.body) {
        const decoder = new TextDecoder()
        const reader = res.body.getReader()
        let buffer = ''

        const processEvent = (rawEvent) => {
          const lines = rawEvent.split('\n')
          let eventName = 'message'
          let data = ''
          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventName = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              data += `${line.slice(5).trim()}\n`
            }
          }
          if (!data) return
          const payload = JSON.parse(data.trim())

          if (eventName === 'story-stage-start') {
            generationProgress = {
              ...generationProgress,
              activeSection: payload.section ?? '',
            }
          } else if (eventName === 'story-section-complete') {
            story = payload.story_artifact ?? story
            generationProgress = {
              ...generationProgress,
              completedSections: [...new Set([...generationProgress.completedSections, payload.section])],
            }
          } else if (eventName === 'story-complete') {
            story = payload.story_artifact ?? payload.state?.story_artifact ?? story
            generationQuality = payload.generation_quality ?? ''
            if (payload.story_setup) {
              storySetup = { ...defaultStorySetup(), ...payload.story_setup }
            }
            if (typeof payload.story_instruction === 'string') {
              storyInstruction = payload.story_instruction
            }
            generationProgress = { ...generationProgress, activeSection: '' }
          } else if (eventName === 'story-error') {
            generationProgress = { ...generationProgress, error: payload.detail ?? 'Story generation failed.' }
            error = generationProgress.error
          }
        }

        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true }).replace(/\r/g, '')
          let splitIndex = buffer.indexOf('\n\n')
          while (splitIndex !== -1) {
            const rawEvent = buffer.slice(0, splitIndex).trim()
            buffer = buffer.slice(splitIndex + 2)
            if (rawEvent) processEvent(rawEvent)
            splitIndex = buffer.indexOf('\n\n')
          }
        }
        return
      }

      const payload = await res.json()
      story = payload.story_artifact ?? payload.state?.story_artifact ?? null
      generationQuality = payload.generation_quality ?? ''
      if (payload.story_setup) {
        storySetup = { ...defaultStorySetup(), ...payload.story_setup }
      }
      if (typeof payload.story_instruction === 'string') {
        storyInstruction = payload.story_instruction
      }
    } catch (fetchError) {
      if (isAbortError(fetchError)) return
      error = 'Failed to generate story.'
    } finally {
      if (generationId === activeGenerationId) {
        activeAbortController = null
        loading = false
      }
    }
  }

  async function saveStory(asCopy = false) {
    if (!story || savingStory || (!asCopy && !storyDirty)) return
    savingStory = true
    error = ''
    try {
      const body = {
        raw_idea: rawIdea,
        state: { story_artifact: story, story_setup: storySetup, story_instruction: storyInstruction, characters: [] },
        meta: { source: 'story', story_generation_quality: generationQuality },
      }
      if (!asCopy && savedName) {
        body.filename = savedName
      }
      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        error = payload?.detail || 'Failed to save story.'
        return
      }
      const payload = await res.json()
      savedName = payload.filename
      lastSavedSignature = storySignature()
      onagentsaved({ page: 'story' })
    } catch {
      error = 'Failed to save story.'
    } finally {
      savingStory = false
    }
  }

  function handleResetStoryPage() {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm('Reset Story page and clear its temporary draft?')
      if (!confirmed) return
    }
    stopStoryGeneration()
    rawIdea = ''
    loading = false
    error = ''
    story = null
    savedName = ''
    lastSavedSignature = ''
    generationQuality = ''
    generationProgress = { activeSection: '', completedSections: [], error: '' }
    storySetup = defaultStorySetup()
    storyInstruction = ''
    editingOverview = false
    editingOpening = false
    editingPlot = false
    editingItemKey = ''
    editingItemDraft = null
  }

  onDestroy(() => {
    stopStoryGeneration()
    if (draftSaveTimer) {
      clearTimeout(draftSaveTimer)
      draftSaveTimer = null
      void persistStoryDraft()
    }
  })
</script>

<section class="story-page dark-ui-page dark-ui-story has-reset">
  <button class="app-btn-reset app-btn-reset-corner" type="button" onclick={handleResetStoryPage}>Reset</button>
  <div class="app-page-header">
    <h2 class="app-page-title">Story Creator</h2>
  </div>
  <textarea bind:value={rawIdea} rows="4" placeholder="Describe the story concept..." disabled={loading}></textarea>

  <div class="setup-grid">
    {#each SETUP_FIELDS as field}
      <label class="setup-label">
        <span class="setup-label-row">
          {field.label}
          <span class="tooltip-anchor" aria-label={field.tooltip}>
            <span class="tooltip-icon" aria-hidden="true">ℹ</span>
            <span class="tooltip-box" role="tooltip">{field.tooltip}</span>
          </span>
        </span>
        <input
          type="text"
          value={storySetup?.[field.key] ?? ''}
          oninput={(event) => updateStorySetup(field.key, event.currentTarget.value)}
          placeholder={field.placeholder}
          disabled={loading}
        />
      </label>
    {/each}
  </div>

  <textarea bind:value={storyInstruction} rows="3" placeholder="Instruction for this pass (optional)..." disabled={loading}></textarea>

  <div class="app-actions-row">
    <button class="app-btn-primary" onclick={handleGenerateClick} disabled={!loading && (!rawIdea.trim() || !llmConnected)}>
      {#if loading}
        <span class="spinner" aria-hidden="true"></span>
        Generating… Click to stop
      {:else}
        Generate Story
      {/if}
    </button>
    <button class="secondary" onclick={() => saveStory(false)} disabled={!story || loading || savingStory || !storyDirty}>
      {savingStory ? 'Saving…' : 'Save'}
    </button>
    <button class="secondary" onclick={() => saveStory(true)} disabled={!story || loading || savingStory}>Save as Copy</button>
  </div>

  {#if error}<p class="error">{error}</p>{/if}
  {#if savedName}<p class="ok">Saved as {savedName}</p>{/if}
  {#if generationQuality && generationQuality !== 'full'}
    <p class="quality-warning">⚠ Story generated with reduced quality — the AI had difficulty producing structured output. Consider regenerating.</p>
  {/if}

  {#if loading || generationProgress.completedSections.length}
    <section class="generation-progress" aria-live="polite">
      <h3>Generation progress</h3>
      {#if generationProgress.activeSection}
        <p>Generating {generationProgress.activeSection.replaceAll('_', ' ')}…</p>
      {:else if !loading}
        <p>Generation complete.</p>
      {/if}
      <div class="progress-stages">
        {#each ['overview', 'title', 'plot', 'history', 'characters_artifact', 'locations', 'objects', 'openings'] as section}
          <span class:complete={generationProgress.completedSections.includes(section)} class:active={generationProgress.activeSection === section}>
            {section.replaceAll('_', ' ')}
          </span>
        {/each}
      </div>
      {#if generationProgress.error}
        <p class="error">{generationProgress.error}</p>
      {/if}
    </section>
  {/if}

  <!-- Loading skeleton -->
  {#if loading && !story}
    <div class="skeleton-grid">
      <div class="skeleton-card tall"></div>
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
      <div class="skeleton-card"></div>
    </div>
  {/if}

  {#if story}
    <div class="story-editor" class:regenerating={loading}>
      <section class="story-module overview-module">
        <header>
          <h3>Story overview</h3>
          <span class="draft-status">
            {agentReviews.length
              ? `${agentReviews.length} agent edit${agentReviews.length === 1 ? '' : 's'} staged`
              : draftSaveState === 'saving'
                ? 'Saving…'
                : draftSaveState === 'error'
                  ? 'Save failed'
                  : 'Saved to draft'}
          </span>
        </header>
        <AgentReviewControls review={agentFieldReview('title')} onreview={handleAgentReview} />
        <label class="module-field">
          <span>Title</span>
          <input type="text" value={agentFieldValue('title') ?? ''} placeholder="Story title" aria-label="Story title" oninput={(event) => updateStoryField('title', event.currentTarget.value)} disabled={loading || agentFieldReview('title')?.view === 'old'} />
        </label>
        <AgentReviewControls review={agentFieldReview('description')} onreview={handleAgentReview} />
        <label class="module-field">
          <span>Summary</span>
          <textarea rows="3" value={agentFieldValue('description') ?? ''} placeholder="A concise overview of the scenario" aria-label="Story summary" oninput={(event) => updateStoryField('description', event.currentTarget.value)} disabled={loading || agentFieldReview('description')?.view === 'old'}></textarea>
        </label>
        <AgentReviewControls review={agentFieldReview('tags')} onreview={handleAgentReview} />
        <div class="module-field">
          <span>Tags</span>
          <div class="tag-editor">
            {#each agentFieldValue('tags') ?? [] as tag}
              <button type="button" class="tag-badge" onclick={() => removeStoryTag(tag)} disabled={loading || agentFieldReview('tags')?.view === 'old'} title={`Remove ${tag}`}>{tag} ×</button>
            {/each}
            <input type="text" placeholder="Add tag and press Enter" aria-label="Add story tag" onkeydown={handleTagKeydown} disabled={loading || agentFieldReview('tags')?.view === 'old'} />
          </div>
        </div>
      </section>

      <section class="story-module">
        <header>
          <h3>Plot</h3>
          <span class="module-tooltip" title={STORY_FIELD_TOOLTIPS.plot} aria-label={STORY_FIELD_TOOLTIPS.plot}>?</span>
        </header>
        <AgentReviewControls review={agentFieldReview('plot')} onreview={handleAgentReview} />
        <textarea rows="7" value={agentFieldValue('plot') ?? ''} placeholder="Describe the premise and main events..." aria-label="Story plot" oninput={(event) => updateStoryField('plot', event.currentTarget.value)} disabled={loading || agentFieldReview('plot')?.view === 'old'}></textarea>
        <div class="module-actions">
          <button class="ghost small" type="button" onclick={() => generateStory('suggest_next_beat')} disabled={loading || !llmConnected}>Expand plot</button>
        </div>
      </section>

      <section class="story-module">
        <header>
          <h3>Setting</h3>
          <span class="module-tooltip" title={STORY_FIELD_TOOLTIPS.setting} aria-label={STORY_FIELD_TOOLTIPS.setting}>?</span>
        </header>
        <AgentReviewControls review={agentFieldReview('setting')} onreview={handleAgentReview} />
        <textarea rows="5" value={agentFieldValue('setting') ?? ''} placeholder="Describe the world, time, place, and atmosphere..." aria-label="Story setting" oninput={(event) => updateStoryField('setting', event.currentTarget.value)} disabled={loading || agentFieldReview('setting')?.view === 'old'}></textarea>
      </section>

      <section class="story-module">
        <header>
          <h3>Style</h3>
          <span class="module-tooltip" title={STORY_FIELD_TOOLTIPS.style} aria-label={STORY_FIELD_TOOLTIPS.style}>?</span>
        </header>
        <AgentReviewControls review={agentFieldReview('style')} onreview={handleAgentReview} />
        <textarea rows="4" value={agentFieldValue('style') ?? ''} placeholder="Describe viewpoint, tone, pacing, and prose style..." aria-label="Story style" oninput={(event) => updateStoryField('style', event.currentTarget.value)} disabled={loading || agentFieldReview('style')?.view === 'old'}></textarea>
      </section>

      <section class="story-module">
        <header>
          <h3>History</h3>
          <span class="module-tooltip" title={STORY_FIELD_TOOLTIPS.history} aria-label={STORY_FIELD_TOOLTIPS.history}>?</span>
        </header>
        <AgentReviewControls review={agentFieldReview('history')} onreview={handleAgentReview} />
        <textarea rows="5" value={agentFieldValue('history') ?? ''} placeholder="Summarize the events leading into this story..." aria-label="Story history" oninput={(event) => updateStoryField('history', event.currentTarget.value)} disabled={loading || agentFieldReview('history')?.view === 'old'}></textarea>
      </section>

      <StorySectionModule
        title="Characters"
        section="characters_artifact"
        items={story.characters_artifact ?? []}
        bodyKey="summary"
        extraKey="tags"
        tooltip={STORY_FIELD_TOOLTIPS.characters}
        disabled={loading}
        agentReviews={agentReviews.filter((review) => review.field === 'characters_artifact')}
        onupdate={(index, item) => updateStoryModuleItem('characters_artifact', index, item)}
        onadd={() => addStoryModuleItem('characters_artifact')}
        onremove={(index) => removeStoryModuleItem('characters_artifact', index)}
        onimage={(index) => generateItemImage('characters_artifact', index)}
        onagentreview={handleAgentReview}
      />
      <StorySectionModule
        title="Locations"
        section="locations"
        items={story.locations ?? []}
        extraKey="tags"
        tooltip={STORY_FIELD_TOOLTIPS.locations}
        disabled={loading}
        agentReviews={agentReviews.filter((review) => review.field === 'locations')}
        onupdate={(index, item) => updateStoryModuleItem('locations', index, item)}
        onadd={() => addStoryModuleItem('locations')}
        onremove={(index) => removeStoryModuleItem('locations', index)}
        onimage={(index) => generateItemImage('locations', index)}
        onagentreview={handleAgentReview}
      />
      <StorySectionModule
        title="Objects"
        section="objects"
        items={story.objects ?? []}
        extraKey="tags"
        tooltip={STORY_FIELD_TOOLTIPS.objects}
        disabled={loading}
        agentReviews={agentReviews.filter((review) => review.field === 'objects')}
        onupdate={(index, item) => updateStoryModuleItem('objects', index, item)}
        onadd={() => addStoryModuleItem('objects')}
        onremove={(index) => removeStoryModuleItem('objects', index)}
        onimage={(index) => generateItemImage('objects', index)}
        onagentreview={handleAgentReview}
      />

      <StoryOpeningsModule
        openings={story.openings ?? []}
        disabled={loading}
        tooltip={STORY_FIELD_TOOLTIPS.openings}
        agentReviews={agentReviews.filter((review) => review.field === 'openings')}
        onupdate={(index, opening) => updateStoryModuleItem('openings', index, opening)}
        onadd={() => addStoryModuleItem('openings')}
        onremove={(index) => removeStoryModuleItem('openings', index)}
        onagentreview={handleAgentReview}
      />
    </div>

    <div class="story-grid legacy-story-grid" class:regenerating={loading}>

      <!-- Overview card -->
      <div class="story-card overview-card">
        <div class="card-header">
          <h3>{story.title || 'Untitled Story'}</h3>
          {#if !editingOverview}
            <button class="icon-action-btn" type="button" title="Edit story summary" aria-label="Edit story summary" onclick={beginOverviewEdit}>✏️</button>
          {/if}
        </div>
        {#if editingOverview}
          <label class="field-label">Title
            <input type="text" value={overviewDraft.title} oninput={(event) => (overviewDraft = { ...overviewDraft, title: event.currentTarget.value })} />
          </label>
          <label class="field-label">Summary
            <textarea rows="4" value={overviewDraft.description} oninput={(event) => (overviewDraft = { ...overviewDraft, description: event.currentTarget.value })}></textarea>
          </label>
          <label class="field-label">Tags (comma-separated)
            <input type="text" value={overviewDraft.tagsText} oninput={(event) => (overviewDraft = { ...overviewDraft, tagsText: event.currentTarget.value })} />
          </label>
          <div class="entity-actions">
            <button class="ghost small" type="button" onclick={saveOverviewEdit}>Save</button>
            <button class="ghost small" type="button" onclick={() => (editingOverview = false)}>Cancel</button>
          </div>
        {:else}
          {#if story.tags?.length}
            <p class="tags">{story.tags.join(', ')}</p>
          {/if}
          {#if story.description}
            {#if looksLikeJson(story.description)}
              <p class="malformed-notice">⚠ Description could not be parsed — please regenerate.</p>
            {:else}
              <p class="description">{story.description}</p>
            {/if}
          {:else}
            <p class="empty">No summary yet.</p>
          {/if}
        {/if}
        <div class="overview-meta">
          {#if story.setting}<span class="meta-chip"><strong>Setting</strong> {story.setting}</span>{/if}
          {#if story.style}<span class="meta-chip"><strong>Style</strong> {story.style}</span>{/if}
        </div>
      </div>

      <!-- Plot Beats card -->
      <div class="story-card">
        <div class="card-header">
          <h4>📖 Plot Beats</h4>
          {#if !editingPlot}
            <button class="icon-action-btn" type="button" title="Edit plot beats" aria-label="Edit plot beats" onclick={beginPlotEdit}>✏️</button>
          {/if}
        </div>
        {#if editingPlot}
          {#if plotDraft.length}
            <div class="plot-edit-list">
              {#each plotDraft as beat, index}
                <div class="plot-edit-item">
                  <textarea rows="2" value={beat} oninput={(event) => updatePlotBeat(index, event.currentTarget.value)}></textarea>
                  <button
                    class="icon-action-btn icon-delete-btn"
                    type="button"
                    title="Delete plot beat"
                    aria-label={`Delete plot beat ${index + 1}`}
                    onclick={() => removePlotBeat(index)}
                  >
                    🗑️
                  </button>
                </div>
              {/each}
            </div>
          {:else}
            <p class="empty">No plot beats yet. Add one below.</p>
          {/if}
          <div class="entity-actions">
            <button class="ghost small" type="button" onclick={addPlotBeat}>+ Add Beat</button>
            <button class="ghost small" type="button" onclick={savePlotEdit}>Save</button>
            <button class="ghost small" type="button" onclick={() => (editingPlot = false)}>Cancel</button>
          </div>
        {:else}
          {#if story.plot?.length}
            <ol class="plot-list">
              {#each story.plot as beat}
                <li>{looksLikeJson(beat) ? '⚠ Beat could not be parsed' : beat}</li>
              {/each}
            </ol>
          {:else}
            <p class="empty">No plot beats generated yet.</p>
          {/if}
        {/if}
        <div class="card-footer">
          <button class="ghost small" type="button" onclick={() => generateStory('suggest_next_beat')} disabled={loading || !llmConnected}>+ Suggest Next Beat</button>
          <button class="ghost small" type="button" onclick={() => generateStory('rewrite_opening')} disabled={loading || !llmConnected}>↩ Rewrite Opening</button>
        </div>
      </div>

      <!-- Characters card -->
      <div class="story-card">
        <div class="card-header">
          <h4>👤 Characters</h4>
        </div>
        {#if story.characters_artifact?.length}
          {#each story.characters_artifact as character, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('characters_artifact', index)}
                <label>Name <input type="text" value={editingItemDraft?.name ?? ''} oninput={(event) => updateEditingField('name', event.currentTarget.value)} /></label>
                <label>Role <input type="text" value={editingItemDraft?.role ?? ''} oninput={(event) => updateEditingField('role', event.currentTarget.value)} /></label>
                <label>Summary <textarea rows="3" value={editingItemDraft?.summary ?? ''} oninput={(event) => updateEditingField('summary', event.currentTarget.value)}></textarea></label>
                <label>Tags <input type="text" value={(editingItemDraft?.tags ?? []).join(', ')} oninput={(event) => updateEditingTags(event.currentTarget.value)} /></label>
              {:else}
                <p><strong>{character.name || 'Unnamed character'}</strong>{#if character.role} · <em>{character.role}</em>{/if}</p>
                {#if character.summary && !looksLikeJson(character.summary)}<p>{character.summary}</p>{/if}
                {#if character.image_data}
                  <img class="entity-image" src={character.image_data} alt={`Character art for ${character.name || 'character'}`} />
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('characters_artifact', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('characters_artifact', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button
                    class="icon-action-btn"
                    type="button"
                    onclick={() => beginEditItem('characters_artifact', index, character)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Edit character"
                    aria-label={`Edit ${character.name || `character ${index + 1}`}`}
                  >
                    ✏️
                  </button>
                  <button
                    class="icon-action-btn icon-delete-btn"
                    type="button"
                    onclick={() => deleteItem('characters_artifact', index)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Delete character"
                    aria-label={`Delete ${character.name || `character ${index + 1}`}`}
                  >
                    🗑️
                  </button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('characters_artifact', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No characters generated yet.</p>
        {/if}
        <div class="card-footer">
          <button class="ghost small" type="button" onclick={() => generateStory('add_character')} disabled={loading || !llmConnected}>+ Add Character</button>
        </div>
      </div>

      <!-- Locations card -->
      <div class="story-card">
        <div class="card-header">
          <h4>📍 Locations</h4>
        </div>
        {#if story.locations?.length}
          {#each story.locations as location, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('locations', index)}
                <label>Name <input type="text" value={editingItemDraft?.name ?? ''} oninput={(event) => updateEditingField('name', event.currentTarget.value)} /></label>
                <label>Description <textarea rows="3" value={editingItemDraft?.description ?? ''} oninput={(event) => updateEditingField('description', event.currentTarget.value)}></textarea></label>
                <label>Tags <input type="text" value={(editingItemDraft?.tags ?? []).join(', ')} oninput={(event) => updateEditingTags(event.currentTarget.value)} /></label>
              {:else}
                <p><strong>{location.name || 'Unnamed location'}</strong></p>
                {#if location.description && !looksLikeJson(location.description)}<p>{location.description}</p>{/if}
                {#if location.image_data}
                  <img class="entity-image" src={location.image_data} alt={`Location art for ${location.name || 'location'}`} />
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('locations', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('locations', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button
                    class="icon-action-btn"
                    type="button"
                    onclick={() => beginEditItem('locations', index, location)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Edit location"
                    aria-label={`Edit ${location.name || `location ${index + 1}`}`}
                  >
                    ✏️
                  </button>
                  <button
                    class="icon-action-btn icon-delete-btn"
                    type="button"
                    onclick={() => deleteItem('locations', index)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Delete location"
                    aria-label={`Delete ${location.name || `location ${index + 1}`}`}
                  >
                    🗑️
                  </button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('locations', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No locations generated yet.</p>
        {/if}
        <div class="card-footer">
          <button class="ghost small" type="button" onclick={() => generateStory('add_location')} disabled={loading || !llmConnected}>+ Add Location</button>
        </div>
      </div>

      <!-- Objects card -->
      <div class="story-card">
        <div class="card-header">
          <h4>🔧 Objects</h4>
        </div>
        {#if story.objects?.length}
          {#each story.objects as item, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('objects', index)}
                <label>Name <input type="text" value={editingItemDraft?.name ?? ''} oninput={(event) => updateEditingField('name', event.currentTarget.value)} /></label>
                <label>Description <textarea rows="3" value={editingItemDraft?.description ?? ''} oninput={(event) => updateEditingField('description', event.currentTarget.value)}></textarea></label>
                <label>Tags <input type="text" value={(editingItemDraft?.tags ?? []).join(', ')} oninput={(event) => updateEditingTags(event.currentTarget.value)} /></label>
              {:else}
                <p><strong>{item.name || 'Unnamed object'}</strong></p>
                {#if item.description && !looksLikeJson(item.description)}<p>{item.description}</p>{/if}
                {#if item.image_data}
                  <img class="entity-image" src={item.image_data} alt={`Object art for ${item.name || 'object'}`} />
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('objects', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('objects', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button
                    class="icon-action-btn"
                    type="button"
                    onclick={() => beginEditItem('objects', index, item)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Edit object"
                    aria-label={`Edit ${item.name || `object ${index + 1}`}`}
                  >
                    ✏️
                  </button>
                  <button
                    class="icon-action-btn icon-delete-btn"
                    type="button"
                    onclick={() => deleteItem('objects', index)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Delete object"
                    aria-label={`Delete ${item.name || `object ${index + 1}`}`}
                  >
                    🗑️
                  </button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('objects', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No objects generated yet.</p>
        {/if}
        <div class="card-footer">
          <button class="ghost small" type="button" onclick={() => generateStory('add_object')} disabled={loading || !llmConnected}>+ Add Object</button>
        </div>
      </div>

      <!-- Opening card -->
      <div class="story-card opening-card">
        <div class="card-header">
          <h4>✍ Opening</h4>
          {#if !editingOpening}
            <button class="icon-action-btn" type="button" title="Edit opening" aria-label="Edit opening" onclick={beginOpeningEdit}>✏️</button>
          {/if}
        </div>
        {#if editingOpening}
          <label class="field-label">Opening text
            <textarea rows="8" value={openingDraft} oninput={(event) => (openingDraft = event.currentTarget.value)}></textarea>
          </label>
          <div class="entity-actions">
            <button class="ghost small" type="button" onclick={saveOpeningEdit}>Save</button>
            <button class="ghost small" type="button" onclick={() => (editingOpening = false)}>Cancel</button>
          </div>
        {:else}
          {#if story.opening && !looksLikeJson(story.opening)}
            <MarkdownBlock source={story.opening} />
          {:else if story.opening}
            <p class="malformed-notice">⚠ Opening could not be parsed — please regenerate.</p>
          {:else}
            <p class="empty">No opening excerpt generated yet.</p>
          {/if}
        {/if}
        <div class="card-footer">
          <button class="ghost small" type="button" onclick={() => generateStory('rewrite_opening')} disabled={loading || !llmConnected}>↩ Rewrite Opening</button>
        </div>
      </div>

      <!-- Examples card -->
      <div class="story-card">
        <div class="card-header">
          <h4>💬 Examples</h4>
          <span class="tooltip-anchor section-tooltip" aria-label="Examples are optional style snippets. Add short mini-passages to steer voice, phrasing, or dialogue style for future generations.">
            <span class="tooltip-icon" aria-hidden="true">ℹ</span>
            <span class="tooltip-box" role="tooltip">
              Examples are optional style snippets. Add short mini-passages to steer voice, phrasing, or dialogue style for future generations.
            </span>
          </span>
        </div>
        {#if story.examples?.length}
          {#each story.examples as example, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('examples', index)}
                <label>Label <input type="text" value={editingItemDraft?.label ?? ''} oninput={(event) => updateEditingField('label', event.currentTarget.value)} /></label>
                <label>Text <textarea rows="3" value={editingItemDraft?.text ?? ''} oninput={(event) => updateEditingField('text', event.currentTarget.value)}></textarea></label>
              {:else}
                <p><strong>{example.label || 'Example'}</strong></p>
                {#if example.text && !looksLikeJson(example.text)}<p>{example.text}</p>{/if}
                {#if example.image_data}
                  <img class="entity-image" src={example.image_data} alt={`Example art for ${example.label || 'example'}`} />
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('examples', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('examples', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button
                    class="icon-action-btn"
                    type="button"
                    onclick={() => beginEditItem('examples', index, example)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Edit example"
                    aria-label={`Edit ${example.label || `example ${index + 1}`}`}
                  >
                    ✏️
                  </button>
                  <button
                    class="icon-action-btn icon-delete-btn"
                    type="button"
                    onclick={() => deleteItem('examples', index)}
                    disabled={Boolean(itemActionKey) || loading}
                    title="Delete example"
                    aria-label={`Delete ${example.label || `example ${index + 1}`}`}
                  >
                    🗑️
                  </button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('examples', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No examples generated yet.</p>
        {/if}
        <div class="card-footer">
          <button class="ghost small" type="button" onclick={() => generateStory('add_example')} disabled={loading || !llmConnected}>+ Add Example</button>
        </div>
      </div>

    </div>
  {/if}
</section>

<style>
  /* ── Page layout ──────────────────────────────────────────────── */
  .story-page { display: grid; gap: 0.75rem; margin-top: 0; }

  textarea {
    width: 100%; box-sizing: border-box;
    border: 1px solid var(--lb-input-border, #cbd5e1); border-radius: 6px;
    padding: 0.6rem; background: var(--lb-input-bg, #fff); color: var(--lb-input-fg, #0f172a);
  }

  /* ── Setup grid with tooltips ─────────────────────────────────── */
  .setup-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.6rem; }
  .setup-label { display: grid; gap: 0.25rem; font-size: 0.85rem; color: var(--lb-text-2, #475569); }
  .setup-label-row { display: flex; align-items: center; gap: 0.3rem; }
  .setup-label input {
    border: 1px solid var(--lb-input-border, #cbd5e1); border-radius: 6px;
    padding: 0.45rem 0.55rem; background: var(--lb-input-bg, #fff); color: var(--lb-input-fg, #0f172a);
  }

  /* Tooltip */
  .tooltip-anchor {
    position: relative; display: inline-flex; align-items: center; cursor: help;
  }
  .tooltip-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 1rem; height: 1rem; border-radius: 50%;
    background: rgba(148,163,184,0.25); color: #94a3b8;
    font-size: 0.65rem; font-style: normal; flex-shrink: 0;
    border: 1px solid rgba(148,163,184,0.4);
  }
  .tooltip-box {
    display: none;
    position: absolute; bottom: calc(100% + 0.4rem); left: 50%; transform: translateX(-50%);
    width: 230px; background: #1e293b; color: #e2e8f0;
    padding: 0.5rem 0.7rem; border-radius: 6px; font-size: 0.78rem; line-height: 1.5;
    z-index: 200; pointer-events: none; white-space: normal;
    border: 1px solid #334155; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  }
  .tooltip-anchor:hover .tooltip-box,
  .tooltip-anchor:focus-within .tooltip-box { display: block; }
  .section-tooltip { margin-left: auto; }

  /* ── Buttons ──────────────────────────────────────────────────── */
  button { border-radius: 6px; padding: 0.4rem 0.75rem; cursor: pointer; }
  button.secondary { background: rgba(51,65,85,0.75); border-color: var(--lb-border-1, #334155); color: var(--lb-text-1, #fff); }
  button.ghost { border-color: var(--lb-border-1, #94a3b8); background: transparent; color: var(--lb-text-2, #334155); }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  button.small { padding: 0.3rem 0.55rem; font-size: 0.82rem; }
  .icon-action-btn {
    width: 2rem;
    height: 2rem;
    padding: 0;
    border: 1px solid var(--lb-border-1, #64748b);
    border-radius: 999px;
    background: rgba(30, 41, 59, 0.6);
    color: #e2e8f0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.95rem;
    line-height: 1;
  }
  .icon-action-btn:hover:not(:disabled) {
    background: rgba(51, 65, 85, 0.95);
    border-color: #94a3b8;
  }
  .icon-delete-btn {
    border-color: rgba(185, 28, 28, 0.6);
    color: #fecaca;
  }
  .icon-delete-btn:hover:not(:disabled) {
    background: rgba(127, 29, 29, 0.4);
    border-color: #ef4444;
  }

  /* ── Spinner ──────────────────────────────────────────────────── */
  .spinner {
    display: inline-block; width: 0.8rem; height: 0.8rem;
    border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
    border-radius: 50%; animation: spin 0.7s linear infinite; vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Status messages ──────────────────────────────────────────── */
  .quality-warning { color: #fbbf24; font-size: 0.85rem; padding: 0.45rem 0.6rem; background: rgba(251,191,36,0.1); border: 1px solid rgba(251,191,36,0.3); border-radius: 6px; margin: 0; }
  .malformed-notice { color: #fb923c; font-size: 0.85rem; font-style: italic; margin: 0; }
  .generation-progress {
    display: grid; gap: 0.45rem; padding: 0.75rem 0.9rem;
    border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 8px;
    background: rgba(14, 116, 144, 0.12);
  }
  .generation-progress h3, .generation-progress p { margin: 0; }
  .progress-stages { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .progress-stages span {
    border: 1px solid rgba(100, 116, 139, 0.65); border-radius: 999px;
    padding: 0.2rem 0.55rem; color: #94a3b8; font-size: 0.78rem;
  }
  .progress-stages span.active { border-color: #38bdf8; color: #e0f2fe; }
  .progress-stages span.complete { border-color: #34d399; color: #d1fae5; }
  .draft-status { color: var(--lb-text-2, #94a3b8); font-size: 0.8rem; }

  /* ── Loading skeleton ─────────────────────────────────────────── */
  .skeleton-grid { display: grid; gap: 0.75rem; }
  .skeleton-card {
    height: 100px; border-radius: 8px;
    background: linear-gradient(90deg, rgba(51,65,85,0.4) 25%, rgba(71,85,105,0.5) 50%, rgba(51,65,85,0.4) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  .skeleton-card.tall { height: 160px; }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  /* ── Story grid ───────────────────────────────────────────────── */
  .story-grid { display: grid; gap: 0.75rem; transition: opacity 0.2s; }
  .story-grid.regenerating { opacity: 0.6; pointer-events: none; }
  .legacy-story-grid { display: none; }

  .story-editor {
    display: grid; gap: 0.8rem; transition: opacity 0.2s;
    border: 1px solid var(--lb-border-1, #334155); border-radius: 10px;
    padding: 0.9rem 1rem; background: rgba(15, 23, 42, 0.5);
  }
  .story-editor.regenerating { opacity: 0.65; pointer-events: none; }
  .story-module { display: grid; gap: 0.55rem; border-top: 1px solid rgba(51, 65, 85, 0.7); padding-top: 0.75rem; }
  .story-module:first-child { border-top: 0; padding-top: 0; }
  .story-module header { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; }
  .story-module h3 { margin: 0; font-size: 1rem; color: var(--lb-text-1, #e2e8f0); }
  .module-tooltip {
    display: inline-flex; align-items: center; justify-content: center;
    width: 1rem; height: 1rem; margin-left: auto; border: 1px solid #64748b;
    border-radius: 50%; color: #cbd5e1; font-size: 0.7rem; cursor: help;
  }
  .module-field { display: grid; gap: 0.3rem; color: var(--lb-text-2, #cbd5e1); font-size: 0.82rem; }
  .story-module > textarea,
  .module-field input,
  .module-field textarea,
  .tag-editor input {
    width: 100%; box-sizing: border-box; border: 1px solid var(--lb-border-1, #475569);
    border-radius: 6px; padding: 0.5rem 0.6rem; background: rgba(30, 41, 59, 0.85);
    color: var(--lb-text-1, #e2e8f0);
  }
  .story-module textarea { resize: vertical; line-height: 1.5; }
  .tag-editor { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }
  .tag-editor input { flex: 1 1 11rem; min-width: 9rem; }
  .tag-badge {
    border: 1px solid rgba(56, 189, 248, 0.45); border-radius: 999px;
    padding: 0.22rem 0.55rem; background: rgba(14, 116, 144, 0.2);
    color: #bae6fd; font-size: 0.78rem;
  }
  .module-actions { display: flex; gap: 0.4rem; }

  /* ── Story cards ──────────────────────────────────────────────── */
  .story-card {
    border: 1px solid var(--lb-border-1, #334155); border-radius: 10px;
    background: rgba(15,23,42,0.5); display: grid; gap: 0.65rem;
    padding: 0.9rem 1rem;
  }
  .overview-card { border-color: rgba(99,179,237,0.35); background: rgba(15,23,42,0.65); }
  .opening-card { border-color: rgba(167,139,250,0.35); }

  .card-header { display: flex; align-items: baseline; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; }
  .card-header h3 { margin: 0; font-size: 1.3rem; color: var(--lb-text-1, #e2e8f0); }
  .card-header h4 { margin: 0; font-size: 1rem; color: var(--lb-text-1, #e2e8f0); }

  .card-footer {
    display: flex; flex-wrap: wrap; gap: 0.4rem;
    padding-top: 0.5rem; border-top: 1px solid rgba(51,65,85,0.5);
    margin-top: 0.25rem;
  }

  .overview-meta { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .meta-chip {
    font-size: 0.82rem; padding: 0.2rem 0.55rem; border-radius: 4px;
    background: rgba(51,65,85,0.5); border: 1px solid rgba(71,85,105,0.5);
    color: var(--lb-text-2, #94a3b8);
  }
  .meta-chip strong { color: var(--lb-text-1, #e2e8f0); margin-right: 0.3rem; }

  .description { color: var(--lb-text-2, #94a3b8); line-height: 1.6; margin: 0; }
  .tags { color: #7dd3fc; font-size: 0.85rem; margin: 0; }

  .plot-list { margin: 0; padding-left: 1.4rem; color: var(--lb-text-2, #94a3b8); }
  .plot-list li { margin-bottom: 0.45rem; line-height: 1.5; }
  .plot-edit-list { display: grid; gap: 0.5rem; }
  .plot-edit-item { display: grid; grid-template-columns: 1fr auto; gap: 0.45rem; align-items: start; }

  /* ── Entity cards (characters, locations, etc.) ───────────────── */
  .entity-card {
    border: 1px solid var(--lb-border-1, #334155); border-radius: 8px;
    padding: 0.55rem 0.65rem; background: rgba(15,23,42,0.38);
  }
  .entity-card label { display: grid; gap: 0.2rem; margin-bottom: 0.35rem; color: var(--lb-text-2, #475569); font-size: 0.85rem; }
  .entity-card input,
  .entity-card textarea {
    border: 1px solid var(--lb-input-border, #cbd5e1); border-radius: 6px;
    padding: 0.4rem 0.5rem; background: var(--lb-input-bg, #fff); color: var(--lb-input-fg, #0f172a);
  }
  .entity-card p { color: var(--lb-text-2, #94a3b8); line-height: 1.5; margin: 0 0 0.3rem 0; }
  .entity-card p strong { color: var(--lb-text-1, #e2e8f0); }
  .entity-card p em { color: #94a3b8; }
  .entity-actions { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
  .entity-image { margin-top: 0.35rem; width: 100%; max-width: 260px; border-radius: 8px; border: 1px solid var(--lb-border-1, #334155); }
  .field-label {
    display: grid;
    gap: 0.35rem;
    color: var(--lb-text-2, #cbd5e1);
    font-size: 0.85rem;
  }
  .field-label input,
  .field-label textarea {
    border: 1px solid var(--lb-input-border, #cbd5e1);
    border-radius: 6px;
    padding: 0.45rem 0.55rem;
    background: var(--lb-input-bg, #fff);
    color: var(--lb-input-fg, #0f172a);
  }

  .empty { color: var(--lb-page-muted, #64748b); font-style: italic; margin: 0; }
</style>
