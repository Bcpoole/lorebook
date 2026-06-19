<script>
  import { onDestroy } from 'svelte'

  import MarkdownBlock from './MarkdownBlock.svelte'

  const STORY_ACTIONS = {
    suggest_next_beat: 'Suggest Next Beat',
    rewrite_opening: 'Rewrite Opening',
    add_character: 'Add Character',
    add_location: 'Add Location',
    add_object: 'Add Object',
    add_example: 'Add Example',
  }

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
  } = $props()

  let activeAbortController = $state(null)
  let activeGenerationId = $state(0)
  let showRawJson = $state(false)
  let itemActionKey = $state('')
  let editingItemKey = $state('')
  let editingItemDraft = $state(null)

  function isAbortError(error) {
    return error?.name === 'AbortError'
  }

  function itemKey(section, index) {
    return `${section}:${index}`
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
      story = payload.story_artifact ?? payload.state?.story_artifact ?? story
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
    const generationId = ++activeGenerationId
    const controller = new AbortController()
    activeAbortController = controller
    loading = true
    error = ''
    savedName = ''
    try {
      const res = await fetch('/api/story', {
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

  async function saveStory() {
    if (!story) return
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        raw_idea: rawIdea,
        state: { story_artifact: story, story_setup: storySetup, story_instruction: storyInstruction, characters: [] },
        meta: { source: 'story', story_generation_quality: generationQuality },
      }),
    })
    if (!res.ok) {
      error = 'Failed to save story.'
      return
    }
    const payload = await res.json()
    savedName = payload.filename
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
    generationQuality = ''
    storySetup = defaultStorySetup()
    storyInstruction = ''
    showRawJson = false
  }

  onDestroy(() => {
    stopStoryGeneration()
  })
</script>

