<script>
  import { onDestroy, onMount } from 'svelte'

  import AgentPanel from './AgentPanel.svelte'
  import Toast from './Toast.svelte'

  let {
    llmConnected = true,
    personaId = 'blank',
    experimentationConfig = {},
    rawIdea = $bindable(''),
    loading = $bindable(false),
    error = $bindable(''),
    workflowState = $bindable({
      raw_idea: '',
      world_setting: '',
      characters: [],
      critique_notes: '',
      passed_inspection: false,
    }),
    activeAgent = $bindable('character_designer'),
    pendingSave = $bindable(null),
    savedRun = $bindable(null),
    savedName = $bindable(''),
  } = $props()

  const CHARACTER_PAGE_STORAGE_KEY = 'lorebook.characterPageDraft.v1'

  function emptyWorkflowState(nextRawIdea = '') {
    return {
      raw_idea: nextRawIdea,
      world_setting: '',
      characters: [],
      critique_notes: '',
      passed_inspection: false,
    }
  }

  function resetCharacterPageState() {
    rawIdea = ''
    loading = false
    error = ''
    workflowState = emptyWorkflowState('')
    activeAgent = 'character_designer'
    pendingSave = null
    savedRun = null
    savedName = ''
  }

  function normalizeWorkflowState(candidate, nextRawIdea = '') {
    const fallback = emptyWorkflowState(nextRawIdea)
    if (!candidate || typeof candidate !== 'object') return fallback
    return {
      raw_idea: candidate.raw_idea ?? nextRawIdea,
      world_setting: candidate.world_setting ?? '',
      characters: Array.isArray(candidate.characters) ? candidate.characters : [],
      critique_notes: candidate.critique_notes ?? '',
      passed_inspection: candidate.passed_inspection ?? false,
    }
  }

  function hasPersistableCharacterPageState() {
    const hasWorkflowContent = Boolean(
      workflowState?.world_setting?.trim() ||
      workflowState?.critique_notes?.trim() ||
      (workflowState?.characters?.length ?? 0) > 0
    )
    return Boolean(
      rawIdea.trim() ||
      hasWorkflowContent ||
      pendingSave ||
      savedRun ||
      savedName.trim()
    )
  }

  function persistCharacterPageState() {
    if (typeof window === 'undefined') return
    try {
      if (!hasPersistableCharacterPageState()) {
        window.localStorage.removeItem(CHARACTER_PAGE_STORAGE_KEY)
        return
      }
      window.localStorage.setItem(
        CHARACTER_PAGE_STORAGE_KEY,
        JSON.stringify({
          rawIdea,
          loading,
          error,
          workflowState,
          activeAgent,
          pendingSave,
          savedRun,
          savedName,
        })
      )
    } catch {
      // Ignore storage quota or serialization issues and keep in-memory state.
    }
  }

  function restoreCharacterPageState() {
    if (typeof window === 'undefined') return
    try {
      const stored = window.localStorage.getItem(CHARACTER_PAGE_STORAGE_KEY)
      if (!stored) return
      const parsed = JSON.parse(stored)
      rawIdea = parsed?.rawIdea ?? ''
      loading = false
      error = parsed?.error ?? ''
      workflowState = normalizeWorkflowState(parsed?.workflowState, rawIdea)
      activeAgent = parsed?.activeAgent ?? 'character_designer'
      pendingSave = parsed?.pendingSave ?? null
      savedRun = parsed?.savedRun ?? null
      savedName = parsed?.savedName ?? ''
    } catch {
      // Ignore invalid cache payloads and keep defaults.
    }
  }

  onMount(() => {
    restoreCharacterPageState()
  })

  $effect(() => {
    persistCharacterPageState()
  })

  let activeAbortController = $state(null)
  let activeGenerationId = $state(0)
  let toastMessage = $state('')
  let toastVisible = $state(false)
  let savedNameTimer = null

  function showToast(message) {
    toastMessage = message
    toastVisible = true
  }

  function isAbortError(error) {
    return error?.name === 'AbortError'
  }

  function stopCharacterGeneration() {
    activeGenerationId += 1
    if (activeAbortController) {
      activeAbortController.abort()
      activeAbortController = null
    }
    loading = false
  }

  function handleGenerateClick() {
    if (loading) {
      stopCharacterGeneration()
      return
    }
    void generateCharacter()
  }

  function markPendingSave() {
    pendingSave = {
      raw_idea: rawIdea,
      state: workflowState,
      meta: { source: 'character-page' },
    }
  }

  async function generateCharacter(directive = '') {
    if (!rawIdea.trim() || loading || !llmConnected) return
    const generationId = ++activeGenerationId
    const controller = new AbortController()
    activeAbortController = controller
    loading = true
    error = ''
    savedName = ''
    savedRun = null
    try {
      const prompt = directive.trim() ? `${rawIdea}\n\nInstruction:\n${directive.trim()}` : rawIdea
      const res = await fetch('/api/character', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          raw_idea: prompt,
          state: workflowState,
          persona_id: personaId,
          experimentation_config: experimentationConfig,
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        error = payload?.detail || 'Failed to generate character.'
        return
      }
      const payload = await res.json()
      workflowState = payload.state
      activeAgent = 'character_designer'
      markPendingSave()
    } catch (fetchError) {
      if (isAbortError(fetchError)) return
      error = 'Failed to generate character.'
    } finally {
      if (generationId === activeGenerationId) {
        activeAbortController = null
        loading = false
      }
    }
  }

  async function handleModuleRun({ stage, directive }) {
    if (stage !== 'character_designer') return
    await generateCharacter(directive ?? '')
  }

  async function handleCharacterImageGenerate({ characterIndex, promptOverride = '', mode = 'full' }) {
    if (!llmConnected) return
    const res = await fetch('/api/character-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        raw_idea: rawIdea,
        state: workflowState,
        character_index: characterIndex,
        prompt_override: promptOverride,
        mode,
        style: experimentationConfig?.sd?.style,
        sd_config: experimentationConfig?.sd ?? {},
        persona_id: personaId,
      }),
    })
    if (!res.ok) {
      const payload = await res.json().catch(() => null)
      error = payload?.detail || 'Failed to generate character image.'
      return
    }
    const payload = await res.json()
    workflowState = payload.state
    markPendingSave()
  }

  async function handleSpawnRelated({ relationship, sourceCharacterIndex, context = '' }) {
    if (!rawIdea.trim() || loading || !llmConnected) return
    loading = true
    error = ''
    try {
      const res = await fetch('/api/character-related', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_idea: rawIdea,
          state: workflowState,
          source_character_index: sourceCharacterIndex,
          relationship,
          context,
          persona_id: personaId,
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        error = payload?.detail || 'Failed to spawn related character.'
        return
      }
      const payload = await res.json()
      workflowState = payload.state
      markPendingSave()
    } catch (fetchError) {
      if (isAbortError(fetchError)) return
      error = 'Failed to spawn related character.'
    } finally {
      loading = false
    }
  }

  async function saveCharacterByIndex(index) {
    const characters = Array.isArray(workflowState?.characters) ? workflowState.characters : []
    if (index < 0 || index >= characters.length) return
    const target = characters[index]
    if (!target || !String(target.details || '').trim()) return
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        raw_idea: rawIdea,
        state: {
          ...workflowState,
          characters: [{ ...target }],
        },
        meta: { source: 'character-page' },
        persona_id: personaId,
      }),
    })
    if (!res.ok) {
      error = 'Failed to save character.'
      return
    }
    const payload = await res.json()
    savedRun = payload
    savedName = payload.filename
    showToast(`💾 Saved as ${payload.filename}`)
    if (savedNameTimer) clearTimeout(savedNameTimer)
    savedNameTimer = setTimeout(() => { savedName = '' }, 4000)
  }

  function handleResetCharacterPage() {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm('Reset Character page and clear its temporary draft?')
      if (!confirmed) return
    }
    stopCharacterGeneration()
    resetCharacterPageState()
  }

  onDestroy(() => {
    stopCharacterGeneration()
    if (savedNameTimer) clearTimeout(savedNameTimer)
  })
