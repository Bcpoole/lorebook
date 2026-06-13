<script>
  let {
    meta = {},
  } = $props()
</script>

<header>
  <span class="brand">Lorebook</span>

  <div class="controls">
    {#if meta.elapsed_ms != null}
      <span class="stats">{meta.elapsed_ms} ms</span>
    {/if}
  </div>
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
    align-items: center;
    gap: 1rem;
  }

  .stats {
    font-size: 0.8rem;
    color: #94a3b8;
  }

</style>
