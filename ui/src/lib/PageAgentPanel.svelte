<script>
  import { onMount, tick } from 'svelte'

  let {
    page = 'world',
    pageLabel = 'World',
    context = {},
    personaOptions = [],
    selectedPersona = null,
    selectedPersonaId = 'blank',
    connected = true,
    onpersonachanged = () => {},
    onproposals = () => {},
  } = $props()

  let panelWidth = $state(380)
  let resizing = $state(false)
  let input = $state('')
  let sending = $state(false)
  let error = $state('')
  let threads = $state({})
  let chatLog = $state(null)
  let nextMessageId = 1

  const messages = $derived(threads[page] ?? [])

  function updateThread(updater) {
    threads = { ...threads, [page]: updater(threads[page] ?? []) }
  }

  function addMessage(message) {
    const entry = { id: nextMessageId++, ...message }
    updateThread((items) => [...items, entry])
    void tick().then(() => {
      if (chatLog) {
        chatLog.scrollTop = chatLog.scrollHeight
      }
    })
  }

  async function sendMessage() {
    const message = input.trim()
    if (!message || sending || !connected) return
    input = ''
    error = ''
    addMessage({ role: 'user', text: message, changes: [] })
    sending = true
    try {
      const response = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          page,
          message,
          persona_id: selectedPersonaId,
          context,
        }),
      })
      const payload = await response.json().catch(() => null)
      if (!response.ok) {
        throw new Error(payload?.detail || 'The page agent could not respond.')
      }
      const changes = Array.isArray(payload.changes) ? payload.changes : []
      onproposals({ page, changes })
      addMessage({
        role: 'assistant',
        text: payload.reply,
        changes,
      })
    } catch (requestError) {
      error = requestError instanceof Error ? requestError.message : 'The page agent could not respond.'
    } finally {
      sending = false
    }
  }

  function handleComposerKeydown(event) {
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    void sendMessage()
  }

  function startResize(event) {
    event.preventDefault()
    resizing = true
  }

  function stopResize() {
    if (!resizing) return
    resizing = false
    try {
      window.localStorage?.setItem('lorebook-agent-panel-width', String(panelWidth))
    } catch {
      // Resizing still works when browser storage is unavailable.
    }
  }

  function resizePanel(event) {
    if (!resizing) return
    const maxWidth = Math.max(360, Math.min(720, window.innerWidth - 420))
    panelWidth = Math.max(300, Math.min(maxWidth, window.innerWidth - event.clientX))
  }

  onMount(() => {
    try {
      const storedWidth = Number(window.localStorage?.getItem('lorebook-agent-panel-width'))
      if (Number.isFinite(storedWidth) && storedWidth >= 300) {
        panelWidth = Math.min(storedWidth, 720)
      }
    } catch {
      // Use the default width when browser storage is unavailable.
    }
    window.addEventListener('pointermove', resizePanel)
    window.addEventListener('pointerup', stopResize)
    return () => {
      window.removeEventListener('pointermove', resizePanel)
      window.removeEventListener('pointerup', stopResize)
    }
  })
</script>

