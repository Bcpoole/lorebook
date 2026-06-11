<script>
  import { marked } from 'marked'

  let { source = '' } = $props()

  marked.setOptions({ breaks: true })
  let rendered = $derived(source ? marked.parse(source) : '')
</script>

{#if rendered}
  <div class="markdown">{@html rendered}</div>
{/if}

<style>
  .markdown :global(p) {
    margin: 0 0 0.75rem;
    line-height: 1.6;
  }

  .markdown :global(p:last-child) {
    margin-bottom: 0;
  }

  .markdown :global(h1),
  .markdown :global(h2),
  .markdown :global(h3),
  .markdown :global(h4) {
    margin: 1rem 0 0.5rem;
    line-height: 1.2;
  }

  .markdown :global(ul),
  .markdown :global(ol) {
    margin: 0 0 0.75rem 1.25rem;
    padding: 0;
  }

  .markdown :global(li) {
    margin: 0.25rem 0;
  }

  .markdown :global(code) {
    background: #e2e8f0;
    padding: 0.1rem 0.25rem;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.95em;
  }

  .markdown :global(pre) {
    background: #e2e8f0;
    padding: 0.75rem;
    border-radius: 8px;
    overflow: auto;
    margin: 0 0 0.75rem;
  }
</style>
