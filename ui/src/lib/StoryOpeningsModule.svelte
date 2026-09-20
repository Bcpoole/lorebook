<script>
  let {
    openings = [],
    disabled = false,
    tooltip = '',
    onupdate = () => {},
    onadd = () => {},
    onremove = () => {},
  } = $props()

  function updateOpening(index, patch) {
    onupdate(index, { ...(openings[index] ?? {}), ...patch })
  }

  function updateMessage(openingIndex, messageIndex, patch) {
    const opening = openings[openingIndex] ?? {}
    const messages = [...(opening.messages ?? [])]
    messages[messageIndex] = { ...(messages[messageIndex] ?? {}), ...patch }
    updateOpening(openingIndex, { messages })
  }

  function addMessage(openingIndex) {
    const opening = openings[openingIndex] ?? {}
    updateOpening(openingIndex, {
      messages: [...(opening.messages ?? []), { role: 'assistant', content: '' }],
    })
  }

  function removeMessage(openingIndex, messageIndex) {
    const opening = openings[openingIndex] ?? {}
    updateOpening(openingIndex, {
      messages: (opening.messages ?? []).filter((_, index) => index !== messageIndex),
    })
  }
</script>

<section class="openings-module">
  <header>
    <h3>Openings <span>({openings.length})</span></h3>
    <button type="button" class="add" onclick={onadd} disabled={disabled}>+ Add</button>
    <span class="tooltip" aria-label={tooltip} title={tooltip}>?</span>
  </header>

  {#each openings as opening, openingIndex}
    <article class="opening-card">
      <button
        type="button"
        class="remove-opening"
        aria-label={`Remove opening ${openingIndex + 1}`}
        onclick={() => onremove(openingIndex)}
        disabled={disabled}
      >×</button>
      <textarea
        rows="3"
        value={opening.description ?? ''}
        placeholder="Optional guidance explaining when to choose this opening."
        aria-label={`Opening ${openingIndex + 1} description`}
        oninput={(event) => updateOpening(openingIndex, { description: event.currentTarget.value })}
        disabled={disabled}
      ></textarea>

      <div class="messages">
        {#each opening.messages ?? [] as message, messageIndex}
          <div class="message-row">
            <select
              value={message.role ?? 'assistant'}
              aria-label={`Opening ${openingIndex + 1} message ${messageIndex + 1} role`}
              onchange={(event) => updateMessage(openingIndex, messageIndex, { role: event.currentTarget.value })}
              disabled={disabled}
            >
              <option value="assistant">Assistant</option>
              <option value="user">User</option>
              <option value="system">System</option>
            </select>
            <textarea
              rows="5"
              value={message.content ?? ''}
              placeholder="Opening message..."
              aria-label={`Opening ${openingIndex + 1} message ${messageIndex + 1}`}
              oninput={(event) => updateMessage(openingIndex, messageIndex, { content: event.currentTarget.value })}
              disabled={disabled}
            ></textarea>
            <button
              type="button"
              class="remove-message"
              aria-label={`Remove opening ${openingIndex + 1} message ${messageIndex + 1}`}
              onclick={() => removeMessage(openingIndex, messageIndex)}
              disabled={disabled}
            >×</button>
          </div>
        {/each}
      </div>
      <button type="button" class="add-message" onclick={() => addMessage(openingIndex)} disabled={disabled}>+ Add message</button>
    </article>
  {/each}
</section>

<style>
  .openings-module { display: grid; gap: 0.65rem; border-top: 1px solid var(--lb-border-1, #334155); padding-top: 0.8rem; }
  header { display: flex; align-items: center; gap: 0.55rem; }
  h3 { margin: 0; font-size: 0.95rem; color: var(--lb-text-1, #e2e8f0); }
  h3 span { color: var(--lb-text-2, #94a3b8); font-weight: 400; }
  button { cursor: pointer; }
  .add, .add-message {
    border: 1px solid var(--lb-border-1, #475569); border-radius: 999px;
    background: transparent; color: var(--lb-text-1, #e2e8f0); padding: 0.25rem 0.65rem;
  }
  .tooltip {
    display: inline-flex; align-items: center; justify-content: center;
    width: 1rem; height: 1rem; border: 1px solid #64748b; border-radius: 50%;
    color: #cbd5e1; font-size: 0.7rem; cursor: help;
  }
  .opening-card {
    position: relative; display: grid; gap: 0.65rem; padding: 0.75rem;
    border: 1px solid var(--lb-border-1, #334155); border-radius: 8px;
    background: rgba(15, 23, 42, 0.38);
  }
  .remove-opening, .remove-message {
    border: 0; border-radius: 4px; background: rgba(51, 65, 85, 0.8);
    color: #fca5a5; width: 1.5rem; height: 1.5rem;
  }
  .remove-opening { position: absolute; top: 0.45rem; right: 0.45rem; z-index: 1; }
  textarea, select {
    box-sizing: border-box; border: 1px solid var(--lb-border-1, #475569);
    border-radius: 6px; padding: 0.5rem 0.6rem; background: rgba(30, 41, 59, 0.85);
    color: var(--lb-text-1, #e2e8f0);
  }
  textarea { width: 100%; resize: vertical; line-height: 1.45; }
  .opening-card > textarea { padding-right: 2.4rem; }
  .messages { display: grid; gap: 0.55rem; }
  .message-row { display: grid; grid-template-columns: 7rem 1fr auto; gap: 0.45rem; align-items: start; }
  .add-message { justify-self: end; }
  button:disabled, textarea:disabled, select:disabled { opacity: 0.55; cursor: not-allowed; }

  @media (max-width: 640px) {
    .message-row { grid-template-columns: 1fr auto; }
    .message-row textarea { grid-column: 1 / -1; grid-row: 2; }
  }
</style>