<aside class:resizing class="page-agent-panel" style={`width: ${panelWidth}px`}>
  <button
    class="resize-handle"
    type="button"
    aria-label="Resize Agent Persona panel"
    title="Drag to resize"
    onpointerdown={startResize}
  ></button>

  <header class="panel-header">
    <div>
      <span>Agent Persona</span>
      <strong>{pageLabel} orchestrator</strong>
    </div>
    <span class="context-indicator" title={`The agent receives the current ${pageLabel} page content.`}>Context on</span>
  </header>

  <div class="persona-summary">
    <label for="persona-select">Persona</label>
    <select id="persona-select" value={selectedPersonaId} onchange={onpersonachanged}>
      {#each personaOptions as persona}
        <option value={persona.id}>{persona.name}</option>
      {/each}
    </select>
    {#if selectedPersona}
      <div class="persona-row">
        {#if selectedPersona.avatarUrl}
          <img src={selectedPersona.avatarUrl} alt={`${selectedPersona.name} avatar`} width="48" height="48" />
        {:else}
          <div class="avatar-placeholder">{selectedPersona.name?.slice(0, 1) || '?'}</div>
        {/if}
        <p>{selectedPersona.description}</p>
      </div>
    {/if}
  </div>

  <div class="chat-log" aria-live="polite" bind:this={chatLog}>
    {#each messages as message (message.id)}
      <article class:assistant={message.role === 'assistant'} class="message">
        <span class="message-role">{message.role === 'assistant' ? selectedPersona?.name || 'Agent' : 'You'}</span>
        <p>{message.text}</p>

        {#if message.changes.length > 0}
          <div class="proposal-header">
            <strong>{message.changes.length} change{message.changes.length === 1 ? '' : 's'} staged on the page</strong>
          </div>
          {#each message.changes as change}
            <div class="staged-change">
              <span>{change.label}</span>
              <small>Review New / Old in {pageLabel}</small>
            </div>
          {/each}
        {/if}
      </article>
    {/each}
    {#if sending}
      <div class="thinking"><span></span><span></span><span></span> Coordinating…</div>
    {/if}
  </div>

  {#if error}
    <div class="panel-error" role="alert">{error}</div>
  {/if}

  <div class="composer">
    <textarea
      bind:value={input}
      onkeydown={handleComposerKeydown}
      placeholder={`Ask about or edit this ${pageLabel.toLowerCase()}…`}
      aria-label="Message page orchestrator"
      rows="3"
      disabled={!connected || sending}
    ></textarea>
    <button type="button" onclick={sendMessage} disabled={!input.trim() || !connected || sending}>Send</button>
  </div>
</aside>

<style>
  .page-agent-panel {
    min-width: 300px;
    max-width: min(720px, calc(100vw - 420px));
    border-left: 1px solid #1f2937;
    background: #111827;
    color: #e5e7eb;
    display: flex;
    flex-direction: column;
    position: relative;
    font-size: 12px;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }
  .page-agent-panel.resizing { user-select: none; }
  .resize-handle {
    position: absolute;
    inset: 0 auto 0 -5px;
    width: 10px;
    border: 0;
    background: transparent;
    cursor: col-resize;
    z-index: 4;
  }
  .resize-handle:hover, .resizing .resize-handle { background: rgba(56, 189, 248, 0.35); }
  .panel-header {
    flex: 0 0 auto;
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    padding: 0.7rem 0.85rem;
    border-bottom: 1px solid #1f2937;
    background: #0b1220;
  }
  .panel-header > div { display: grid; gap: 0.15rem; }
  .panel-header span:first-child { color: #9ca3af; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
  .panel-header strong { font-size: 0.82rem; color: #f8fafc; }
  .context-indicator { color: #67e8f9; background: #164e63; border-radius: 999px; padding: 0.2rem 0.45rem; white-space: nowrap; }
  .persona-summary { flex: 0 0 auto; padding: 0.7rem 0.8rem; border-bottom: 1px solid #1f2937; display: grid; gap: 0.35rem; }
  .persona-summary label { color: #cbd5e1; }
  .persona-summary select {
    width: 100%;
    background: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 0.4rem 0.5rem;
  }
  .persona-row { display: flex; align-items: center; gap: 0.55rem; }
  .persona-row img, .avatar-placeholder { width: 48px; height: 48px; border-radius: 8px; border: 1px solid #374151; object-fit: cover; flex: 0 0 auto; }
  .avatar-placeholder { display: grid; place-items: center; background: #1f2937; font-size: 1.3rem; font-weight: 700; }
  .persona-row p { margin: 0; color: #94a3b8; line-height: 1.35; }
  .chat-log { flex: 1 1 auto; min-height: 0; overflow-y: auto; overflow-x: hidden; padding: 0.75rem; display: grid; align-content: start; gap: 0.7rem; }
  .message { justify-self: end; width: min(92%, 520px); background: #164e63; border: 1px solid #155e75; border-radius: 12px 12px 3px 12px; padding: 0.65rem; }
  .message.assistant { justify-self: stretch; width: auto; background: #1e293b; border-color: #334155; border-radius: 3px 12px 12px 12px; }
  .message-role { color: #67e8f9; font-size: 0.68rem; font-weight: 700; text-transform: uppercase; }
  .message > p { margin: 0.3rem 0 0; line-height: 1.45; white-space: pre-wrap; }
  .proposal-header { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; }
  .proposal-header { margin-top: 0.65rem; padding-top: 0.55rem; border-top: 1px solid #475569; }
  button { border: 1px solid #0891b2; border-radius: 6px; background: #0e7490; color: white; padding: 0.3rem 0.5rem; cursor: pointer; font: inherit; font-weight: 700; }
  button:hover:not(:disabled) { background: #0891b2; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .staged-change { margin-top: 0.45rem; padding: 0.5rem; border: 1px solid #475569; border-radius: 7px; background: #0f172a; display: grid; gap: 0.15rem; }
  .staged-change span { color: #e2e8f0; font-weight: 700; }
  .staged-change small { color: #67e8f9; }
  .thinking { color: #94a3b8; }
  .thinking span { display: inline-block; width: 5px; height: 5px; margin-right: 2px; border-radius: 50%; background: #67e8f9; }
  .panel-error { margin: 0 0.75rem 0.5rem; color: #fecaca; background: #7f1d1d; border-radius: 6px; padding: 0.5rem; }
  .composer { flex: 0 0 auto; border-top: 1px solid #1f2937; padding: 0.7rem; display: grid; grid-template-columns: 1fr auto; gap: 0.45rem; align-items: end; background: #111827; }
  .composer textarea { resize: vertical; min-height: 58px; max-height: 160px; border: 1px solid #374151; border-radius: 8px; background: #0b1220; color: #f8fafc; padding: 0.55rem; font: inherit; }
  @media (max-width: 900px) {
    .page-agent-panel { width: min(380px, 45vw) !important; min-width: 280px; }
  }
</style>
