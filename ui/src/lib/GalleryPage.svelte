<script>
  import { onMount } from 'svelte'
  import MarkdownBlock from './MarkdownBlock.svelte'
  import PokeHoloCard from './PokeHoloCard.svelte'

  let items = $state([])
  let loading = $state(false)
  let error = $state('')
  let search = $state('')
  let tag = $state('')
  let selected = $state(null)

  async function loadGallery() {
    loading = true
    error = ''
    try {
      const params = new URLSearchParams()
      if (search.trim()) params.set('search', search.trim())
      if (tag.trim()) params.set('tag', tag.trim().toLowerCase())
      const res = await fetch(`/api/gallery?${params}`)
      if (!res.ok) {
        error = 'Failed to load gallery.'
        return
      }
      const payload = await res.json()
      items = payload.items ?? []
    } catch {
      error = 'Failed to load gallery.'
    } finally {
      loading = false
    }
  }

  async function openRun(runId) {
    const res = await fetch(`/api/runs/${runId}`)
    if (!res.ok) return
    selected = await res.json()
  }

  async function setRole(runId, index, role) {
    const res = await fetch('/api/character-role', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: runId, character_index: index, role }),
    })
    if (!res.ok) return
    await loadGallery()
    if (selected?.run_id === runId) {
      selected = await res.json().then((payload) => payload.run)
    }
  }

  onMount(() => {
    void loadGallery()
  })
</script>

<section class="gallery-page">
  <h2>Saved Gallery</h2>
  <div class="filters">
    <input placeholder="Search title, description, tags" bind:value={search} />
    <input placeholder="Tag" bind:value={tag} />
    <button onclick={loadGallery} disabled={loading}>{loading ? 'Loading…' : 'Apply'}</button>
  </div>
  {#if error}<p class="error">{error}</p>{/if}

  <div class="grid">
    {#each items as item}
      <PokeHoloCard {item} onopen={openRun} />
    {/each}
  </div>

  {#if selected}
    <div
      class="modal"
      role="button"
      tabindex="0"
      onclick={(event) => event.target === event.currentTarget && (selected = null)}
      onkeydown={(event) => (event.key === 'Enter' || event.key === 'Escape') && (selected = null)}
    >
      <div class="modal-card">
        <button class="close" onclick={() => (selected = null)}>✕</button>
        <h3>{selected.preview?.title || selected.raw_idea}</h3>
        {#if selected.state?.story_artifact}
          <MarkdownBlock source={selected.state.story_artifact.opening || ''} />
        {/if}
        {#if selected.state?.characters?.length}
          {#each selected.state.characters as character, index}
            <div class="character-item">
              <strong>{character.name || `Character ${index + 1}`}</strong>
              <span class="role">{character.role || 'character'}</span>
              <div class="role-actions">
                <button onclick={() => setRole(selected.run_id, index, 'character')}>Character</button>
                <button onclick={() => setRole(selected.run_id, index, 'persona')}>Persona</button>
              </div>
              <MarkdownBlock source={character.details || ''} />
            </div>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</section>

<style>
  .gallery-page { display: grid; gap: 0.65rem; margin-top: 1rem; }
  .filters { display: flex; gap: 0.45rem; }
  input { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.4rem 0.55rem; }
  button { border: 1px solid #334155; background: #334155; color: #fff; border-radius: 6px; padding: 0.35rem 0.7rem; cursor: pointer; }
  .grid { display: grid; gap: 0.65rem; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
  .modal { position: fixed; inset: 0; background: rgba(2, 6, 23, 0.72); display: grid; place-items: center; padding: 1rem; z-index: 55; }
  .modal-card { width: min(860px, 100%); max-height: 90vh; overflow: auto; background: #fff; border-radius: 12px; border: 1px solid #cbd5e1; padding: 0.8rem; position: relative; }
  .close { position: absolute; top: 0.4rem; right: 0.4rem; }
  .character-item { border-top: 1px solid #e2e8f0; margin-top: 0.6rem; padding-top: 0.6rem; }
  .role { margin-left: 0.35rem; border: 1px solid #0ea5e9; border-radius: 999px; padding: 0.1rem 0.5rem; font-size: 0.75rem; color: #0369a1; }
  .role-actions { display: inline-flex; gap: 0.3rem; margin-left: 0.5rem; }
  .error { color: #b91c1c; }
</style>
