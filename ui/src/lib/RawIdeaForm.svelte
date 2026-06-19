<script>
  let { running = false, llmConnected = true, rawIdea = $bindable(''), onrun, onstop = () => {} } = $props()

  function submit() {
    if (running) {
      onstop()
      return
    }

    if (!rawIdea.trim() || !llmConnected) return
    onrun({ rawIdea })
  }
</script>

<div class="form">
  <textarea
    bind:value={rawIdea}
    placeholder="Describe your world idea…"
    rows="4"
    disabled={running}
  ></textarea>
  <button onclick={submit} disabled={!running && (!rawIdea.trim() || !llmConnected)}>
    {running ? 'Running… Click to stop' : 'Generate'}
  </button>
</div>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  textarea {
    width: 100%;
    padding: 0.6rem;
    border: 1px solid var(--lb-input-border, #cbd5e1);
    border-radius: 6px;
    font-size: 0.95rem;
    resize: vertical;
    box-sizing: border-box;
    background: var(--lb-input-bg, #fff);
    color: var(--lb-input-fg, #0f172a);
  }

  button {
    align-self: flex-end;
    padding: 0.5rem 1.4rem;
    background: linear-gradient(135deg, var(--lb-accent-1, #2563eb), var(--lb-accent-2, #1d4ed8));
    color: #eff6ff;
    border: 1px solid var(--lb-accent-2, #1d4ed8);
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.95rem;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
