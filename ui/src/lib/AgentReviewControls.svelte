<script>
  let {
    review,
    onreview = () => {},
  } = $props()
</script>

{#if review}
  <div class="agent-review-controls">
    <strong>Agent edit · {review.label}</strong>
    <div role="tablist" aria-label={`${review.label} agent comparison`}>
      <button
        class:active={review.view !== 'old'}
        type="button"
        role="tab"
        onclick={() => onreview({ reviewId: review.id, action: 'view', view: 'new' })}
      >New</button>
      <button
        class:active={review.view === 'old'}
        type="button"
        role="tab"
        onclick={() => onreview({ reviewId: review.id, action: 'view', view: 'old' })}
      >Old</button>
      <button type="button" onclick={() => onreview({ reviewId: review.id, action: 'keep' })}>Keep New</button>
      <button class="revert" type="button" onclick={() => onreview({ reviewId: review.id, action: 'revert' })}>Revert</button>
    </div>
  </div>
{/if}

<style>
  .agent-review-controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    padding: 0.45rem 0.55rem;
    border: 1px solid rgba(34, 211, 238, 0.55);
    border-radius: 7px;
    background: rgba(8, 145, 178, 0.14);
  }
  strong { color: #a5f3fc; font-size: 0.75rem; }
  div[role='tablist'] { display: flex; gap: 0.25rem; flex-wrap: wrap; justify-content: flex-end; }
  button {
    cursor: pointer;
    border: 1px solid #0e7490;
    border-radius: 5px;
    padding: 0.2rem 0.42rem;
    background: #164e63;
    color: #cffafe;
    font-size: 0.7rem;
  }
  button.active { background: #0891b2; color: #fff; }
  button.revert { border-color: #b45309; background: #78350f; color: #fef3c7; }
</style>