</script>

<section class="character-page dark-ui-page dark-ui-character">
  <Toast bind:visible={toastVisible} message={toastMessage} />
  <div class="page-header">
    <h2>Character Generator</h2>
    <button class="reset-btn" type="button" onclick={handleResetCharacterPage}>
      Reset
    </button>
  </div>
  <textarea bind:value={rawIdea} rows="4" placeholder="Describe the character concept..." disabled={loading}></textarea>
  <div class="actions">
    <button onclick={handleGenerateClick} disabled={!loading && (!rawIdea.trim() || !llmConnected)}>
      {loading ? 'Generating… Click to stop' : 'Generate Character'}
    </button>
  </div>
  {#if error}<p class="error">{error}</p>{/if}
  {#if savedName}<p class="ok">Saved as {savedName}</p>{/if}

  <AgentPanel
    bind:workflowState
    running={loading}
    bind:activeAgent
    {pendingSave}
    {savedRun}
    showNext={false}
    showContinue={false}
    llmConnected={llmConnected}
    visibleAgentKeys={['character_designer']}
    iconOnlyCharacterActions={true}
    confirmDeleteDialog={true}
    onrunmodule={handleModuleRun}
    oncharacterimage={handleCharacterImageGenerate}
    onspawnrelated={handleSpawnRelated}
    onsavecharacter={saveCharacterByIndex}
  />
</section>

<style>
  .character-page { display: grid; gap: 0.65rem; margin-top: 0; }
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
  h2 { margin: 0; color: var(--lb-page-heading, #0f172a); }
  textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--lb-input-border, #cbd5e1); border-radius: 6px; padding: 0.6rem; background: var(--lb-input-bg, #fff); color: var(--lb-input-fg, #0f172a); }
  .actions { display: flex; gap: 0.5rem; }
  button { border: 1px solid var(--lb-accent-2, #2563eb); background: linear-gradient(135deg, var(--lb-accent-1, #2563eb), var(--lb-accent-2, #1d4ed8)); color: #fff; border-radius: 6px; padding: 0.4rem 0.75rem; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .reset-btn { border-color: var(--lb-btn-secondary-border, #94a3b8); background: var(--lb-btn-secondary-bg, #fff); color: var(--lb-btn-secondary-fg, #334155); }
  .reset-btn:hover { border-color: var(--lb-border-2, #64748b); background: rgba(71, 85, 105, 0.5); }
  .error { color: #fca5a5; }
  .ok { color: #6ee7b7; }
</style>
