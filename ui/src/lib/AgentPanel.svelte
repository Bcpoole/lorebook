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
    showContinue = false,
    continueDisabled = true,
    llmConnected = true,
    reviewState = null,
    reviewPanelOpen = true,
    visibleAgentKeys = null,
    iconOnlyCharacterActions = false,
    confirmDeleteDialog = false,
    onnext = () => {},
    oncontinue = () => {},
    onsave = () => {},
    onsuggestname = () => {},
    onrandomname = () => {},
    onrunmodule = async () => {},
    oncharacterimage = async () => {},
    onspawnrelated = async () => {},
    onsavecharacter = async () => {},
    onapprovereview = () => {},
    onrejectreview = () => {},
    oneditreview = () => {},
    onregeneratesummary = () => {},
    ontogglereviewpanel = () => {},
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

  const visibleEntries = $derived.by(() => {
    if (!Array.isArray(visibleAgentKeys) || visibleAgentKeys.length === 0) {
      return Object.entries(agentLabels)
    }
    return Object.entries(agentLabels).filter(([key]) => visibleAgentKeys.includes(key))
  })

  $effect(() => {
    if (Array.isArray(visibleAgentKeys) && visibleAgentKeys.length > 0 && !visibleAgentKeys.includes(activeAgent)) {
      activeAgent = visibleAgentKeys[0]
    }
  })

  let editingLoremaster = $state(false)
  let loremasterDraft = $state('')

  let modulePromptLoremaster = $state('')
  let modulePromptCharacter = $state('')
  let modulePromptEditor = $state('')

  let editingCharacterIndex = $state(null)
  let characterDraft = $state('')
  let selectedCharacterIndex = $state(0)
  let collapsed = $state({})
  let confirmDeleteIndex = $state(null)
  let imageModalSrc = $state('')
  let imageModalTitle = $state('')
  let imageGeneratingIndex = $state(null)
  let imagePromptDrafts = $state({})
  let editingReview = $state(false)
  let spawnRelationship = $state('')
  let spawnContext = $state('')
  let savingCharacterIndex = $state(null)
  let savedFlash = $state({})

  function updateWorkflow(nextState) {
    workflowState = nextState
  }

  function extractCharacterName(details) {
    if (!details || typeof details !== 'string') return ''
    const lines = details.split('\n').map((line) => line.trim()).filter(Boolean)

    for (const line of lines) {
      const match = line.match(/^(?:[-*]\s*)?(?:\*\*|__)?name(?:\*\*|__)?:?(?:\*\*|__)?\s*(.+?)\s*$/i)
      if (match && match[1]) {
        const parsed = match[1].replace(/[*_`]/g, '').trim()
        if (parsed.length > 0 && parsed.length < 100) return parsed
      }
    }

    for (const line of lines) {
      const header = line.replace(/^#+\s*/, '').replace(/[*_`]/g, '').trim()
      if (!header) continue
      const lower = header.toLowerCase()
      if (
        lower === 'character card profile' ||
        lower === 'sillytavern dialogue attributes' ||
        lower === 'appearance' ||
        lower === 'personality' ||
        lower === 'background' ||
        lower === 'abilities'
      ) {
        continue
      }
      if (header.length > 0 && header.length < 100) return header
    }

    return ''
  }

  function shouldReplaceCharacterName(name) {
    const value = (name ?? '').trim()
    if (!value) return true
    return (
      /^companion(?:\s+\d+)?$/i.test(value) ||
      /^character card profile$/i.test(value) ||
      /^character(?:\s+\d+)?$/i.test(value)
    )
  }

  // Auto-extract and set character names when they're generated
  $effect(() => {
    if (!characters || characters.length === 0) return
    
    const updated = characters.map((char, idx) => {
      // Only update name if it's placeholder/generic and we have details
      if (shouldReplaceCharacterName(char.name) && char.details) {
        const extracted = extractCharacterName(char.details)
        if (extracted && extracted !== char.name) {
          return { ...char, name: extracted }
        }
      }
      return char
    })

    // Only update if something actually changed
    if (JSON.stringify(updated) !== JSON.stringify(characters)) {
      updateWorkflow({ ...workflowState, characters: updated })
    }
  })

  function startEditLoremaster() {
    loremasterDraft = worldSetting
    editingLoremaster = true
  }

  function confirmEditLoremaster() {
    updateWorkflow({ ...workflowState, world_setting: loremasterDraft })
    editingLoremaster = false
  }

  function ensureCharacterIndex(index) {
    if (index < 0) return 0
    if (index >= characters.length) return Math.max(0, characters.length - 1)
    return index
  }

  function selectCharacter(index) {
    selectedCharacterIndex = ensureCharacterIndex(index)
  }

  function startEditCharacter(index) {
    characterDraft = characters[index]?.details ?? ''
    editingCharacterIndex = index
    selectedCharacterIndex = index
  }

  function confirmEditCharacter(index) {
    const updated = [...characters]
    if (!updated[index]) return
    updated[index] = { ...updated[index], details: characterDraft }
    updateWorkflow({ ...workflowState, characters: updated })
    editingCharacterIndex = null
  }

  function addCharacter() {
    const next = [
      ...characters,
      {
        name: '',
        details: '',
      },
    ]
    updateWorkflow({ ...workflowState, characters: next })
    selectedCharacterIndex = next.length - 1
  }

  function askDeleteCharacter(index) {
    if (confirmDeleteDialog && typeof window !== 'undefined') {
      const label = characters[index]?.name || `Character ${index + 1}`
      const confirmed = window.confirm(`Delete ${label}? This cannot be undone.`)
      if (confirmed) {
        deleteCharacter(index)
      }
      return
    }
    confirmDeleteIndex = index
  }

  function deleteCharacter(index) {
    const next = characters.filter((_, i) => i !== index)
    updateWorkflow({ ...workflowState, characters: next })
    confirmDeleteIndex = null
    if (next.length === 0) {
      selectedCharacterIndex = 0
      return
    }
    selectedCharacterIndex = Math.min(selectedCharacterIndex, next.length - 1)
  }

  function toggleCollapse(index) {
    collapsed = { ...collapsed, [index]: !collapsed[index] }
  }

  function imageSrc(character) {
    if (character?.image_data) return character.image_data
    return ''
  }

  function extractCharacterHook(details) {
    if (!details || typeof details !== 'string') return ''
    const lines = details.split('\n').map(l => l.trim()).filter(l => l)
    for (const line of lines) {
      if (line.startsWith('#') || line.startsWith('**')) continue
      if (line.length > 10 && line.length < 120) {
        return line.replace(/[*_`]/g, '').substring(0, 100)
      }
    }
    return ''
  }

  function isCharacterLoading(index) {
    return running && lastNode === 'character_designer' && index === selectedCharacterIndex
  }

  function openImageModal(character, fallbackTitle) {
    const src = imageSrc(character)
    if (!src) return
    imageModalSrc = src
    imageModalTitle = character?.name || fallbackTitle
  }

  function closeImageModal() {
    imageModalSrc = ''
    imageModalTitle = ''
  }

  function handleModalBackdropClick(event) {
    if (event.target === event.currentTarget) {
      closeImageModal()
    }
  }

  function handleModalKeydown(event) {
    if (event.key === 'Escape') {
      closeImageModal()
    }
  }

  function updateCharacterName(index, nextName) {
    const updated = [...characters]
    if (!updated[index]) return
    updated[index] = { ...updated[index], name: nextName }
    updateWorkflow({ ...workflowState, characters: updated })
  }

  async function runModulePrompt(stage) {
    if (running || !llmConnected) return

    let directive = ''
    let characterIndex = selectedCharacterIndex
    if (stage === 'loremaster') directive = modulePromptLoremaster
    if (stage === 'character_designer') directive = modulePromptCharacter
    if (stage === 'editor') directive = modulePromptEditor

    await onrunmodule({ stage, directive, characterIndex })
  }

  async function generateCharacterImage(index) {
    if (running || imageGeneratingIndex !== null || !llmConnected) return
    imageGeneratingIndex = index
    try {
      await oncharacterimage({
        characterIndex: index,
        promptOverride: imagePromptDrafts[index] ?? '',
        mode: 'full', // generate both prompt and image
      })
    } finally {
      imageGeneratingIndex = null
    }
  }

  async function regenerateImagePrompt(index) {
    if (running || imageGeneratingIndex !== null || !llmConnected) return
    imageGeneratingIndex = index
    try {
      await oncharacterimage({
        characterIndex: index,
        promptOverride: imagePromptDrafts[index] ?? '',
        mode: 'prompt', // generate prompt only
      })
    } finally {
      imageGeneratingIndex = null
    }
  }

  async function generateImageFromPrompt(index) {
    if (running || imageGeneratingIndex !== null || !llmConnected) return
    imageGeneratingIndex = index
    try {
      await oncharacterimage({
        characterIndex: index,
        promptOverride: imagePromptDrafts[index] ?? '',
        mode: 'image', // use existing prompt, generate image only
      })
    } finally {
      imageGeneratingIndex = null
    }
  }

  function isReviewActiveForStage(stage, characterIndex = selectedCharacterIndex) {
    if (!reviewState) return false
    if (reviewState.stage !== stage) return false
    if (stage !== 'character_designer') return true
    return reviewState.characterIndex === characterIndex
  }

  function toggleReviewEdit() {
    editingReview = !editingReview
  }

  $effect(() => {
    reviewState
    editingReview = false
  })

  async function handleSpawnRelated() {
    if (running || !llmConnected || characters.length === 0 || !spawnRelationship.trim()) return
    await onspawnrelated({ relationship: spawnRelationship.trim(), sourceCharacterIndex: selectedCharacterIndex, context: spawnContext.trim() })
    spawnRelationship = ''
    spawnContext = ''
  }

  async function handleSaveCharacter(index) {
    if (savingCharacterIndex !== null) return
    savingCharacterIndex = index
    try {
      await onsavecharacter(index)
      savedFlash = { ...savedFlash, [index]: true }
      setTimeout(() => {
        savedFlash = { ...savedFlash, [index]: false }
      }, 1500)
    } finally {
      savingCharacterIndex = null
    }
  }
</script>

<div class="agents">
  <div class="workflow-header">
    <nav class="agent-tabs" aria-label="Workflow order">
      {#each visibleEntries as [key, label], index}
        <button
          class="agent-step"
          class:active={activeAgent === key}
          class:current={lastNode === key && running}
          class:done={savedRun && key === 'save_assets'}
          onclick={() => (activeAgent = key)}
        >
          {#if visibleEntries.length > 1}<span class="step-index">{index + 1}</span>{/if}
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
      {#if showContinue}
        <button class="continue-btn" onclick={oncontinue} disabled={continueDisabled || !llmConnected}>
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

  <div class="panel-shell">
    <div class="panel">
    {#if activeAgent === 'loremaster'}
      <div class="module-runner">
        <label for="module-loremaster">Loremaster prompt</label>
        <textarea id="module-loremaster" bind:value={modulePromptLoremaster} rows="3" placeholder="Refine world setting output..."></textarea>
        <button class="module-btn" onclick={() => runModulePrompt('loremaster')} disabled={running || !llmConnected}>Send To Loremaster</button>
      </div>

      {#if worldSetting}
        {#if isReviewActiveForStage('loremaster')}
          <div class="review-headline">Review Refined Output</div>
          <div class="review-actions">
            <button class="edit-btn" onclick={toggleReviewEdit}>{editingReview ? 'Done Editing' : 'Edit'}</button>
            <button class="cancel-btn" onclick={onrejectreview}>Reject</button>
            <button class="confirm-btn" onclick={onapprovereview} disabled={!reviewState?.wip?.trim()}>Approve</button>
          </div>
          <div class="review-compare two-col">
            <section class="compare-col">
              <h4>Original</h4>
              <MarkdownBlock source={reviewState.original} />
            </section>
            <section class="compare-col wip">
              <h4>Next Output</h4>
              {#if editingReview}
                <textarea class="edit-area" value={reviewState.wip} oninput={(event) => oneditreview(event.currentTarget.value)}></textarea>
              {:else}
                <MarkdownBlock source={reviewState.wip} />
              {/if}
            </section>
          </div>
        {:else}
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
        {/if}
      {:else}
        <p class="empty">{running && lastNode === 'loremaster' ? 'Generating…' : 'No output yet.'}</p>
      {/if}

    {:else if activeAgent === 'character_designer'}
      <div class="module-runner">
        <label for="module-character">Character Designer prompt (selected card)</label>
        <textarea id="module-character" bind:value={modulePromptCharacter} rows="3" placeholder="Refine selected character..."></textarea>
        <button class="module-btn" onclick={() => runModulePrompt('character_designer')} disabled={running || characters.length === 0 || !llmConnected}>
          Send To Character Designer
        </button>
      </div>

      <div class="spawn-section">
        <label class="spawn-label" for="spawn-relationship">Spawn Related Character</label>
        <div class="spawn-row">
          <input
            id="spawn-relationship"
            class="spawn-input"
            bind:value={spawnRelationship}
            placeholder="Relationship (e.g. mother, rival, mentor)"
          />
          <button
            class="module-btn spawn-btn"
            onclick={handleSpawnRelated}
            disabled={running || !llmConnected || characters.length === 0 || !spawnRelationship.trim()}
          >Spawn Related</button>
        </div>
        <textarea
          class="spawn-context"
          bind:value={spawnContext}
          rows="2"
          placeholder="Optional: additional context for the new character (traits, backstory hints, tone…)"
        ></textarea>
      </div>

      <div class="character-toolbar">
        <button class="add-char-btn" onclick={addCharacter} disabled={running}>+ Add Blank Character</button>
      </div>

      {#if characters.length > 0}
        {#each characters as character, index}
          {@const isCollapsed = Boolean(collapsed[index])}
          {@const isSelected = selectedCharacterIndex === index}
          {@const headerImg = imageSrc(character)}
          {@const hook = extractCharacterHook(character.details)}
          {@const isLoading = isCharacterLoading(index)}
          <article class="character-card" class:selected={isSelected}>
            {#if !isCollapsed && !isLoading}
              <div class="character-compact-header">
                <div class="compact-info">
                  <span class="compact-name">{character.name || `Character ${index + 1}`}</span>
                  {#if hook}
                    <span class="compact-hook">{hook}</span>
                  {/if}
                </div>
              </div>
            {/if}
            <header class="character-header">
              <button class="collapse-btn" onclick={() => toggleCollapse(index)} title={isCollapsed ? 'Expand' : 'Collapse'}>
                {isCollapsed ? '▸' : '▾'}
              </button>

              <div class="character-summary">
                {#if headerImg}
                  <button
                    class="image-btn"
                    onclick={() => openImageModal(character, `Character ${index + 1}`)}
                    aria-label={`Open ${character.name} image`}
                  >
                    <img
                      class="thumb"
                      class:thumb-collapsed={isCollapsed}
                      src={headerImg}
                      alt={`${character.name} avatar`}
                    />
                  </button>
                {:else}
                  <div class="thumb placeholder" class:thumb-collapsed={isCollapsed}>IMG</div>
                {/if}

                <input
                  class="char-name-input"
                  value={character.name}
                  placeholder={`Character ${index + 1}`}
                  oninput={(event) => updateCharacterName(index, event.currentTarget.value)}
                  onfocus={() => selectCharacter(index)}
                />
              </div>

              <div class="character-actions">
                <button class="select-btn" class:is-selected={isSelected} onclick={() => selectCharacter(index)}>
                  {isSelected ? '✓ Active' : 'Select'}
                </button>
                <button
                  class="save-char-btn"
                  class:save-flash={savedFlash[index]}
                  onclick={() => handleSaveCharacter(index)}
                  disabled={running || !llmConnected || !character?.details?.trim() || savingCharacterIndex !== null}
                >
                  {savedFlash[index] ? '✅' : '💾'}
                </button>
                <button
                  class="edit-btn"
                  class:icon-action={iconOnlyCharacterActions}
                  onclick={() => startEditCharacter(index)}
                  disabled={running}
                  title="Edit character"
                  aria-label={`Edit ${character.name || `Character ${index + 1}`}`}
                >
                  {iconOnlyCharacterActions ? '✏️' : '✎ Edit'}
                </button>
                <button
                  class="delete-btn"
                  class:icon-action={iconOnlyCharacterActions}
                  onclick={() => askDeleteCharacter(index)}
                  disabled={running || characters.length === 1}
                  title="Delete character"
                  aria-label={`Delete ${character.name || `Character ${index + 1}`}`}
                >
                  {iconOnlyCharacterActions ? '🗑️' : '🗑 Delete'}
                </button>
              </div>
            </header>

            {#if !isCollapsed}
              <div class="character-body">
                <div class="portrait-panel">
                  {#if headerImg}
                    <button class="image-btn" onclick={() => openImageModal(character, character.name)} aria-label={`Open ${character.name} portrait`}>
                      <img class="portrait" src={headerImg} alt={`${character.name} portrait`} />
                    </button>
                  {:else}
                    <div class="portrait portrait-placeholder">No image yet</div>
                  {/if}

                  <label for={`image-prompt-${index}`}>Image prompt</label>
                  <textarea
                    id={`image-prompt-${index}`}
                    rows="3"
                    placeholder="Leave empty to auto-generate prompt from character details"
                    value={imagePromptDrafts[index] ?? character.image_prompt ?? ''}
                    oninput={(event) => {
                      imagePromptDrafts = { ...imagePromptDrafts, [index]: event.currentTarget.value }
                    }}
                  ></textarea>

                  <div class="image-button-group">
                    <button class="module-btn" onclick={() => generateCharacterImage(index)} disabled={running || imageGeneratingIndex !== null || !llmConnected}>
                      {imageGeneratingIndex === index ? 'Generating…' : '🎨 Generate Image'}
                    </button>
                    <button class="icon-btn" onclick={() => regenerateImagePrompt(index)} disabled={running || imageGeneratingIndex !== null || !llmConnected} title="Regenerate prompt">
                      ♻️
                    </button>
                    <button class="icon-btn" onclick={() => generateImageFromPrompt(index)} disabled={running || imageGeneratingIndex !== null || !llmConnected} title="Generate image from current prompt">
                      🎨
                    </button>
                  </div>
                </div>

                <div class="details-panel">
                  {#if isLoading}
                    <div class="skeleton-loader">
                      <div class="skeleton-line skeleton-title"></div>
                      <div class="skeleton-line skeleton-long"></div>
                      <div class="skeleton-line"></div>
                      <div class="skeleton-line"></div>
                      <div class="skeleton-line skeleton-short"></div>
                    </div>
                  {:else if editingCharacterIndex === index}
                    <textarea class="edit-area" bind:value={characterDraft}></textarea>
                    <div class="inline-actions">
                      <button class="confirm-btn" onclick={() => confirmEditCharacter(index)}>✔ Done</button>
                      <button class="cancel-btn" onclick={() => (editingCharacterIndex = null)}>✕</button>
                    </div>
                  {:else if isReviewActiveForStage('character_designer', index)}
                    <div class="review-headline">Review Refined Output</div>
                    <div class="review-actions">
                      <button class="edit-btn" onclick={toggleReviewEdit}>{editingReview ? 'Done Editing' : 'Edit'}</button>
                      <button class="cancel-btn" onclick={onrejectreview}>Reject</button>
                      <button class="confirm-btn" onclick={onapprovereview} disabled={!reviewState?.wip?.trim()}>Approve</button>
                    </div>
                    <div class="review-compare two-col">
                      <section class="compare-col">
                        <h4>Original</h4>
                        <MarkdownBlock source={reviewState.original} />
                      </section>
                      <section class="compare-col wip">
                        <h4>Next Output</h4>
                        {#if editingReview}
                          <textarea class="edit-area" value={reviewState.wip} oninput={(event) => oneditreview(event.currentTarget.value)}></textarea>
                        {:else}
                          <MarkdownBlock source={reviewState.wip} />
                        {/if}
                      </section>
                    </div>
                  {:else}
                    <MarkdownBlock source={character.details} />
                  {/if}
                </div>
              </div>
            {/if}
          </article>
        {/each}
      {:else}
        <div class="empty-state">
          <p class="empty">No characters yet.</p>
          <button class="add-char-btn" onclick={addCharacter} disabled={running}>+ Generate First Character</button>
        </div>
      {/if}

      {#if confirmDeleteIndex !== null}
        <div class="confirm-strip">
          <p>Delete {characters[confirmDeleteIndex]?.name || `Character ${confirmDeleteIndex + 1}`}?</p>
          <div class="inline-actions">
            <button class="delete-btn" onclick={() => deleteCharacter(confirmDeleteIndex)}>Yes, delete</button>
            <button class="cancel-btn" onclick={() => (confirmDeleteIndex = null)}>Cancel</button>
          </div>
        </div>
      {/if}

    {:else if activeAgent === 'editor'}
      <div class="module-runner">
        <label for="module-editor">Editor prompt</label>
        <textarea id="module-editor" bind:value={modulePromptEditor} rows="3" placeholder="Ask editor for specific critique focus..."></textarea>
        <button class="module-btn" onclick={() => runModulePrompt('editor')} disabled={running || characters.length === 0 || !llmConnected}>
          Send To Editor
        </button>
      </div>

      {#if passedInspection === true}
        <p class="passed">✓ PASSED</p>
        {#if critiqueNotes}
          {#if isReviewActiveForStage('editor')}
            <div class="review-headline">Review Refined Output</div>
            <div class="review-actions">
              <button class="edit-btn" onclick={toggleReviewEdit}>{editingReview ? 'Done Editing' : 'Edit'}</button>
              <button class="cancel-btn" onclick={onrejectreview}>Reject</button>
              <button class="confirm-btn" onclick={onapprovereview} disabled={!reviewState?.wip?.trim()}>Approve</button>
            </div>
            <div class="review-compare two-col">
              <section class="compare-col">
                <h4>Original</h4>
                <MarkdownBlock source={reviewState.original} />
              </section>
              <section class="compare-col wip">
                <h4>Next Output</h4>
                {#if editingReview}
                  <textarea class="edit-area" value={reviewState.wip} oninput={(event) => oneditreview(event.currentTarget.value)}></textarea>
                {:else}
                  <MarkdownBlock source={reviewState.wip} />
                {/if}
              </section>
            </div>
          {:else}
            <MarkdownBlock source={critiqueNotes} />
          {/if}
        {/if}
      {:else if passedInspection === false && critiqueNotes}
        <p class="failed">✗ Needs revision</p>
        {#if isReviewActiveForStage('editor')}
          <div class="review-headline">Review Refined Output</div>
          <div class="review-actions">
            <button class="edit-btn" onclick={toggleReviewEdit}>{editingReview ? 'Done Editing' : 'Edit'}</button>
            <button class="cancel-btn" onclick={onrejectreview}>Reject</button>
            <button class="confirm-btn" onclick={onapprovereview} disabled={!reviewState?.wip?.trim()}>Approve</button>
          </div>
          <div class="review-compare two-col">
            <section class="compare-col">
              <h4>Original</h4>
              <MarkdownBlock source={reviewState.original} />
            </section>
            <section class="compare-col wip">
              <h4>Next Output</h4>
              {#if editingReview}
                <textarea class="edit-area" value={reviewState.wip} oninput={(event) => oneditreview(event.currentTarget.value)}></textarea>
              {:else}
                <MarkdownBlock source={reviewState.wip} />
              {/if}
            </section>
          </div>
        {:else}
          <MarkdownBlock source={critiqueNotes} />
        {/if}
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
          <p class="save-subtitle">Choose a filename and store this run in outputs/world, outputs/character, or outputs/story.</p>

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
              <button class="suggest-btn" onclick={onsuggestname} disabled={suggesting || !llmConnected}>
                {suggesting ? '…' : '✨ Smart Name'}
              </button>
              <button class="random-btn" onclick={onrandomname}>🎲 Random ID</button>
            </div>

            <button class="save-btn" onclick={() => onsave(filename)} disabled={!llmConnected}>Save Run</button>
          </div>
        </div>
      {:else}
        <p class="empty">Waiting for editor pass.</p>
      {/if}
    {/if}
    </div>

    <aside class="review-panel" class:closed={!reviewPanelOpen}>
      <header class="review-panel-header">
        <h3>Summary</h3>
        <button class="collapse-side-btn" onclick={ontogglereviewpanel}>{reviewPanelOpen ? '⟩' : '⟨'}</button>
      </header>
      {#if reviewPanelOpen}
        {#if reviewState}
          <div class="summary-box">
            {#if reviewState.summaryLoading}
              <p class="summary-loading">Generating narrative summary…</p>
            {/if}
            <div class="summary-content" aria-label="Revision summary">
              <MarkdownBlock source={reviewState.summary} />
            </div>
            <button class="module-btn" onclick={onregeneratesummary} disabled={reviewState.summaryLoading}>Regenerate Summary</button>
          </div>
        {:else}
          <p class="empty">Run a refinement prompt to generate a review summary.</p>
        {/if}
      {/if}
    </aside>
  </div>
</div>

{#if imageModalSrc}
  <div
    class="image-modal"
    role="dialog"
    aria-modal="true"
    tabindex="0"
    onkeydown={handleModalKeydown}
    onclick={handleModalBackdropClick}
  >
    <div class="image-modal-content">
      <button class="modal-close" onclick={closeImageModal}>✕</button>
      <h3>{imageModalTitle}</h3>
      <img src={imageModalSrc} alt={imageModalTitle} />
    </div>
  </div>
{/if}

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

  .header-actions {
    display: flex;
    gap: 0.45rem;
    flex: 0 0 auto;
  }

  .next-btn,
  .continue-btn,
  .module-btn,
  .add-char-btn {
    border: 1px solid #2563eb;
    background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
    color: #fff;
    border-radius: 999px;
    padding: 0.45rem 1rem;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
  }

  .continue-btn {
    border-color: #6366f1;
    background: linear-gradient(180deg, #818cf8 0%, #6366f1 100%);
  }

  .next-btn:disabled,
  .continue-btn:disabled,
  .module-btn:disabled,
  .add-char-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .image-button-group {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .image-button-group .module-btn {
    flex: 1;
    min-width: 150px;
  }

  .icon-btn {
    border: 1px solid #cbd5e1;
    background: #f8fafc;
    color: #334155;
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .icon-btn:hover:not(:disabled) {
    border-color: #2563eb;
    background: #eff6ff;
    color: #1e40af;
  }

  .icon-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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
  }

  .agent-step::after {
    content: '➜';
    position: absolute;
    right: -1.03rem;
    top: 50%;
    transform: translateY(-50%);
    color: #94a3b8;
    font-size: 0.9rem;
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
  }

  .agent-step.active {
    background: #1e40af;
    color: #fff;
    border-color: #1e40af;
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
  }

  @keyframes blink {
    50% { opacity: 0; }
  }

  .panel-shell {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: 0.85rem;
    align-items: start;
  }

  .panel {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    min-height: 220px;
  }

  .review-panel {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #f8fafc;
    padding: 0.8rem;
    position: sticky;
    top: 0.5rem;
  }

  .review-panel.closed {
    width: 58px;
    padding: 0.6rem 0.45rem;
  }

  .review-panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.4rem;
    margin-bottom: 0.5rem;
  }

  .review-panel-header h3 {
    margin: 0;
    font-size: 0.92rem;
    color: #1e293b;
  }

  .collapse-side-btn {
    border: 1px solid #cbd5e1;
    background: #fff;
    border-radius: 8px;
    width: 1.9rem;
    height: 1.9rem;
    cursor: pointer;
  }

  .summary-box {
    display: grid;
    gap: 0.55rem;
  }

  .summary-loading {
    margin: 0;
    font-size: 0.72rem;
    color: #1d4ed8;
    font-weight: 600;
  }

  .summary-content {
    max-height: calc(14 * 1.35em);
    overflow-y: auto;
    padding-right: 0.35rem;
    border: 1px solid #dbe7f6;
    border-radius: 8px;
    background: #ffffff;
  }

  .summary-content :global(p),
  .summary-content :global(li),
  .summary-content :global(blockquote),
  .summary-content :global(code) {
    font-size: 0.74rem;
    line-height: 1.35;
  }

  .summary-content :global(ul),
  .summary-content :global(ol) {
    margin: 0.35rem 0;
    padding-left: 1rem;
  }

  .review-headline {
    font-size: 0.85rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 0.4rem;
  }

  .review-actions {
    display: flex;
    gap: 0.4rem;
    margin-bottom: 0.65rem;
  }

  .review-compare {
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    overflow: hidden;
    background: #ffffff;
  }

  .two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .compare-col {
    padding: 0.75rem;
    min-height: 130px;
  }

  .compare-col h4 {
    margin: 0 0 0.55rem;
    font-size: 0.8rem;
    color: #334155;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .compare-col.wip {
    border-left: 1px solid #cbd5e1;
    background: #eff6ff;
  }

  .module-runner {
    display: grid;
    gap: 0.45rem;
    margin-bottom: 0.85rem;
    padding: 0.75rem;
    border: 1px dashed #cbd5e1;
    border-radius: 10px;
    background: #ffffff;
  }

  .spawn-section {
    display: grid;
    gap: 0.4rem;
    margin-bottom: 0.85rem;
    padding: 0.65rem 0.75rem;
    border: 1px dashed #a5b4fc;
    border-radius: 10px;
    background: #fafaff;
  }

  .spawn-label {
    font-size: 0.82rem;
    font-weight: 700;
    color: #4338ca;
  }

  .spawn-row {
    display: flex;
    gap: 0.45rem;
    align-items: center;
  }

  .spawn-input {
    flex: 1;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.4rem 0.55rem;
    font-size: 0.85rem;
  }

  .spawn-btn {
    flex: 0 0 auto;
    white-space: nowrap;
    border-color: #4338ca;
    background: linear-gradient(180deg, #6366f1 0%, #4338ca 100%);
  }

  .module-runner label {
    font-size: 0.82rem;
    font-weight: 700;
    color: #334155;
  }

  .module-runner textarea,
  .edit-area,
  .portrait-panel textarea {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.55rem;
    resize: vertical;
    font-size: 0.9rem;
    min-height: 78px;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    margin-bottom: 0.4rem;
  }

  .character-toolbar {
    margin: 0 0 0.75rem;
  }

  .character-card {
    border: 1px solid #d1d5db;
    border-radius: 12px;
    background: #fff;
    margin-bottom: 0.85rem;
    overflow: hidden;
  }

  .character-card.selected {
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
  }

  .character-card.selected .character-header {
    background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
    border-bottom-color: #bfdbfe;
  }

  .character-compact-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0.75rem;
    background: linear-gradient(135deg, #f0f9ff 0%, #eff6ff 100%);
    border-bottom: 1px solid #bfdbfe;
  }

  .compact-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-width: 0;
  }

  .compact-name {
    font-weight: 700;
    font-size: 0.9rem;
    color: #1e40af;
  }

  .compact-hook {
    font-size: 0.8rem;
    color: #64748b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .character-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.65rem 0.75rem;
    background: #f8fafc;
    cursor: pointer;
  }

  .collapse-btn {
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 1rem;
  }

  .character-summary {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex: 1;
  }

  .thumb {
    width: 64px;
    height: 64px;
    border-radius: 10px;
    object-fit: cover;
    border: 1px solid #cbd5e1;
    cursor: pointer;
    flex: 0 0 auto;
  }

  .image-btn {
    border: none;
    background: transparent;
    padding: 0;
    margin: 0;
    line-height: 0;
    cursor: pointer;
    border-radius: 10px;
  }

  .image-btn:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
  }

  .thumb-collapsed {
    width: 64px;
    height: 64px;
  }

  .placeholder {
    display: grid;
    place-items: center;
    background: #e2e8f0;
    color: #475569;
    font-size: 0.75rem;
    font-weight: 700;
  }

  .char-name-input {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    font-size: 0.95rem;
    width: min(320px, 100%);
  }

  .character-actions {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .select-btn,
  .save-char-btn,
  .edit-btn,
  .confirm-btn,
  .cancel-btn,
  .delete-btn {
    border: 1px solid #cbd5e1;
    background: #fff;
    border-radius: 8px;
    padding: 0.35rem 0.6rem;
    font-size: 0.78rem;
    cursor: pointer;
  }

  .select-btn {
    border-color: #2563eb;
    color: #1d4ed8;
  }

  .select-btn.is-selected {
    background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
    color: #fff;
    border-color: #1d4ed8;
    font-weight: 700;
  }

  .save-char-btn {
    border-color: #334155;
    color: #334155;
    font-size: 1rem;
    padding: 0.3rem 0.55rem;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
  }

  .save-char-btn.save-flash {
    background: #dcfce7;
    border-color: #16a34a;
    color: #15803d;
  }

  .spawn-context {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid #c7d2fe;
    border-radius: 8px;
    padding: 0.45rem 0.55rem;
    font-size: 0.84rem;
    resize: vertical;
    background: #fff;
    color: #374151;
    min-height: 54px;
  }

  .spawn-context::placeholder {
    color: #a5b4fc;
    font-style: italic;
  }

  .delete-btn {
    border-color: #fecaca;
    color: #b91c1c;
  }

  .icon-action {
    min-width: 2rem;
    height: 2rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    font-size: 0.95rem;
    line-height: 1;
  }

  .character-body {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 0.85rem;
    padding: 0.8rem;
    border-top: 1px solid #e2e8f0;
  }

  .portrait-panel {
    display: grid;
    gap: 0.45rem;
    align-content: start;
  }

  .portrait {
    width: 256px;
    height: 256px;
    border-radius: 12px;
    object-fit: cover;
    border: 1px solid #cbd5e1;
    cursor: pointer;
  }

  .portrait-placeholder {
    display: grid;
    place-items: center;
    background: #e2e8f0;
    color: #475569;
    font-weight: 600;
  }

  .confirm-strip {
    margin-top: 0.4rem;
    border: 1px solid #fecaca;
    background: #fff1f2;
    color: #881337;
    border-radius: 10px;
    padding: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .inline-actions {
    display: flex;
    gap: 0.4rem;
  }

  .passed { color: #16a34a; font-weight: 700; }
  .failed { color: #dc2626; font-weight: 700; }
  .empty { color: #94a3b8; font-style: italic; }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.8rem;
    padding: 1.5rem;
    text-align: center;
    background: #f9fafb;
    border: 2px dashed #d1d5db;
    border-radius: 12px;
  }

  .empty-state .empty {
    margin: 0;
    font-size: 1rem;
  }

  .empty-state .add-char-btn {
    margin: 0;
  }

  .skeleton-loader {
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    padding: 1rem;
  }

  .skeleton-line {
    height: 1rem;
    background: linear-gradient(90deg, #e5e7eb 0%, #f3f4f6 50%, #e5e7eb 100%);
    background-size: 200% 100%;
    border-radius: 6px;
    animation: shimmer 2s infinite;
  }

  .skeleton-title {
    height: 1.4rem;
    width: 60%;
  }

  .skeleton-long {
    width: 100%;
  }

  .skeleton-short {
    width: 40%;
  }

  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .save-card {
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 0.9rem;
    background: #fff;
  }

  .save-card.success {
    border-color: #16a34a;
    background: #f0fdf4;
  }

  .save-form {
    display: grid;
    gap: 0.55rem;
  }

  .filename-input {
    width: 100%;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.55rem;
    box-sizing: border-box;
  }

  .name-actions {
    display: flex;
    gap: 0.5rem;
  }

  .suggest-btn,
  .random-btn,
  .save-btn {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.45rem 0.7rem;
    background: #fff;
    cursor: pointer;
  }

  .save-btn {
    background: #1e40af;
    color: #fff;
    border-color: #1e40af;
  }

  .image-modal {
    position: fixed;
    inset: 0;
    background: rgba(2, 6, 23, 0.6);
    display: grid;
    place-items: center;
    z-index: 60;
    padding: 1rem;
  }

  .image-modal-content {
    position: relative;
    width: min(94vw, 860px);
    max-height: 92vh;
    background: #fff;
    border-radius: 12px;
    padding: 1rem;
    display: grid;
    gap: 0.75rem;
  }

  .image-modal-content img {
    width: 100%;
    max-height: calc(92vh - 140px);
    object-fit: contain;
    border-radius: 8px;
    background: #0f172a;
  }

  .modal-close {
    position: absolute;
    top: 0.55rem;
    right: 0.55rem;
    border: 1px solid #cbd5e1;
    background: #fff;
    border-radius: 999px;
    width: 2rem;
    height: 2rem;
    cursor: pointer;
  }

  :global(.dark-ui-world) .agent-step,
  :global(.dark-ui-character) .agent-step {
    border-color: #334155;
    background: linear-gradient(180deg, #1e293b 0%, #111827 100%);
    color: #cbd5e1;
  }

  :global(.dark-ui-world) .step-index,
  :global(.dark-ui-character) .step-index {
    background: #1e3a8a;
    color: #dbeafe;
  }

  :global(.dark-ui-world) .agent-step.active,
  :global(.dark-ui-character) .agent-step.active {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    border-color: #1d4ed8;
    color: #eff6ff;
  }

  :global(.dark-ui-world) .panel,
  :global(.dark-ui-character) .panel,
  :global(.dark-ui-world) .review-panel,
  :global(.dark-ui-character) .review-panel,
  :global(.dark-ui-world) .module-runner,
  :global(.dark-ui-character) .module-runner,
  :global(.dark-ui-world) .review-compare,
  :global(.dark-ui-character) .review-compare,
  :global(.dark-ui-world) .summary-content,
  :global(.dark-ui-character) .summary-content,
  :global(.dark-ui-world) .save-card,
  :global(.dark-ui-character) .save-card {
    background: rgba(15, 23, 42, 0.55);
    border-color: #334155;
    color: #e2e8f0;
  }

  :global(.dark-ui-world) .spawn-section,
  :global(.dark-ui-character) .spawn-section {
    background: rgba(30, 41, 59, 0.5);
    border-color: #475569;
  }

  :global(.dark-ui-world) .compare-col.wip,
  :global(.dark-ui-character) .compare-col.wip {
    background: rgba(30, 58, 138, 0.25);
    border-left-color: #334155;
  }

  :global(.dark-ui-world) .character-card,
  :global(.dark-ui-character) .character-card,
  :global(.dark-ui-world) .character-header,
  :global(.dark-ui-character) .character-header,
  :global(.dark-ui-world) .character-compact-header,
  :global(.dark-ui-character) .character-compact-header,
  :global(.dark-ui-world) .character-body,
  :global(.dark-ui-character) .character-body,
  :global(.dark-ui-world) .empty-state,
  :global(.dark-ui-character) .empty-state {
    background: rgba(15, 23, 42, 0.55);
    border-color: #334155;
    color: #cbd5e1;
  }

  :global(.dark-ui-world) .character-compact-header,
  :global(.dark-ui-character) .character-compact-header {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.92) 0%, rgba(30, 41, 59, 0.88) 100%);
    border-bottom-color: #334155;
  }

  :global(.dark-ui-world) .character-card.selected .character-header,
  :global(.dark-ui-character) .character-card.selected .character-header {
    background: linear-gradient(135deg, rgba(30, 64, 175, 0.42) 0%, rgba(30, 41, 59, 0.88) 100%);
    border-bottom: 1px solid rgba(96, 165, 250, 0.55);
  }

  :global(.dark-ui-world) .module-runner label,
  :global(.dark-ui-character) .module-runner label,
  :global(.dark-ui-world) .spawn-label,
  :global(.dark-ui-character) .spawn-label,
  :global(.dark-ui-world) .review-headline,
  :global(.dark-ui-character) .review-headline,
  :global(.dark-ui-world) .compact-name,
  :global(.dark-ui-character) .compact-name,
  :global(.dark-ui-world) .review-panel-header h3,
  :global(.dark-ui-character) .review-panel-header h3 {
    color: #e2e8f0;
  }

  :global(.dark-ui-world) .compact-hook,
  :global(.dark-ui-character) .compact-hook,
  :global(.dark-ui-world) .summary-loading,
  :global(.dark-ui-character) .summary-loading,
  :global(.dark-ui-world) .empty,
  :global(.dark-ui-character) .empty {
    color: #94a3b8;
  }

  :global(.dark-ui-world) .module-runner textarea,
  :global(.dark-ui-character) .module-runner textarea,
  :global(.dark-ui-world) .edit-area,
  :global(.dark-ui-character) .edit-area,
  :global(.dark-ui-world) .portrait-panel textarea,
  :global(.dark-ui-character) .portrait-panel textarea,
  :global(.dark-ui-world) .filename-input,
  :global(.dark-ui-character) .filename-input,
  :global(.dark-ui-world) .spawn-input,
  :global(.dark-ui-character) .spawn-input,
  :global(.dark-ui-world) .spawn-context,
  :global(.dark-ui-character) .spawn-context,
  :global(.dark-ui-world) .char-name-input,
  :global(.dark-ui-character) .char-name-input {
    background: #1e293b;
    border-color: #334155;
    color: #e2e8f0;
  }

  :global(.dark-ui-world) .suggest-btn,
  :global(.dark-ui-character) .suggest-btn,
  :global(.dark-ui-world) .random-btn,
  :global(.dark-ui-character) .random-btn,
  :global(.dark-ui-world) .select-btn,
  :global(.dark-ui-character) .select-btn,
  :global(.dark-ui-world) .save-char-btn,
  :global(.dark-ui-character) .save-char-btn,
  :global(.dark-ui-world) .edit-btn,
  :global(.dark-ui-character) .edit-btn,
  :global(.dark-ui-world) .confirm-btn,
  :global(.dark-ui-character) .confirm-btn,
  :global(.dark-ui-world) .cancel-btn,
  :global(.dark-ui-character) .cancel-btn,
  :global(.dark-ui-world) .delete-btn,
  :global(.dark-ui-character) .delete-btn,
  :global(.dark-ui-world) .collapse-side-btn,
  :global(.dark-ui-character) .collapse-side-btn {
    background: rgba(51, 65, 85, 0.42);
    border-color: #334155;
    color: #cbd5e1;
  }

  :global(.dark-ui-world) .character-actions .select-btn,
  :global(.dark-ui-character) .character-actions .select-btn,
  :global(.dark-ui-world) .character-actions .save-char-btn,
  :global(.dark-ui-character) .character-actions .save-char-btn,
  :global(.dark-ui-world) .character-actions .edit-btn,
  :global(.dark-ui-character) .character-actions .edit-btn,
  :global(.dark-ui-world) .character-actions .delete-btn,
  :global(.dark-ui-character) .character-actions .delete-btn {
    background: rgba(30, 41, 59, 0.9);
    border-color: #64748b;
    color: #e2e8f0;
    text-shadow: 0 1px 0 rgba(2, 6, 23, 0.4);
  }

  :global(.dark-ui-world) .character-actions .icon-action,
  :global(.dark-ui-character) .character-actions .icon-action {
    width: 2rem;
    border-radius: 999px;
    padding: 0;
  }

  :global(.dark-ui-world) .character-actions .edit-btn.icon-action,
  :global(.dark-ui-character) .character-actions .edit-btn.icon-action {
    border-color: #475569;
    color: #bfdbfe;
  }

  :global(.dark-ui-world) .character-actions .delete-btn.icon-action,
  :global(.dark-ui-character) .character-actions .delete-btn.icon-action {
    border-color: rgba(239, 68, 68, 0.55);
    color: #fecaca;
    background: rgba(127, 29, 29, 0.28);
  }

  :global(.dark-ui-world) .character-actions .edit-btn.icon-action:hover:not(:disabled),
  :global(.dark-ui-world) .character-actions .delete-btn.icon-action:hover:not(:disabled),
  :global(.dark-ui-character) .character-actions .edit-btn.icon-action:hover:not(:disabled),
  :global(.dark-ui-character) .character-actions .delete-btn.icon-action:hover:not(:disabled) {
    background: rgba(51, 65, 85, 0.96);
    border-color: #93c5fd;
  }

  :global(.dark-ui-world) .character-actions .delete-btn.icon-action:hover:not(:disabled),
  :global(.dark-ui-character) .character-actions .delete-btn.icon-action:hover:not(:disabled) {
    background: rgba(127, 29, 29, 0.5);
    border-color: #ef4444;
  }

  :global(.dark-ui-world) .collapse-btn,
  :global(.dark-ui-character) .collapse-btn {
    color: #cbd5e1;
  }

  :global(.dark-ui-world) .save-btn,
  :global(.dark-ui-character) .save-btn,
  :global(.dark-ui-world) .select-btn.is-selected,
  :global(.dark-ui-character) .select-btn.is-selected {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    border-color: #1d4ed8;
    color: #eff6ff;
  }

  @media (max-width: 900px) {
    .character-body {
      grid-template-columns: 1fr;
    }

    .portrait {
      width: 100%;
      max-width: 256px;
    }

    .character-header {
      flex-wrap: wrap;
    }

    .character-actions {
      width: 100%;
      justify-content: flex-end;
    }
  }

  @media (max-width: 1040px) {
    .panel-shell {
      grid-template-columns: 1fr;
    }

    .review-panel {
      position: static;
    }
  }

  @media (max-width: 780px) {
    .two-col {
      grid-template-columns: 1fr;
    }

    .compare-col.wip {
      border-left: none;
      border-top: 1px solid #cbd5e1;
    }
  }
</style>
