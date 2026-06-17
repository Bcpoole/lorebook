<script>
  import MarkdownBlock from './MarkdownBlock.svelte'

  let {
    location,
    onClose = () => {},
    onEdit = () => {},
    onDelete = () => {},
  } = $props()
</script>

<div class="location-modal">
  <button class="modal-close" on:click={onClose} title="Close">✕</button>

  <div class="modal-content">
    <h2>{location?.name || 'Untitled Location'}</h2>

    {#if location?.description}
      <div class="section">
        <h3>Description</h3>
        <p>{location.description}</p>
      </div>
    {/if}

    {#if location?.atmosphere}
      <div class="section">
        <h3>Atmosphere</h3>
        <p>{location.atmosphere}</p>
      </div>
    {/if}

    {#if location?.accessibility}
      <div class="section">
        <h3>Accessibility</h3>
        <p>{location.accessibility}</p>
      </div>
    {/if}

    {#if location?.inhabitants}
      <div class="section">
        <h3>Inhabitants</h3>
        <p>{location.inhabitants}</p>
      </div>
    {/if}

    {#if location?.history}
      <div class="section">
        <h3>History</h3>
        <p>{location.history}</p>
      </div>
    {/if}
  </div>

  <div class="modal-actions">
    <button class="action-btn edit-btn" on:click={onEdit}>Edit</button>
    <button class="action-btn delete-btn" on:click={onDelete}>Delete</button>
    <button class="action-btn close-btn" on:click={onClose}>Close</button>
  </div>
</div>

<style>
  .location-modal {
    position: relative;
    background: white;
    border-radius: 8px;
    padding: 2rem;
    max-height: 85vh;
    overflow-y: auto;
    display: grid;
    gap: 2rem;
    grid-template-rows: 1fr auto;
  }

  .modal-close {
    position: absolute;
    top: 1rem;
    right: 1rem;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 1.5rem;
    padding: 0;
    opacity: 0.6;
    transition: opacity 0.2s;
    z-index: 10;
  }

  .modal-close:hover {
    opacity: 1;
  }

  .modal-content {
    display: grid;
    gap: 1.5rem;
  }

  h2 {
    margin: 0;
    font-size: 1.75rem;
    color: #1e293b;
  }

  h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.1rem;
    color: #1e293b;
  }

  .section {
    display: grid;
    gap: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #e2e8f0;
  }

  .section:last-of-type {
    border-bottom: none;
  }

  p {
    color: #475569;
    line-height: 1.6;
    margin: 0;
  }

  .modal-actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
  }

  .action-btn {
    padding: 0.75rem 1.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .edit-btn {
    background: #2563eb;
    color: white;
    border-color: #2563eb;
  }

  .edit-btn:hover {
    background: #1d4ed8;
  }

  .delete-btn {
    background: #dc2626;
    color: white;
    border-color: #dc2626;
  }

  .delete-btn:hover {
    background: #b91c1c;
  }

  .close-btn {
    background: #f1f5f9;
    color: #1e293b;
  }

  .close-btn:hover {
    background: #e2e8f0;
  }
</style>
