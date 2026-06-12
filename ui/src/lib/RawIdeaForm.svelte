<script>
  let { running = false, llmConnected = true, rawIdea = $bindable(''), onrun } = $props()

  function submit() {
    if (!rawIdea.trim() || running || !llmConnected) return
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
  <button onclick={submit} disabled={running || !rawIdea.trim() || !llmConnected}>
    {running ? 'Running…' : 'Generate'}
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
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 0.95rem;
    resize: vertical;
    box-sizing: border-box;
  }

  button {
    align-self: flex-end;
    padding: 0.5rem 1.4rem;
    background: #1e40af;
    color: #fff;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.95rem;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
