<script>
  let { showStats = $bindable(false), streaming = $bindable(true), meta = {} } = $props()
</script>

<header>
  <span class="brand">Lorebook</span>

  <div class="controls">
    <label class="toggle">
      <input type="checkbox" bind:checked={streaming} />
      Stream
    </label>

    <label class="toggle">
      <input type="checkbox" bind:checked={showStats} />
      Stats
    </label>
  </div>

  {#if showStats && meta.elapsed_ms != null}
    <div class="stats">
      {meta.elapsed_ms} ms
    </div>
  {/if}
</header>

<style>
  header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.6rem 1rem;
    background: #1e293b;
    color: #f1f5f9;
    font-family: system-ui, sans-serif;
  }

  .brand {
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 0.03em;
    flex: 1;
  }

  .controls {
    display: flex;
    gap: 1rem;
  }

  .toggle {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.875rem;
    cursor: pointer;
  }

  .stats {
    font-size: 0.8rem;
    color: #94a3b8;
  }
</style>
