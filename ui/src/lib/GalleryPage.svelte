<script>
  import { onMount } from 'svelte'
  import MarkdownBlock from './MarkdownBlock.svelte'
  import PokeHoloCard from './PokeHoloCard.svelte'
  import StoryArtifactModal from './StoryArtifactModal.svelte'
  import LocationModal from './LocationModal.svelte'
  import ObjectModal from './ObjectModal.svelte'

  let {
    title = 'Saved Gallery',
    tabs = [
      { id: 'character', label: 'Character', artifactType: 'character' },
      { id: 'location', label: 'Location', artifactType: 'location' },
      { id: 'object', label: 'Object', artifactType: 'object' },
    ],
    initialTab = 'character',
    enableCharacterModal = true,
  } = $props()

  // ── State ──────────────────────────────────────────────────
  let items = $state([])
  let loading = $state(false)
  let error = $state('')
  let search = $state('')
  let tag = $state('')
  let favoritesOnly = $state(false)
  let activeArtifactTab = $state('character')

  // Modal
  let selectedItem = $state(null) // gallery item (immediate, from local list)
  let selected = $state(null) // full run object (loaded from API)
  let selectedCharacterId = $state('')
  let modalLoading = $state(false)
  let flipped = $state(false)
  let activeTab = $state('bio')
  let roleDdOpen = $state(false)
  let relationshipNodeCache = $state({})
  let relationshipLookupPending = $state({})
  let showStoryModal = $state(false)

  // Navigation history (for relationship traversal)
  let navHistory = $state([]) // [{run_id, character_id, character_name}]
  let navForward = $state([]) // [{run_id, character_id, character_name}]

  const MAX_NAV_DEPTH = 20
  let activeArtifactType = $derived.by(() => {
    const current = tabs.find((tab) => tab.id === activeArtifactTab) ?? tabs[0]
    return current?.artifactType ?? 'character'
  })
  let showCharacterModal = $derived(enableCharacterModal && activeArtifactType === 'character')

  let runCharacters = $derived(selected?.state?.characters ?? [])
  let currentCharacter = $derived.by(() => {
    if (!Array.isArray(runCharacters) || runCharacters.length === 0) return null
    if (!selectedCharacterId) return runCharacters[0] ?? null
    return runCharacters.find((character) => character?.id === selectedCharacterId) ?? runCharacters[0] ?? null
  })
  let currentCharacterIndex = $derived.by(() => {
    if (!currentCharacter || !Array.isArray(runCharacters)) return 0
    const idx = runCharacters.findIndex((character) => character?.id === currentCharacter?.id)
    return idx >= 0 ? idx : 0
  })
  let relationshipEntries = $derived.by(() => {
    if (!currentCharacter?.relationships || typeof currentCharacter.relationships !== 'object') return []
    return Object.entries(currentCharacter.relationships)
      .filter(([urn, label]) => String(urn).trim() && String(label).trim())
      .map(([target_urn, relationship_label]) => ({ target_urn, relationship_label }))
  })
  let relationshipNodes = $derived.by(() => {
    return relationshipEntries.map((entry) => {
      const localMatch = runCharacters.find((character) => character?.id === entry.target_urn) ?? null
      const cached = relationshipNodeCache[entry.target_urn] ?? null
      const resolvedCharacter = localMatch ?? cached?.character ?? null
      return {
        ...entry,
        run_id: localMatch ? selected?.run_id : (cached?.run_id ?? ''),
        name: resolvedCharacter?.name || trimUrn(entry.target_urn),
        avatar_data: resolvedCharacter?.image_data || '',
        loading: Boolean(relationshipLookupPending[entry.target_urn]) && !resolvedCharacter,
      }
    })
  })

  // ── API helpers ────────────────────────────────────────────
  async function loadGallery() {
    loading = true
    error = ''
    try {
      const params = new URLSearchParams()
      if (search.trim()) params.set('search', search.trim())
      if (tag.trim()) params.set('tag', tag.trim().toLowerCase())
      if (favoritesOnly) params.set('favorites_only', 'true')
      if (activeArtifactType) params.set('artifact_type', activeArtifactType)
      const res = await fetch(`/api/gallery?${params}`)
      if (!res.ok) { error = 'Failed to load gallery.'; return }
      const payload = await res.json()
      items = payload.items ?? []
    } catch {
      error = 'Failed to load gallery.'
    } finally {
      loading = false
    }
  }

  async function openRun(itemOrRunId) {
    if (!showCharacterModal && activeArtifactType !== 'story' && activeArtifactType !== 'location' && activeArtifactType !== 'object') return
    const targetItem = typeof itemOrRunId === 'object' && itemOrRunId
      ? itemOrRunId
      : items.find((i) => i.run_id === itemOrRunId) ?? null
    const runId = targetItem?.run_id ?? String(itemOrRunId || '')
    selectedItem = targetItem
    selected = null
    selectedCharacterId = ''
    flipped = false
    showStoryModal = false
    activeTab = 'bio'
    roleDdOpen = false
    navHistory = []
    navForward = []
    modalLoading = true
    try {
      const params = new URLSearchParams()
      if (targetItem?.artifact_type) params.set('artifact_type', targetItem.artifact_type)
      const suffix = params.toString() ? `?${params}` : ''
      const res = await fetch(`/api/runs/${runId}${suffix}`)
      if (!res.ok) return
      selected = await res.json()
      const artifactType = targetItem?.artifact_type || selected?.artifact_type
      if (artifactType === 'story') {
        showStoryModal = true
      } else if (artifactType === 'location' || artifactType === 'object') {
        showStoryModal = true
      } else {
        selectedCharacterId = selected?.state?.characters?.[0]?.id ?? ''
      }
    } finally {
      modalLoading = false
    }
  }

  async function navigateToCharacter(targetEntry, newHistory, newForward) {
    if (!targetEntry?.run_id) return
    modalLoading = true
    flipped = true
    activeTab = 'bio'
    roleDdOpen = false
    try {
      if (selected?.run_id === targetEntry.run_id) {
        selectedCharacterId = targetEntry.character_id || selectedCharacterId
      } else {
        const params = new URLSearchParams()
        if (targetEntry?.artifact_type) params.set('artifact_type', targetEntry.artifact_type)
        const suffix = params.toString() ? `?${params}` : ''
        const res = await fetch(`/api/runs/${targetEntry.run_id}${suffix}`)
        if (!res.ok) return
        selected = await res.json()
        selectedItem = items.find((i) => i.run_id === targetEntry.run_id) ?? selectedItem
        const fallbackId = selected?.state?.characters?.[0]?.id ?? ''
        selectedCharacterId = targetEntry.character_id || fallbackId
      }
      navHistory = newHistory
      navForward = newForward
    } finally {
      modalLoading = false
    }
  }

  function closeModal() {
    selectedItem = null
    selected = null
    selectedCharacterId = ''
    flipped = false
    navHistory = []
    navForward = []
  }

  async function toggleFavorite(runId) {
    const item = items.find((entry) => entry.run_id === runId) ?? selectedItem
    const params = new URLSearchParams()
    if (item?.artifact_type) params.set('artifact_type', item.artifact_type)
    const suffix = params.toString() ? `?${params}` : ''
    const res = await fetch(`/api/gallery/${runId}/favorite${suffix}`, { method: 'POST' })
    if (!res.ok) return
    const payload = await res.json()
    items = items.map((i) => (
      i.run_id === runId && (!item?.artifact_type || i.artifact_type === item.artifact_type)
        ? { ...i, favorite: payload.favorite }
        : i
    ))
    if (selectedItem?.run_id === runId && (!item?.artifact_type || selectedItem.artifact_type === item.artifact_type)) {
      selectedItem = { ...selectedItem, favorite: payload.favorite }
    }
  }

  async function setRole(index, role) {
    if (!selected) return
    roleDdOpen = false
    const res = await fetch('/api/character-role', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_id: selected.run_id,
        artifact_type: selected.artifact_type || selectedItem?.artifact_type || '',
        character_index: index,
        role,
      }),
    })
    if (!res.ok) return
    const payload = await res.json()
    selected = payload.run
    await loadGallery()
    if (selectedItem) {
      selectedItem = items.find((i) => i.run_id === selected?.run_id) ?? selectedItem
    }
  }

  // ── Navigation helpers ─────────────────────────────────────
  function capNav(entries) {
    if (!Array.isArray(entries)) return []
    if (entries.length <= MAX_NAV_DEPTH) return entries
    return entries.slice(entries.length - MAX_NAV_DEPTH)
  }

  function currentNavEntry() {
    if (!selected || !currentCharacter) return null
    return {
      run_id: selected.run_id,
      artifact_type: selected.artifact_type || selectedItem?.artifact_type || '',
      character_id: String(currentCharacter.id || ''),
      character_name: currentCharacter.name || 'Character',
    }
  }

  function navBack() {
    if (navHistory.length === 0 || !selected) return
    const entry = currentNavEntry()
    if (!entry) return
    const newForward = [entry, ...navForward].slice(0, MAX_NAV_DEPTH)
    const newHistory = navHistory.slice(0, -1)
    const target = navHistory[navHistory.length - 1]
    void navigateToCharacter(target, newHistory, newForward)
  }

  function navForwardFn() {
    if (navForward.length === 0 || !selected) return
    const entry = currentNavEntry()
    if (!entry) return
    const newHistory = capNav([...navHistory, entry])
    const newForward = navForward.slice(1)
    const target = navForward[0]
    void navigateToCharacter(target, newHistory, newForward)
  }

  // ── Utilities ──────────────────────────────────────────────
  function cardVariantFor(item) {
    const isPersona = Array.isArray(item.roles) && item.roles.some((r) => String(r).toLowerCase() === 'persona')
    const isFavorite = Boolean(item?.favorite)

    // Mapping:
    // character -> no effect
    // character + favorite -> regular holo
    // persona -> reverse holo
    // persona + favorite -> cosmos holo
    if (isPersona && isFavorite) return 'cosmos-holo'
    if (isPersona) return 'reverse-holo'
    if (isFavorite) return 'holo'
    return null
  }

  function trimUrn(urn) {
    if (!urn) return ''
    const parts = urn.split(':')
    return parts[parts.length - 1] || urn
  }

  function initials(name) {
    const value = String(name || '').trim()
    if (!value) return '?'
    return value
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() || '')
      .join('')
  }

  function characterAvatar(character) {
    if (!character) return ''
    if (character.image_data) return character.image_data
    const cached = relationshipNodeCache[String(character.id || '')]
    if (cached?.character?.image_data) return cached.character.image_data
    return selectedItem?.avatar_data || ''
  }

  async function resolveCharacterReference(urn) {
    const normalizedUrn = String(urn || '').trim()
    if (!normalizedUrn) return null

    const localIndex = runCharacters.findIndex((character) => character?.id === normalizedUrn)
    if (localIndex >= 0) {
      return {
        run_id: selected?.run_id || '',
        artifact_type: selected?.artifact_type || selectedItem?.artifact_type || '',
        character_index: localIndex,
        character: runCharacters[localIndex],
      }
    }

    const cached = relationshipNodeCache[normalizedUrn]
    if (cached) return cached
    if (relationshipLookupPending[normalizedUrn]) return null

    relationshipLookupPending = { ...relationshipLookupPending, [normalizedUrn]: true }
    try {
      const params = new URLSearchParams({ urn: normalizedUrn })
      const res = await fetch(`/api/characters/by-id?${params}`)
      if (!res.ok) return null
      const payload = await res.json()
      relationshipNodeCache = { ...relationshipNodeCache, [normalizedUrn]: payload }
      return payload
    } catch {
      return null
    } finally {
      relationshipLookupPending = { ...relationshipLookupPending, [normalizedUrn]: false }
    }
  }

  async function openRelationshipNode(targetUrn) {
    const target = String(targetUrn || '').trim()
    if (!target || !selected || !currentCharacter || target === currentCharacter.id) return

    const resolved = await resolveCharacterReference(target)
    if (!resolved?.run_id) return

    const currentEntry = currentNavEntry()
    if (!currentEntry) return
    const newHistory = capNav([...navHistory, currentEntry])
    const targetEntry = {
      run_id: resolved.run_id,
      artifact_type: resolved.artifact_type || '',
      character_id: target,
      character_name: resolved.character?.name || trimUrn(target),
    }
    void navigateToCharacter(targetEntry, newHistory, [])
  }

  function nodeBorderColor(characterId) {
    const target = String(characterId || '').trim()
    if (!target) return '#cbd5e1'
    if (currentCharacter?.id && target === currentCharacter.id) return '#1d4ed8'

    const backIndex = navHistory.map((entry) => entry.character_id).lastIndexOf(target)
    if (backIndex >= 0) {
      const depth = navHistory.length - backIndex
      const lightness = Math.max(82 - depth * 5, 24)
      return `hsl(214 74% ${lightness}%)`
    }

    const forwardIndex = navForward.findIndex((entry) => entry.character_id === target)
    if (forwardIndex >= 0) {
      const depth = forwardIndex + 1
      const lightness = Math.max(82 - depth * 5, 24)
      return `hsl(145 52% ${lightness}%)`
    }

    return '#cbd5e1'
  }

  function handleModalBackdrop(event) {
    if (event.target === event.currentTarget) closeModal()
  }

  function handleGlobalKeydown(event) {
    if (event.key === 'Escape' && selectedItem) closeModal()
  }

  $effect(() => {
    if (activeTab !== 'relationships' || !currentCharacter) return
    for (const { target_urn } of relationshipEntries) {
      const isLocal = runCharacters.some((character) => character?.id === target_urn)
      if (!isLocal && !relationshipNodeCache[target_urn] && !relationshipLookupPending[target_urn]) {
        void resolveCharacterReference(target_urn)
      }
    }
  })

  $effect(() => {
    activeArtifactType
    closeModal()
    void loadGallery()
  })

  onMount(() => {
    const configuredTab = tabs.some((tab) => tab.id === initialTab)
      ? initialTab
      : tabs[0]?.id ?? 'character'
    activeArtifactTab = configuredTab
  })