<section class="story-page dark-ui-page dark-ui-story">
  <div class="page-header">
    <h2>Story Artifact</h2>
    <button class="reset-btn" type="button" onclick={handleResetStoryPage}>Reset</button>
  </div>
  <textarea bind:value={rawIdea} rows="4" placeholder="Describe the story concept..." disabled={loading}></textarea>
  <div class="setup-grid">
    <label>Protagonist seed<input type="text" value={storySetup?.protagonist ?? ''} oninput={(event) => updateStorySetup('protagonist', event.currentTarget.value)} placeholder="Name, archetype, POV..." disabled={loading} /></label>
    <label>Opening preference<input type="text" value={storySetup?.opening_preference ?? ''} oninput={(event) => updateStorySetup('opening_preference', event.currentTarget.value)} placeholder="Cold open, dialogue-first..." disabled={loading} /></label>
    <label>Output format<input type="text" value={storySetup?.output_format ?? ''} oninput={(event) => updateStorySetup('output_format', event.currentTarget.value)} placeholder="Novel prose, beat sheet..." disabled={loading} /></label>
    <label>Tone<input type="text" value={storySetup?.tone ?? ''} oninput={(event) => updateStorySetup('tone', event.currentTarget.value)} placeholder="Whimsical, grimdark, noir..." disabled={loading} /></label>
    <label>Length target<input type="text" value={storySetup?.length_target ?? ''} oninput={(event) => updateStorySetup('length_target', event.currentTarget.value)} placeholder="Short scene, chapter..." disabled={loading} /></label>
  </div>
  <textarea bind:value={storyInstruction} rows="3" placeholder="Instruction for this pass (optional)..." disabled={loading}></textarea>
  <div class="actions">
    <button onclick={handleGenerateClick} disabled={!loading && (!rawIdea.trim() || !llmConnected)}>
      {loading ? 'Generating… Click to stop' : 'Generate Story'}
    </button>
    <button class="secondary" onclick={saveStory} disabled={!story}>Save</button>
    <button class="ghost" type="button" onclick={() => (showRawJson = !showRawJson)} disabled={!story}>
      {showRawJson ? 'Hide Raw JSON' : 'Show Raw JSON'}
    </button>
  </div>
  <div class="actions">
    {#each Object.entries(STORY_ACTIONS) as [action, label]}
      <button class="secondary" type="button" onclick={() => generateStory(action)} disabled={!story || loading || !llmConnected}>
        {label}
      </button>
    {/each}
  </div>
  {#if error}<p class="error">{error}</p>{/if}
  {#if savedName}<p class="ok">Saved as {savedName}</p>{/if}
  {#if generationQuality}<p class="meta">Generation quality: {generationQuality}</p>{/if}

  {#if story}
    <article class="artifact">
      <header class="artifact-header">
        <h3>{story.title}</h3>
        {#if story.tags?.length}
          <p class="tags">{story.tags.join(', ')}</p>
        {/if}
      </header>
      <p>{story.description || 'No summary yet.'}</p>
      <div class="overview-grid">
        <p><strong>Setting:</strong> {story.setting || 'Not set'}</p>
        <p><strong>Style:</strong> {story.style || 'Not set'}</p>
      </div>

      <section>
        <h4>Plot beats</h4>
        {#if story.plot?.length}
          <ol>
            {#each story.plot as beat}
              <li>{beat}</li>
            {/each}
          </ol>
        {:else}
          <p class="empty">No plot beats generated yet.</p>
        {/if}
      </section>

      <section>
        <h4>Characters</h4>
        {#if story.characters_artifact?.length}
          {#each story.characters_artifact as character, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('characters_artifact', index)}
                <label>Name <input type="text" value={editingItemDraft?.name ?? ''} oninput={(event) => updateEditingField('name', event.currentTarget.value)} /></label>
                <label>Role <input type="text" value={editingItemDraft?.role ?? ''} oninput={(event) => updateEditingField('role', event.currentTarget.value)} /></label>
                <label>Summary <textarea rows="3" value={editingItemDraft?.summary ?? ''} oninput={(event) => updateEditingField('summary', event.currentTarget.value)}></textarea></label>
                <label>Tags <input type="text" value={(editingItemDraft?.tags ?? []).join(', ')} oninput={(event) => updateEditingTags(event.currentTarget.value)} /></label>
              {:else}
                <p><strong>{character.name || 'Unnamed character'}</strong> · {character.role || 'character'}</p>
                <p>{character.summary || 'No summary available.'}</p>
                {#if character.image_data}
                  <img class="entity-image" src={character.image_data} alt={`Character art for ${character.name || 'character'}`} />
                {:else if character.image_name}
                  <p class="meta">Image: {character.image_name}</p>
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('characters_artifact', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('characters_artifact', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button class="ghost small" type="button" onclick={() => beginEditItem('characters_artifact', index, character)} disabled={Boolean(itemActionKey) || loading}>Edit</button>
                  <button class="ghost small danger" type="button" onclick={() => deleteItem('characters_artifact', index)} disabled={Boolean(itemActionKey) || loading}>Delete</button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('characters_artifact', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No characters generated yet.</p>
        {/if}
      </section>

      <section>
        <h4>Locations</h4>
        {#if story.locations?.length}
          {#each story.locations as location, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('locations', index)}
                <label>Name <input type="text" value={editingItemDraft?.name ?? ''} oninput={(event) => updateEditingField('name', event.currentTarget.value)} /></label>
                <label>Description <textarea rows="3" value={editingItemDraft?.description ?? ''} oninput={(event) => updateEditingField('description', event.currentTarget.value)}></textarea></label>
                <label>Tags <input type="text" value={(editingItemDraft?.tags ?? []).join(', ')} oninput={(event) => updateEditingTags(event.currentTarget.value)} /></label>
              {:else}
                <p><strong>{location.name || 'Unnamed location'}</strong></p>
                <p>{location.description || 'No description available.'}</p>
                {#if location.image_data}
                  <img class="entity-image" src={location.image_data} alt={`Location art for ${location.name || 'location'}`} />
                {:else if location.image_name}
                  <p class="meta">Image: {location.image_name}</p>
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('locations', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('locations', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button class="ghost small" type="button" onclick={() => beginEditItem('locations', index, location)} disabled={Boolean(itemActionKey) || loading}>Edit</button>
                  <button class="ghost small danger" type="button" onclick={() => deleteItem('locations', index)} disabled={Boolean(itemActionKey) || loading}>Delete</button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('locations', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No locations generated yet.</p>
        {/if}
      </section>

      <section>
        <h4>Objects</h4>
        {#if story.objects?.length}
          {#each story.objects as item, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('objects', index)}
                <label>Name <input type="text" value={editingItemDraft?.name ?? ''} oninput={(event) => updateEditingField('name', event.currentTarget.value)} /></label>
                <label>Description <textarea rows="3" value={editingItemDraft?.description ?? ''} oninput={(event) => updateEditingField('description', event.currentTarget.value)}></textarea></label>
                <label>Tags <input type="text" value={(editingItemDraft?.tags ?? []).join(', ')} oninput={(event) => updateEditingTags(event.currentTarget.value)} /></label>
              {:else}
                <p><strong>{item.name || 'Unnamed object'}</strong></p>
                <p>{item.description || 'No description available.'}</p>
                {#if item.image_data}
                  <img class="entity-image" src={item.image_data} alt={`Object art for ${item.name || 'object'}`} />
                {:else if item.image_name}
                  <p class="meta">Image: {item.image_name}</p>
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('objects', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('objects', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button class="ghost small" type="button" onclick={() => beginEditItem('objects', index, item)} disabled={Boolean(itemActionKey) || loading}>Edit</button>
                  <button class="ghost small danger" type="button" onclick={() => deleteItem('objects', index)} disabled={Boolean(itemActionKey) || loading}>Delete</button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('objects', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No objects generated yet.</p>
        {/if}
      </section>

      <section>
        <h4>Opening</h4>
        {#if story.opening}
          <MarkdownBlock source={story.opening} />
        {:else}
          <p class="empty">No opening excerpt generated yet.</p>
        {/if}
      </section>

      <section>
        <h4>Examples</h4>
        {#if story.examples?.length}
          {#each story.examples as example, index}
            <div class="entity-card">
              {#if editingItemKey === itemKey('examples', index)}
                <label>Label <input type="text" value={editingItemDraft?.label ?? ''} oninput={(event) => updateEditingField('label', event.currentTarget.value)} /></label>
                <label>Text <textarea rows="3" value={editingItemDraft?.text ?? ''} oninput={(event) => updateEditingField('text', event.currentTarget.value)}></textarea></label>
              {:else}
                <p><strong>{example.label || 'Example'}</strong></p>
                <p>{example.text || 'No text provided.'}</p>
                {#if example.image_data}
                  <img class="entity-image" src={example.image_data} alt={`Example art for ${example.label || 'example'}`} />
                {:else if example.image_name}
                  <p class="meta">Image: {example.image_name}</p>
                {/if}
              {/if}
              <div class="entity-actions">
                {#if editingItemKey === itemKey('examples', index)}
                  <button class="ghost small" type="button" onclick={() => saveItemEdit('examples', index)} disabled={Boolean(itemActionKey) || loading}>Save</button>
                  <button class="ghost small" type="button" onclick={cancelEditItem} disabled={Boolean(itemActionKey) || loading}>Cancel</button>
                {:else}
                  <button class="ghost small" type="button" onclick={() => beginEditItem('examples', index, example)} disabled={Boolean(itemActionKey) || loading}>Edit</button>
                  <button class="ghost small danger" type="button" onclick={() => deleteItem('examples', index)} disabled={Boolean(itemActionKey) || loading}>Delete</button>
                  <button class="ghost small" type="button" onclick={() => generateItemImage('examples', index)} disabled={Boolean(itemActionKey) || loading || !llmConnected}>Generate Image</button>
                {/if}
              </div>
            </div>
          {/each}
        {:else}
          <p class="empty">No examples generated yet.</p>
        {/if}
      </section>

      {#if showRawJson}
        <pre>{JSON.stringify(story, null, 2)}</pre>
      {/if}
    </article>
  {/if}
</section>

<style>
  .story-page { display: grid; gap: 0.75rem; margin-top: 0; }
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
  h2 { margin: 0; color: var(--lb-page-heading, #0f172a); }
  textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--lb-input-border, #cbd5e1); border-radius: 6px; padding: 0.6rem; background: var(--lb-input-bg, #fff); color: var(--lb-input-fg, #0f172a); }
  .setup-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.6rem; }
  .setup-grid label { display: grid; gap: 0.25rem; font-size: 0.85rem; color: var(--lb-text-2, #475569); }
  .setup-grid input { border: 1px solid var(--lb-input-border, #cbd5e1); border-radius: 6px; padding: 0.45rem 0.55rem; background: var(--lb-input-bg, #fff); color: var(--lb-input-fg, #0f172a); }
  .actions { display: flex; gap: 0.5rem; }
  .actions { flex-wrap: wrap; }
  button { border: 1px solid var(--lb-accent-2, #2563eb); background: linear-gradient(135deg, var(--lb-accent-1, #2563eb), var(--lb-accent-2, #1d4ed8)); color: #fff; border-radius: 6px; padding: 0.4rem 0.75rem; cursor: pointer; }
  .reset-btn { border-color: var(--lb-btn-secondary-border, #94a3b8); background: var(--lb-btn-secondary-bg, #fff); color: var(--lb-btn-secondary-fg, #334155); }
  .reset-btn:hover { border-color: var(--lb-border-2, #64748b); background: rgba(71, 85, 105, 0.5); }
  button.secondary { background: rgba(51, 65, 85, 0.75); border-color: var(--lb-border-1, #334155); color: var(--lb-text-1, #fff); }
  button.ghost { border-color: var(--lb-border-1, #94a3b8); background: transparent; color: var(--lb-text-2, #334155); }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .artifact { border: 1px solid var(--lb-border-1, #e2e8f0); border-radius: 8px; padding: 0.9rem; background: rgba(15, 23, 42, 0.5); display: grid; gap: 0.8rem; }
  .artifact-header { display: flex; align-items: baseline; justify-content: space-between; gap: 0.8rem; }
  .overview-grid { display: grid; gap: 0.4rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
  .entity-card { border: 1px solid var(--lb-border-1, #e2e8f0); border-radius: 8px; padding: 0.55rem 0.65rem; background: rgba(15, 23, 42, 0.38); }
  .entity-card label { display: grid; gap: 0.2rem; margin-bottom: 0.35rem; color: var(--lb-text-2, #475569); font-size: 0.85rem; }
  .entity-card input,
  .entity-card textarea { border: 1px solid var(--lb-input-border, #cbd5e1); border-radius: 6px; padding: 0.4rem 0.5rem; background: var(--lb-input-bg, #fff); color: var(--lb-input-fg, #0f172a); }
  .entity-actions { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
  .entity-image { margin-top: 0.35rem; width: 100%; max-width: 260px; border-radius: 8px; border: 1px solid var(--lb-border-1, #cbd5e1); background: rgba(15, 23, 42, 0.5); }
  button.small { padding: 0.3rem 0.55rem; font-size: 0.82rem; }
  button.danger { border-color: #b91c1c; color: #fecaca; }
  .empty { color: var(--lb-page-muted, #64748b); font-style: italic; }
  .meta { color: var(--lb-page-muted, #334155); font-size: 0.9rem; }
  .tags { color: #7dd3fc; }
  pre { background: #0f172a; color: #e2e8f0; padding: 0.6rem; border-radius: 6px; overflow: auto; }
  .error { color: #fca5a5; }
  .ok { color: #6ee7b7; }
</style>
