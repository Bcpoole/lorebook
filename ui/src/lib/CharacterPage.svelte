<script>
  import AgentPanel from './AgentPanel.svelte'

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

  function markPendingSave() {
    pendingSave = {
      raw_idea: rawIdea,
      state: workflowState,
      meta: { source: 'character-page' },
    }
  }

  async function generateCharacter(directive = '') {
    if (!rawIdea.trim() || loading || !llmConnected) return
    loading = true
    error = ''
    savedName = ''
    savedRun = null
    try {
      const prompt = directive.trim() ? `${rawIdea}\n\nInstruction:\n${directive.trim()}` : rawIdea
      const res = await fetch('/api/character', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
    } catch {
      error = 'Failed to generate character.'
    } finally {
      loading = false
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

  async function saveCharacter() {
    if (!pendingSave) return
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...pendingSave }),
    })
    if (!res.ok) {
      error = 'Failed to save character.'
      return
    }
    const payload = await res.json()
    savedRun = payload
    savedName = payload.filename
    pendingSave = null
  }
</script>

<section class="character-page">
  <h2>Character Generator</h2>
  <textarea bind:value={rawIdea} rows="4" placeholder="Describe the character concept..." disabled={loading}></textarea>
  <div class="actions">
    <button onclick={() => generateCharacter()} disabled={!rawIdea.trim() || loading || !llmConnected}>
      {loading ? 'Generating…' : 'Generate Character'}
    </button>
    <button class="secondary" onclick={saveCharacter} disabled={!pendingSave}>Save</button>
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
    onrunmodule={handleModuleRun}
    oncharacterimage={handleCharacterImageGenerate}
  />
</section>

<style>
  .character-page { display: grid; gap: 0.65rem; margin-top: 1rem; }
  textarea { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.6rem; }
  .actions { display: flex; gap: 0.5rem; }
  button { border: 1px solid #2563eb; background: #2563eb; color: #fff; border-radius: 6px; padding: 0.4rem 0.75rem; cursor: pointer; }
  button.secondary { background: #334155; border-color: #334155; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .error { color: #b91c1c; }
  .ok { color: #047857; }
</style>
