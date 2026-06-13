<script>
  let {
    meta = {},
    activeTab = 'world',
    onselecttab = () => {},
  } = $props()

  const tabs = [
    { id: 'world', label: '🌍 World' },
    { id: 'story', label: '📕 Story' },
    { id: 'character', label: '🎭 Character' },
    { id: 'gallery', label: '🏛️ Gallery' },
  ]
</script>

<header>
  <span class="brand">Lorebook</span>

  <div class="controls">
    <nav class="tabs" aria-label="Primary pages">
      {#each tabs as tab}
        <button class="nav-btn" class:active={activeTab === tab.id} onclick={() => onselecttab(tab.id)}>
          {tab.label}
        </button>
      {/each}
    </nav>

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

  .tabs {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .stats {
    font-size: 0.8rem;
    color: #94a3b8;
  }

  .nav-btn {
    padding: 0.3rem 0.9rem;
    background: transparent;
    border: 1px solid #475569;
    border-radius: 6px;
    color: #cbd5e1;
    font-size: 0.875rem;
    cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
  }

  .nav-btn:hover {
    border-color: #94a3b8;
    color: #f1f5f9;
  }

  .nav-btn.active {
    border-color: #60a5fa;
    background: #1e3a8a;
    color: #dbeafe;
  }
</style>
