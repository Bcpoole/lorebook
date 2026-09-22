<script>
  let {
    title,
    section,
    items = [],
    bodyKey = 'description',
    extraKey = '',
    tooltip = '',
    disabled = false,
    agentReviews = [],
    onupdate = () => {},
    onadd = () => {},
    onremove = () => {},
    onimage = () => {},
    onagentreview = () => {},
  } = $props()

  const isCharacter = $derived(section === 'characters_artifact')
  const bodyLabel = $derived(bodyKey === 'summary' ? 'Summary' : bodyKey === 'text' ? 'Text' : 'Description')
  let tagInputs = $state({})

  function updateItem(index, key, value) {
    onupdate(index, { ...(items[index] ?? {}), [key]: value })
  }

  function addTag(index, value) {
    const tag = value.trim().toLowerCase()
    const currentTags = Array.isArray(items[index]?.tags) ? items[index].tags : []
    if (!tag || currentTags.includes(tag)) return
    updateItem(
      index,
      'tags',
      [...currentTags, tag],
    )
  }

  function removeTag(index, tag) {
    updateItem(index, 'tags', (items[index]?.tags ?? []).filter((entry) => entry !== tag))
  }

  function handleTagKeydown(index, event) {
    if (event.key !== 'Enter' && event.key !== ',') return
    event.preventDefault()
    addTag(index, event.currentTarget.value)
    tagInputs = { ...tagInputs, [index]: '' }
  }
</script>

