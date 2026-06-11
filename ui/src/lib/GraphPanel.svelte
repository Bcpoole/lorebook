<script>
  import { onMount } from 'svelte'

  let mermaidDef = $state('')
  let error = $state('')
  let container = $state()

  onMount(async () => {
    try {
      const res = await fetch('/api/graph')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      mermaidDef = await res.text()

      const mermaid = (await import('mermaid')).default
      mermaid.initialize({ startOnLoad: false, theme: 'default' })
      const { svg } = await mermaid.render('lorebook-graph', mermaidDef)
      container.innerHTML = svg
    } catch (e) {
      error = e.message
    }
  })
</script>

<div class="graph-wrap">
  {#if error}
    <p class="err">Could not load graph: {error}</p>
  {:else if !mermaidDef}
    <p class="loading">Loading graph…</p>
  {/if}
  <div bind:this={container}></div>
</div>

<style>
  .graph-wrap {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    min-height: 200px;
    overflow: auto;
  }

  .loading, .err { color: #94a3b8; font-style: italic; }
  .err { color: #dc2626; }
</style>
