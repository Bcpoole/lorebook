<script>
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

  async function generateStory() {
    if (!rawIdea.trim() || loading || !llmConnected) return
    loading = true
    error = ''
    savedName = ''
    try {
      const res = await fetch('/api/story', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
    } catch {
      error = 'Failed to generate story.'
    } finally {
      loading = false
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
</script>

<section class="story-page">
  <h2>Story Artifact</h2>
  <textarea bind:value={rawIdea} rows="4" placeholder="Describe the story concept..." disabled={loading}></textarea>
  <div class="actions">
    <button onclick={generateStory} disabled={!rawIdea.trim() || loading || !llmConnected}>
      {loading ? 'Generating…' : 'Generate Story'}
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
  textarea { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.6rem; }
  .actions { display: flex; gap: 0.5rem; }
  button { border: 1px solid #2563eb; background: #2563eb; color: #fff; border-radius: 6px; padding: 0.4rem 0.75rem; cursor: pointer; }
  button.secondary { background: #334155; border-color: #334155; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .artifact { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; background: #fff; }
  .tags { color: #0369a1; }
  pre { background: #0f172a; color: #e2e8f0; padding: 0.6rem; border-radius: 6px; overflow: auto; }
  .error { color: #b91c1c; }
  .ok { color: #047857; }
</style>
