<script>
  let {
    meta = {},
    showStats = false,
    activeTab = "world",
    onselecttab = () => {},
  } = $props();

  const elapsedMs = $derived.by(() => {
    const parsed = Number(meta?.elapsed_ms ?? 0);
    return Number.isFinite(parsed) ? parsed : 0;
  });

  const tabs = [
    { id: "world", label: "🌍 World" },
    { id: "story", label: "📕 Story" },
    { id: "character", label: "🎭 Character" },
    { id: "gallery", label: "🗂️ Gallery" },
    { id: "world-story", label: "🪶 Lore" },
    { id: "personas", label: "🎭 Personas" },
  ];
</script>

<header>
  <div class="header-shell">
    <div class="brand-wrap">
      <span class="brand-mark" aria-hidden="true"></span>
      <span class="brand">Lorebook</span>
    </div>

    <nav class="tabs" aria-label="Primary pages">
      {#each tabs as tab}
        <button
          type="button"
          class="nav-btn"
          class:active={activeTab === tab.id}
          onclick={() => onselecttab(tab.id)}
        >
          {tab.label}
        </button>
      {/each}
    </nav>

    <div class="meta">
      {#if showStats}
        <span class="stats">{elapsedMs} ms</span>
      {/if}
    </div>
  </div>
</header>

<style>
  header {
    position: sticky;
    top: 0;
    z-index: 30;
    border-bottom: 1px solid #334155;
    background: radial-gradient(
      circle at top,
      #1e3a8a 0%,
      #111827 40%,
      #020617 100%
    );
    color: #e2e8f0;
    font-family: inherit;
    box-shadow: 0 8px 24px rgba(2, 6, 23, 0.45);
  }

  .header-shell {
    display: grid;
    grid-template-columns: minmax(10rem, 1fr) auto minmax(10rem, 1fr);
    align-items: center;
    gap: 1rem;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0.7rem 1rem;
  }

  .brand-wrap {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    min-width: 0;
  }

  .brand-mark {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 999px;
    background: linear-gradient(135deg, #60a5fa, #2563eb);
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2);
    flex: 0 0 auto;
  }

  .brand {
    font-weight: 700;
    font-size: 1.08rem;
    letter-spacing: 0.02em;
    color: #f8fafc;
  }

  .tabs {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.28rem;
    border: 1px solid #334155;
    border-radius: 12px;
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(8px);
    justify-self: center;
  }

  .meta {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    min-height: 2.15rem;
  }

  .stats {
    display: inline-flex;
    align-items: center;
    height: 2rem;
    padding: 0 0.75rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: #bfdbfe;
    border: 1px solid #1d4ed8;
    border-radius: 999px;
    background: rgba(37, 99, 235, 0.22);
  }

  .nav-btn {
    height: 2rem;
    padding: 0 0.92rem;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    color: #cbd5e1;
    font-size: 0.875rem;
    font-weight: 600;
    line-height: 1;
    cursor: pointer;
    transition:
      background-color 0.16s,
      color 0.16s,
      border-color 0.16s,
      transform 0.16s;
  }

  .nav-btn:hover {
    border-color: #475569;
    background: rgba(30, 41, 59, 0.95);
    color: #f8fafc;
    transform: translateY(-1px);
  }

  .nav-btn:focus-visible {
    outline: 2px solid #60a5fa;
    outline-offset: 2px;
  }

  .nav-btn.active {
    border-color: #1d4ed8;
    background: linear-gradient(135deg, #2563eb, #1e40af);
    color: #eff6ff;
    box-shadow: 0 10px 18px rgba(37, 99, 235, 0.35);
    transform: translateY(0);
  }

  @media (max-width: 900px) {
    .header-shell {
      grid-template-columns: 1fr auto;
      row-gap: 0.7rem;
    }

    .tabs {
      grid-column: 1 / -1;
      justify-self: stretch;
      justify-content: center;
      flex-wrap: wrap;
    }
  }
</style>