<section class="story-module">
  <header>
    <h3>{title} <span>({items.length})</span></h3>
    <button type="button" class="add" onclick={onadd} disabled={disabled}>+ Add</button>
    {#if tooltip}<span class="tooltip" aria-label={tooltip} title={tooltip}>?</span>{/if}
  </header>

  <div class="module-items">
    {#each items as item, index}
      {@const agentReview = agentReviews.find((review) => review.entity_index === index)}
      {@const displayItem = agentReview?.view === 'old' ? agentReview.before ?? {} : item}
      <article class:agent-reviewing={Boolean(agentReview)} class="module-item">
        {#if agentReview}
          <div class="agent-review-bar">
            <strong>Agent edit · {agentReview.label}</strong>
            <div class="agent-review-tabs" role="tablist" aria-label={`${agentReview.label} agent comparison`}>
              <button
                class:active={agentReview.view !== 'old'}
                type="button"
                role="tab"
                onclick={() => onagentreview({ reviewId: agentReview.id, action: 'view', view: 'new' })}
              >New</button>
              <button
                class:active={agentReview.view === 'old'}
                type="button"
                role="tab"
                onclick={() => onagentreview({ reviewId: agentReview.id, action: 'view', view: 'old' })}
              >Old</button>
              <button type="button" onclick={() => onagentreview({ reviewId: agentReview.id, action: 'keep' })}>Keep New</button>
              <button class="revert" type="button" onclick={() => onagentreview({ reviewId: agentReview.id, action: 'revert' })}>Revert</button>
            </div>
          </div>
        {/if}
        <div class="item-controls">
          <button
            type="button"
            class="remove"
            title={`Remove ${displayItem.name || displayItem.label || 'item'}`}
            aria-label={`Remove ${displayItem.name || displayItem.label || 'item'}`}
            onclick={() => onremove(index)}
            disabled={disabled}
          >×</button>
          <button
            type="button"
            class="image"
            title="Generate image"
            aria-label={`Generate image for ${displayItem.name || 'item'}`}
            onclick={() => onimage(index)}
            disabled={disabled}
          >▧</button>
        </div>
        <input
          type="text"
          value={displayItem.name ?? ''}
          placeholder={`${title.slice(0, -1)} name`}
          aria-label={`${title} ${index + 1} name`}
          oninput={(event) => updateItem(index, 'name', event.currentTarget.value)}
          disabled={disabled || agentReview?.view === 'old'}
        />
        {#if isCharacter}
          <input
            type="text"
            value={displayItem.role ?? ''}
            placeholder="Character role"
            aria-label={`${title} ${index + 1} role`}
            oninput={(event) => updateItem(index, 'role', event.currentTarget.value)}
            disabled={disabled || agentReview?.view === 'old'}
          />
        {/if}
        <textarea
          rows="3"
          value={displayItem[bodyKey] ?? ''}
          placeholder={`${bodyLabel}...`}
          aria-label={`${title} ${index + 1} ${bodyLabel}`}
          oninput={(event) => updateItem(index, bodyKey, event.currentTarget.value)}
          disabled={disabled || agentReview?.view === 'old'}
        ></textarea>
        {#if extraKey === 'tags'}
          <div class="tag-editor">
            {#each displayItem.tags ?? [] as tag}
              <button type="button" class="tag-badge" onclick={() => removeTag(index, tag)} disabled={disabled} title={`Remove ${tag}`}>{tag} ×</button>
            {/each}
            <input
              type="text"
              value={tagInputs[index] ?? ''}
              placeholder="Add tag"
              aria-label={`${title} ${index + 1} tags`}
              oninput={(event) => (tagInputs = { ...tagInputs, [index]: event.currentTarget.value })}
              onkeydown={(event) => handleTagKeydown(index, event)}
              disabled={disabled || agentReview?.view === 'old'}
            />
          </div>
        {/if}
        {#if displayItem.image_data}
          <img src={displayItem.image_data} alt={`Generated art for ${displayItem.name || displayItem.label || 'item'}`} />
        {/if}
      </article>
    {/each}
  </div>
</section>

<style>
  .story-module {
    display: grid;
    gap: 0.6rem;
    border-top: 1px solid var(--lb-border-1, #334155);
    padding-top: 0.8rem;
  }

  header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  h3 {
    margin: 0;
    font-size: 0.95rem;
    color: var(--lb-text-1, #e2e8f0);
  }

  h3 span {
    color: var(--lb-text-2, #94a3b8);
    font-weight: 400;
  }

  button {
    cursor: pointer;
  }

  .add {
    border: 1px solid var(--lb-border-1, #475569);
    border-radius: 999px;
    background: transparent;
    color: var(--lb-text-1, #e2e8f0);
    padding: 0.25rem 0.65rem;
  }
  .tooltip {
    display: inline-flex; align-items: center; justify-content: center;
    width: 1rem; height: 1rem; border: 1px solid #64748b; border-radius: 50%;
    color: #cbd5e1; font-size: 0.7rem; cursor: help;
  }

  .module-items {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.6rem;
  }

  .module-item {
    position: relative;
    display: grid;
    gap: 0.4rem;
    padding: 0.7rem;
    border: 1px solid var(--lb-border-1, #334155);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.38);
  }
  .module-item.agent-reviewing {
    border-color: #22d3ee;
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.2);
  }
  .agent-review-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin: -0.7rem -0.7rem 0.2rem;
    padding: 0.45rem 0.55rem;
    border-bottom: 1px solid rgba(34, 211, 238, 0.45);
    background: rgba(8, 145, 178, 0.16);
  }
  .agent-review-bar strong { color: #a5f3fc; font-size: 0.75rem; }
  .agent-review-tabs { display: flex; gap: 0.25rem; flex-wrap: wrap; justify-content: flex-end; }
  .agent-review-tabs button {
    border: 1px solid #0e7490;
    border-radius: 5px;
    padding: 0.2rem 0.42rem;
    background: #164e63;
    color: #cffafe;
    font-size: 0.7rem;
  }
  .agent-review-tabs button.active { background: #0891b2; color: #fff; }
  .agent-review-tabs button.revert { border-color: #b45309; background: #78350f; color: #fef3c7; }

  .item-controls {
    position: absolute;
    top: 0.45rem;
    right: 0.45rem;
    display: flex;
    gap: 0.25rem;
  }
  .module-item.agent-reviewing .item-controls {
    top: 3.35rem;
  }

  .item-controls button {
    width: 1.5rem;
    height: 1.5rem;
    border: 0;
    border-radius: 4px;
    background: rgba(51, 65, 85, 0.7);
    color: #cbd5e1;
  }

  .item-controls .remove {
    color: #fca5a5;
  }

  input,
  textarea {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--lb-border-1, #475569);
    border-radius: 6px;
    padding: 0.45rem 0.55rem;
    background: rgba(30, 41, 59, 0.85);
    color: var(--lb-text-1, #e2e8f0);
  }
  .tag-editor { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }
  .tag-editor input { flex: 1 1 7rem; min-width: 6rem; }
  .tag-badge {
    width: auto; border: 1px solid rgba(56, 189, 248, 0.45); border-radius: 999px;
    padding: 0.22rem 0.55rem; background: rgba(14, 116, 144, 0.2);
    color: #bae6fd; font-size: 0.78rem;
  }

  input:first-of-type {
    padding-right: 3.5rem;
  }

  textarea {
    resize: vertical;
    min-height: 5rem;
    line-height: 1.45;
  }

  img {
    width: 100%;
    border-radius: 6px;
  }

  button:disabled,
  input:disabled,
  textarea:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

  @media (max-width: 640px) {
    .module-items { grid-template-columns: 1fr; }
  }
</style>