</script>

<svelte:window onkeydown={handleGlobalKeydown} />

<section class="gallery-page">
  <div class="gallery-topbar">
    <h2>{title}</h2>
  </div>

  <div class="artifact-tabs" role="tablist" aria-label={`${title} artifact types`}>
    {#each tabs as tab}
      <button
        type="button"
        class="artifact-tab-btn"
        class:active={activeArtifactTab === tab.id}
        role="tab"
        aria-selected={activeArtifactTab === tab.id}
        onclick={() => (activeArtifactTab = tab.id)}
      >
        {tab.label}
      </button>
    {/each}
  </div>

  <div class="filters">
    <input class="filter-input" placeholder="Search title, description, tags" bind:value={search} />
    <input class="filter-input filter-tag" placeholder="Tag" bind:value={tag} />
    <label class="fav-check">
      <input type="checkbox" bind:checked={favoritesOnly} />
      ★ Favorites only
    </label>
    <button class="apply-btn" onclick={loadGallery} disabled={loading}>
      {loading ? 'Loading…' : 'Apply'}
    </button>
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  <div class="grid">
    {#each items as item}
      <PokeHoloCard {item} onopen={showCharacterModal || activeArtifactType === 'story' || activeArtifactType === 'location' || activeArtifactType === 'object' ? openRun : (() => {})} variant={cardVariantFor(item)} />
    {/each}
    {#if !loading && items.length === 0}
      <p class="empty-note">No items found.</p>
    {/if}
  </div>
</section>

<!-- ── Modal ─────────────────────────────────────────────────── -->
{#if showCharacterModal && selectedItem}
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    aria-label={`Character: ${selectedItem.avatar_name || selectedItem.title}`}
    onclick={handleModalBackdrop}
    onkeydown={(e) => e.key === 'Escape' && closeModal()}
  >
    <div class="flip-scene" class:flipped>
      <div class="flip-card">

        <!-- FRONT FACE -->
        <div class="flip-face flip-front">
          <div class="front-inner">
            {#if selectedItem.avatar_data}
              <button
                class="front-img-btn"
                onclick={() => (flipped = true)}
                aria-label="Flip card to see details"
              >
                <img
                  class="front-img"
                  src={selectedItem.avatar_data}
                  alt={selectedItem.avatar_name || selectedItem.title}
                />
              </button>
            {:else}
              <div
                class="front-placeholder"
                role="button"
                tabindex="0"
                onclick={() => (flipped = true)}
                onkeydown={(e) => e.key === 'Enter' && (flipped = true)}
              >
                <span>{selectedItem.avatar_name || 'No Image'}</span>
              </div>
            {/if}

            <div class="front-overlay-top">
              <h2>{selectedItem.avatar_name || selectedItem.title}</h2>
            </div>

            {#if selectedItem.avatar_summary || selectedItem.description}
              <div class="front-overlay-bottom">
                <p>{selectedItem.avatar_summary || selectedItem.description}</p>
              </div>
            {/if}

            <button
              class="fav-btn front-fav"
              onclick={(e) => { e.stopPropagation(); void toggleFavorite(selectedItem.run_id) }}
              aria-label={selectedItem.favorite ? 'Remove from favorites' : 'Add to favorites'}
            >{selectedItem.favorite ? '★' : '☆'}</button>

            <button class="modal-close" onclick={closeModal} aria-label="Close">✕</button>

            <button class="flip-hint" onclick={() => (flipped = true)} aria-label="Flip card">
              Tap image to flip ↺
            </button>
          </div>
        </div>

        <!-- BACK FACE -->
        <div class="flip-face flip-back">
          <div class="back-inner">
            {#if modalLoading}
              <div class="modal-loading">
                <div class="spinner"></div>
                <p>Loading…</p>
              </div>
            {:else if selected && currentCharacter}
              <div class="back-layout">
                <!-- Left: avatar -->
                <div class="back-avatar">
                  {#if characterAvatar(currentCharacter)}
                    <img
                      src={characterAvatar(currentCharacter)}
                      alt={currentCharacter.name}
                      class="back-avatar-img"
                    />
                  {:else}
                    <div class="back-avatar-fallback">{initials(currentCharacter.name)}</div>
                  {/if}
                </div>

                <!-- Right: tabs -->
                <div class="back-content">
                  <!-- Top bar with navigation -->
                  <div class="back-topbar">
                    <button class="back-flip-btn" onclick={() => (flipped = false)} aria-label="Front">🎴</button>
                    {#if navHistory.length > 0}
                      <button class="nav-btn" onclick={navBack}>← Back</button>
                    {/if}
                    {#if navForward.length > 0}
                      <button class="nav-btn" onclick={navForwardFn}>Forward →</button>
                    {/if}
                    <button class="modal-close back-close" onclick={closeModal} aria-label="Close">✕</button>
                  </div>

                  <!-- Breadcrumb -->
                  {#if navHistory.length > 0}
                    <nav class="breadcrumb" aria-label="Navigation history">
                      {#each navHistory as h}
                        <span class="crumb">{h.character_name}</span>
                        <span class="crumb-sep">›</span>
                      {/each}
                      <span class="crumb crumb-current">{currentCharacter.name}</span>
                    </nav>
                  {/if}

                  <!-- Tab bar -->
                  <div class="tab-bar" role="tablist">
                    <button
                      class="tab-btn"
                      class:active={activeTab === 'bio'}
                      role="tab"
                      aria-selected={activeTab === 'bio'}
                      onclick={() => (activeTab = 'bio')}
                    >Bio</button>
                    <button
                      class="tab-btn"
                      class:active={activeTab === 'relationships'}
                      role="tab"
                      aria-selected={activeTab === 'relationships'}
                      onclick={() => (activeTab = 'relationships')}
                    >Relationships</button>
                  </div>

                  <!-- Tab content -->
                  <div class="tab-content" role="tabpanel">
                    {#if activeTab === 'bio'}
                      <div class="bio-tab">
                        <div class="bio-header">
                          <h3 class="bio-name">{currentCharacter.name}</h3>
                          <div class="bio-badges">
                            <!-- Role badge with dropdown -->
                            <div class="role-dd-wrap">
                              <button
                                class="role-badge"
                                onclick={(e) => { e.stopPropagation(); roleDdOpen = !roleDdOpen }}
                                title="Click to change role"
                              >{currentCharacter.role || 'character'} ▾</button>
                              {#if roleDdOpen}
                                <div class="role-dropdown">
                                  {#each ['character', 'persona'].filter((r) => r !== (currentCharacter.role || 'character')) as r}
                                    <button
                                      class="role-dd-option"
                                      onclick={() => void setRole(currentCharacterIndex, r)}
                                    >{r}</button>
                                  {/each}
                                </div>
                              {/if}
                            </div>

                            <!-- Tags -->
                            {#if currentCharacter.tags?.length}
                              {#each currentCharacter.tags as t}
                                <span class="tag-pill">#{t}</span>
                              {/each}
                            {/if}

                            <!-- Favorite -->
                            <button
                              class="fav-btn fav-sm"
                              onclick={() => void toggleFavorite(selected.run_id)}
                              aria-label={selectedItem.favorite ? 'Remove from favorites' : 'Add to favorites'}
                            >{selectedItem.favorite ? '★' : '☆'}</button>
                          </div>
                        </div>

                        <div class="bio-details">
                          <MarkdownBlock source={currentCharacter.details || ''} />
                        </div>
                      </div>

                    {:else}
                      <!-- Relationships tab -->
                      <div class="rel-tab">
                        <div class="rel-center">
                          <div class="rel-node rel-node-card rel-current" style={`border-color: ${nodeBorderColor(currentCharacter.id)}`}>
                            <div class="rel-node-avatar-wrap">
                              {#if characterAvatar(currentCharacter)}
                                <img
                                  class="rel-node-avatar"
                                  src={characterAvatar(currentCharacter)}
                                  alt={currentCharacter.name}
                                />
                              {:else}
                                <div class="rel-node-avatar rel-node-avatar-fallback">{initials(currentCharacter.name)}</div>
                              {/if}
                            </div>
                            <span class="rel-node-name">{currentCharacter.name || 'Character'}</span>
                          </div>
                        </div>

                        {#if relationshipNodes.length > 0}
                          <ul class="rel-list rel-graph">
                            {#each relationshipNodes as node}
                              <li class="rel-entry">
                                <button
                                  class="rel-node rel-node-card rel-node-target"
                                  style={`border-color: ${nodeBorderColor(node.target_urn)}`}
                                  onclick={() => void openRelationshipNode(node.target_urn)}
                                  disabled={node.loading}
                                  title={node.run_id ? 'Open related character' : 'Loading related character'}
                                >
                                  <div class="rel-node-avatar-wrap">
                                    {#if node.avatar_data}
                                      <img class="rel-node-avatar" src={node.avatar_data} alt={node.name} />
                                    {:else}
                                      <div class="rel-node-avatar rel-node-avatar-fallback">{initials(node.name)}</div>
                                    {/if}
                                  </div>
                                  <span class="rel-node-name">{node.name}</span>
                                </button>
                                <span class="rel-arrow">←</span>
                                <span class="rel-type">{node.relationship_label}</span>
                                <span class="rel-arrow">→</span>
                                <span class="rel-self-name">{currentCharacter.name}</span>
                              </li>
                            {/each}
                          </ul>
                        {:else}
                          <p class="rel-empty">No relationships defined.</p>
                        {/if}
                      </div>
                    {/if}
                  </div>
                </div>
              </div>
            {:else if !modalLoading}
              <div class="modal-empty">
                <p>Could not load character data.</p>
                <button class="back-flip-btn" onclick={() => (flipped = false)}>← Back to card</button>
              </div>
            {/if}
          </div>
        </div>

      </div>
    </div>
  </div>
{/if}

<!-- ── Story Modal ──────────────────────────────────────────────────── -->
{#if showStoryModal && selected && selectedItem}
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    aria-label={`${selected.artifact_type || selectedItem.artifact_type}: ${selectedItem.title}`}
    onclick={handleModalBackdrop}
    onkeydown={(e) => e.key === 'Escape' && closeModal()}
  >
    <div class="modal-overlay">
      <div class="modal-card">
        {#if selected?.artifact_type === 'story' && selected?.state?.story_artifact}
          <StoryArtifactModal
            storyArtifact={selected.state.story_artifact}
            storyId={selected.run_id}
            onClose={closeModal}
            onUpdate={() => {
              void openRun(selected.run_id)
            }}
          />
        {:else if selected?.artifact_type === 'location' && selected?.state?.story_artifact}
          <LocationModal
            location={selected.state.story_artifact}
            onClose={closeModal}
            onEdit={() => {}}
            onDelete={() => {}}
          />
        {:else if selected?.artifact_type === 'object' && selected?.state?.story_artifact}
          <ObjectModal
            object={selected.state.story_artifact}
            onClose={closeModal}
            onEdit={() => {}}
            onDelete={() => {}}
          />
        {:else if !modalLoading}
          <div class="modal-empty">
            <p>Could not load artifact data.</p>
            <button class="back-flip-btn" onclick={closeModal}>Close</button>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  /* ── Gallery layout ───────────────────────────────────────── */
  .gallery-page { display: grid; gap: 0.8rem; margin-top: 1rem; }

  .gallery-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .gallery-topbar h2 { margin: 0; }

  .artifact-tabs {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .artifact-tab-btn {
    border: 1px solid #cbd5e1;
    background: #fff;
    color: #334155;
    border-radius: 999px;
    padding: 0.3rem 0.7rem;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .artifact-tab-btn.active {
    border-color: #1d4ed8;
    background: #2563eb;
    color: #fff;
  }

  /* ── Filters ──────────────────────────────────────────────── */
  .filters { display: flex; gap: 0.45rem; align-items: center; flex-wrap: wrap; }

  .filter-input {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 0.4rem 0.55rem;
    font-size: 0.85rem;
  }

  .filter-tag { width: 8rem; }

  .fav-check {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.85rem;
    color: #334155;
    cursor: pointer;
    white-space: nowrap;
  }

  .apply-btn {
    border: 1px solid #334155;
    background: #334155;
    color: #fff;
    border-radius: 6px;
    padding: 0.35rem 0.7rem;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .apply-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* ── Regular grid ─────────────────────────────────────────── */
  .grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  }

  .empty-note { color: #94a3b8; font-size: 0.85rem; }
  .error { color: #b91c1c; }

  /* ── Modal overlay ────────────────────────────────────────── */
  .modal {
    position: fixed;
    inset: 0;
    background: rgba(2, 6, 23, 0.8);
    display: grid;
    place-items: center;
    padding: 1rem;
    z-index: 55;
  }

  /* ── Flip scene ───────────────────────────────────────────── */
  .flip-scene {
    perspective: 1200px;
    width: min(360px, 92vw);
    transition: width 0.45s ease;
  }

  .flip-scene.flipped {
    width: min(700px, 95vw);
  }

  .flip-card {
    width: 100%;
    height: min(520px, 82vh);
    transform-style: preserve-3d;
    transition: transform 0.55s ease;
    position: relative;
  }

  .flip-scene.flipped .flip-card {
    transform: rotateY(180deg);
  }

  .flip-face {
    position: absolute;
    inset: 0;
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    border-radius: 14px;
    overflow: hidden;
  }

  .flip-back {
    transform: rotateY(180deg);
    background: #fff;
  }

  /* ── Front face ───────────────────────────────────────────── */
  .front-inner {
    position: relative;
    width: 100%;
    height: 100%;
    background: #0f172a;
  }

  .front-img-btn {
    display: block;
    width: 100%;
    height: 100%;
    border: none;
    padding: 0;
    background: none;
    cursor: pointer;
  }

  .front-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .front-placeholder {
    width: 100%;
    height: 100%;
    background: linear-gradient(135deg, #1e293b, #334155);
    display: grid;
    place-items: center;
    cursor: pointer;
    color: #94a3b8;
    font-size: 1rem;
  }

  .front-overlay-top {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    padding: 1rem 1rem 2rem;
    background: linear-gradient(to bottom, rgba(0,0,0,0.65), transparent);
    pointer-events: none;
  }

  .front-overlay-top h2 {
    margin: 0;
    color: rgba(255,255,255,0.92);
    font-size: 1.2rem;
    font-weight: 700;
    text-shadow: 0 1px 4px rgba(0,0,0,0.5);
  }

  .front-overlay-bottom {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 2rem 1rem 1rem;
    background: linear-gradient(to top, rgba(0,0,0,0.65), transparent);
    pointer-events: none;
  }

  .front-overlay-bottom p {
    margin: 0;
    color: rgba(255,255,255,0.82);
    font-size: 0.82rem;
    line-height: 1.45;
    text-shadow: 0 1px 3px rgba(0,0,0,0.6);
  }

  .flip-hint {
    position: absolute;
    bottom: 0.6rem;
    left: 50%;
    transform: translateX(-50%);
    font-size: 0.72rem;
    color: rgba(255,255,255,0.45);
    cursor: pointer;
    white-space: nowrap;
    pointer-events: auto;
    padding: 0.2rem 0.5rem;
    border: none;
    background: none;
    z-index: 4;
  }

  .fav-btn {
    position: absolute;
    border: none;
    background: none;
    font-size: 1.4rem;
    cursor: pointer;
    line-height: 1;
    text-shadow: 0 1px 4px rgba(0,0,0,0.6);
    z-index: 5;
  }

  .front-fav {
    top: 0.55rem;
    right: 2.4rem;
    color: #fbbf24;
  }

  .modal-close {
    position: absolute;
    top: 0.4rem;
    right: 0.4rem;
    border: none;
    background: rgba(0,0,0,0.45);
    color: #fff;
    border-radius: 999px;
    width: 1.8rem;
    height: 1.8rem;
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
  }

  /* ── Back face ────────────────────────────────────────────── */
  .back-inner {
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .back-layout {
    display: flex;
    height: 100%;
  }

  .back-avatar {
    flex: 0 0 33.3%;
    overflow: hidden;
    background: #0f172a;
  }

  .back-avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .back-avatar-fallback {
    width: 100%;
    height: 100%;
    display: grid;
    place-items: center;
    color: #cbd5e1;
    font-size: 2rem;
    font-weight: 700;
  }

  .back-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #fff;
  }

  .back-topbar {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.45rem 0.5rem;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
    position: relative;
  }

  .back-flip-btn, .nav-btn {
    border: 1px solid #cbd5e1;
    background: #fff;
    color: #334155;
    border-radius: 999px;
    padding: 0.2rem 0.6rem;
    font-size: 0.75rem;
    cursor: pointer;
  }

  .back-close {
    position: static;
    margin-left: auto;
    width: 1.6rem;
    height: 1.6rem;
    background: #f1f5f9;
    color: #475569;
    border-radius: 999px;
    border: none;
    font-size: 0.8rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.2rem;
    padding: 0.25rem 0.5rem;
    font-size: 0.72rem;
    color: #64748b;
    background: #f1f5f9;
    flex-wrap: wrap;
  }

  .crumb { cursor: pointer; color: #3b82f6; text-decoration: underline; }
  .crumb-current { color: #0f172a; cursor: default; text-decoration: none; font-weight: 600; }
  .crumb-sep { color: #94a3b8; }

  /* ── Tabs ─────────────────────────────────────────────────── */
  .tab-bar {
    display: flex;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
    flex-shrink: 0;
  }

  .tab-btn {
    flex: 1;
    padding: 0.45rem 0.5rem;
    border: none;
    border-bottom: 2px solid transparent;
    background: none;
    font-size: 0.82rem;
    color: #64748b;
    cursor: pointer;
    font-weight: 500;
  }

  .tab-btn.active {
    color: #2563eb;
    border-bottom-color: #2563eb;
    background: #fff;
  }

  .tab-content {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem 0.65rem;
  }

  /* ── Bio tab ──────────────────────────────────────────────── */
  .bio-header {
    margin-bottom: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .bio-name {
    margin: 0;
    font-size: 1rem;
    color: #0f172a;
    font-weight: 700;
  }

  .bio-badges {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .role-dd-wrap { position: relative; }

  .role-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    background: #1e40af;
    color: #fff;
    border: none;
    border-radius: 999px;
    padding: 0.18rem 0.6rem;
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
    text-transform: capitalize;
  }

  .role-dropdown {
    position: absolute;
    top: calc(100% + 3px);
    left: 0;
    background: #fff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    z-index: 20;
    overflow: hidden;
    min-width: 8rem;
  }

  .role-dd-option {
    display: block;
    width: 100%;
    padding: 0.4rem 0.7rem;
    text-align: left;
    background: none;
    border: none;
    font-size: 0.8rem;
    cursor: pointer;
    text-transform: capitalize;
  }

  .role-dd-option:hover { background: #f1f5f9; }

  .tag-pill {
    display: inline-block;
    border: 1px solid #bfdbfe;
    color: #1e40af;
    border-radius: 999px;
    padding: 0.1rem 0.45rem;
    font-size: 0.68rem;
    background: #eff6ff;
  }

  .fav-sm {
    position: static;
    font-size: 1rem;
    color: #fbbf24;
    text-shadow: none;
    padding: 0;
    line-height: 1;
    border: none;
    background: none;
    cursor: pointer;
  }

  .bio-details {
    font-size: 0.82rem;
    border-top: 1px solid #f1f5f9;
    padding-top: 0.4rem;
  }

  /* ── Relationships tab ────────────────────────────────────── */
  .rel-tab {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .rel-center {
    display: flex;
    justify-content: center;
    padding: 0.4rem 0;
  }

  .rel-node {
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    border: 2px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.35rem 0.5rem;
    font-size: 0.78rem;
    font-weight: 600;
    background: #f8fafc;
    color: #334155;
    max-width: 100%;
    text-align: left;
  }

  .rel-node-card {
    display: inline-flex;
    gap: 0.4rem;
    min-width: 10rem;
  }

  .rel-node-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rel-node-avatar-wrap {
    flex: 0 0 auto;
  }

  .rel-node-avatar {
    width: 1.4rem;
    height: 1.4rem;
    border-radius: 4px;
    object-fit: cover;
    display: block;
    border: 1px solid rgba(148, 163, 184, 0.4);
  }

  .rel-node-avatar-fallback {
    display: grid;
    place-items: center;
    font-size: 0.65rem;
    font-weight: 700;
    color: #334155;
    background: #e2e8f0;
  }

  .rel-current {
    border-color: #1d4ed8;
    background: #eff6ff;
    color: #1e40af;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
  }

  .rel-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .rel-entry {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex-wrap: wrap;
  }

  .rel-graph {
    gap: 0.65rem;
  }

  .rel-node-target {
    cursor: pointer;
    transition: transform 0.14s ease, box-shadow 0.14s ease;
  }

  .rel-node-target:hover:enabled {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.12);
  }

  .rel-node-target:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .rel-arrow { color: #94a3b8; font-size: 0.85rem; }

  .rel-type {
    font-size: 0.72rem;
    color: #7c3aed;
    font-weight: 600;
    background: #f5f3ff;
    border-radius: 999px;
    padding: 0.1rem 0.45rem;
    border: 1px solid #ddd6fe;
  }

  .rel-empty {
    font-size: 0.75rem;
    color: #94a3b8;
    font-style: italic;
    margin: 0;
  }

  .rel-self-name {
    font-size: 0.72rem;
    color: #64748b;
    font-weight: 600;
  }

  /* ── Loading state ────────────────────────────────────────── */
  .modal-loading, .modal-empty {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    color: #64748b;
    font-size: 0.9rem;
  }

  .spinner {
    width: 2rem;
    height: 2rem;
    border: 3px solid #e2e8f0;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }
</style>
