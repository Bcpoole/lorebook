<script>
  import { onDestroy } from 'svelte'

  import MarkdownBlock from './MarkdownBlock.svelte'

  let {
    llmConnected = true,
    personaId = 'blank',
    experimentationConfig = {},
    rawIdea = $bindable(''),
    loading = $bindable(false),
    error = $bindable(''),
    story = $bindable(null),
    savedName = $bindable(''),
  } = $props()

  let activeAbortController = $state(null)
  let activeGenerationId = $state(0)

  function isAbortError(error) {
    return error?.name === 'AbortError'
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
    void generateStory()
  }

  async function generateStory() {
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
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        error = payload?.detail || 'Failed to generate story.'
        return
      }
      const payload = await res.json()
      story = payload.story_artifact
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
        state: { story_artifact: story, characters: [] },
        meta: { source: 'story' },
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
  }

  onDestroy(() => {
    stopStoryGeneration()
  })
</script>

<section class="story-page">
  <div class="page-header">
    <h2>Story Artifact</h2>
    <button class="reset-btn" type="button" onclick={handleResetStoryPage}>Reset</button>
  </div>
  <textarea bind:value={rawIdea} rows="4" placeholder="Describe the story concept..." disabled={loading}></textarea>
  <div class="actions">
    <button onclick={handleGenerateClick} disabled={!loading && (!rawIdea.trim() || !llmConnected)}>
      {loading ? 'Generating… Click to stop' : 'Generate Story'}
    </button>
    <button class="secondary" onclick={saveStory} disabled={!story}>Save</button>
  </div>
  {#if error}<p class="error">{error}</p>{/if}
  {#if savedName}<p class="ok">Saved as {savedName}</p>{/if}

  {#if story}
    <article class="artifact">
      <h3>{story.title}</h3>
      <p>{story.description}</p>
      {#if story.tags?.length}
        <p class="tags">{story.tags.join(', ')}</p>
      {/if}
      {#if story.opening}
        <MarkdownBlock source={story.opening} />
      {/if}
      <pre>{JSON.stringify(story, null, 2)}</pre>
    </article>
  {/if}
</section>

<style>
  .story-page { display: grid; gap: 0.65rem; margin-top: 1rem; }
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
  h2 { margin: 0; }
  textarea { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.6rem; }
  .actions { display: flex; gap: 0.5rem; }
  button { border: 1px solid #2563eb; background: #2563eb; color: #fff; border-radius: 6px; padding: 0.4rem 0.75rem; cursor: pointer; }
  .reset-btn { border-color: #94a3b8; background: #fff; color: #334155; }
  .reset-btn:hover { border-color: #64748b; background: #f8fafc; }
  button.secondary { background: #334155; border-color: #334155; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .artifact { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; background: #fff; }
  .tags { color: #0369a1; }
  pre { background: #0f172a; color: #e2e8f0; padding: 0.6rem; border-radius: 6px; overflow: auto; }
  .error { color: #b91c1c; }
  .ok { color: #047857; }
</style>
