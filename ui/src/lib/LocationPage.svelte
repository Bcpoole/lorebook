<script>
  import { onMount } from 'svelte'
  import LocationEditPanel from './LocationEditPanel.svelte'
  import Toast from './Toast.svelte'

  let {
    id = '',
  } = $props()

  let location = $state(null)
  let loading = $state(true)
  let editMode = $state(false)
  let error = $state('')
  let toastMessage = $state('')
  let toastVisible = $state(false)
  let deleting = $state(false)

  onMount(() => {
    loadLocation()
  })

  async function loadLocation() {
    if (!id) {
      error = 'Location ID not provided'
      loading = false
      return
    }

    try {
      const res = await fetch(`/api/artifact/location/${id}`)
      if (res.status === 404) {
        error = 'Location not found'
      } else if (!res.ok) {
        error = 'Failed to load location'
      } else {
        location = await res.json()
        error = ''
      }
    } catch (err) {
      error = 'Error loading location: ' + (err.message || 'Unknown error')
    } finally {
      loading = false
    }
  }

  async function handleSave(updatedData) {
    // updatedData is the response from /api/save
    location = { ...location, ...updatedData.artifact }
    editMode = false
    toastMessage = 'Location updated ✓'
    toastVisible = true
  }

  async function handleDelete() {
    if (!location?.id) return
    if (!confirm('Are you sure you want to delete this location? This cannot be undone.')) {
      return
    }

    deleting = true
    try {
      const res = await fetch(`/api/artifact/location/${location.id}`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        throw new Error('Failed to delete location')
      }

      toastMessage = 'Location deleted ✓'
      toastVisible = true
      setTimeout(() => {
        window.location.href = '/worlds-stories'
      }, 1500)
    } catch (err) {
      error = err.message || 'Failed to delete location'
    } finally {
      deleting = false
    }
  }
</script>

<div class="location-page">
  {#if loading}
    <div class="loading">
      <p>Loading location...</p>
    </div>
  {:else if error}
    <div class="error-container">
      <p class="error-title">⚠️ Error</p>
      <p>{error}</p>
      <a href="/worlds-stories">← Back to Gallery</a>
    </div>
  {:else if location}
    {#if !editMode}
      <div class="location-display">
        <div class="page-header">
          <h1>{location.name}</h1>
          <div class="actions">
            <button on:click={() => (editMode = true)} class="edit-btn">✏️ Edit</button>
            <button on:click={handleDelete} disabled={deleting} class="delete-btn">
              {deleting ? '🗑️ Deleting...' : '🗑️ Delete'}
            </button>
          </div>
        </div>

        {#if location.image_file}
          <div class="image-container">
            <img src={location.image_data || location.image_file} alt={location.name} />
          </div>
        {/if}

        <section class="section">
          <h2>Description</h2>
          <p>{location.description}</p>
        </section>

        {#if location.atmosphere}
          <section class="section">
            <h3>Atmosphere</h3>
            <p><strong>{location.atmosphere}</strong></p>
          </section>
        {/if}

        {#if location.accessibility}
          <section class="section">
            <h3>How to Access</h3>
            <p>{location.accessibility}</p>
          </section>
        {/if}

        {#if location.inhabitants}
          <section class="section">
            <h3>Inhabitants</h3>
            <p>{location.inhabitants}</p>
          </section>
        {/if}

        {#if location.history}
          <section class="section">
            <h3>History & Significance</h3>
            <p>{location.history}</p>
          </section>
        {/if}

        <div class="metadata">
          <p>
            <small>ID: <code>{location.id}</code></small>
          </p>
          {#if location.created_at}
            <p>
              <small>Created: {new Date(location.created_at).toLocaleString()}</small>
            </p>
          {/if}
          {#if location.modified_at}
            <p>
              <small>Modified: {new Date(location.modified_at).toLocaleString()}</small>
            </p>
          {/if}
        </div>
      </div>
    {:else}
      <div class="edit-container">
        <LocationEditPanel location={location} onSave={handleSave} onCancel={() => (editMode = false)} />
      </div>
    {/if}
  {/if}

  <Toast message={toastMessage} visible={toastVisible} on:close={() => (toastVisible = false)} />
</div>

<style>
  .location-page {
    display: grid;
    gap: 1.5rem;
    padding: 2rem;
    max-width: 900px;
    margin: 0 auto;
  }

  .loading,
  .error-container {
    padding: 2rem;
    text-align: center;
  }

  .error-container {
    background: #fee2e2;
    border: 1px solid #fecaca;
    border-radius: 8px;
  }

  .error-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #991b1b;
    margin: 0 0 0.5rem 0;
  }

  .error-container p {
    color: #7c2d12;
    margin: 0.5rem 0;
  }

  .error-container a {
    display: inline-block;
    margin-top: 1rem;
    color: #2563eb;
    text-decoration: none;
    font-weight: 600;
  }

  .error-container a:hover {
    text-decoration: underline;
  }

  .location-display {
    display: grid;
    gap: 2rem;
  }

  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 2rem;
  }

  h1 {
    margin: 0;
    font-size: 2rem;
    color: #1e293b;
    flex: 1;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    flex-shrink: 0;
  }

  button {
    padding: 0.75rem 1rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #f8fafc;
    color: #334155;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  button:hover:not(:disabled) {
    background: #e2e8f0;
    border-color: #94a3b8;
  }

  button.edit-btn:hover {
    background: #dbeafe;
    border-color: #2563eb;
    color: #2563eb;
  }

  button.delete-btn:hover:not(:disabled) {
    background: #fee2e2;
    border-color: #dc2626;
    color: #dc2626;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .image-container {
    width: 100%;
    border-radius: 8px;
    overflow: hidden;
    background: #f1f5f9;
    aspect-ratio: 16 / 9;
  }

  .image-container img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .section {
    display: grid;
    gap: 0.75rem;
  }

  h2,
  h3 {
    margin: 0;
    color: #1e293b;
  }

  h2 {
    font-size: 1.5rem;
  }

  h3 {
    font-size: 1.1rem;
  }

  section p {
    color: #475569;
    line-height: 1.6;
    margin: 0;
  }

  .metadata {
    padding: 1rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
  }

  .metadata p {
    margin: 0.25rem 0;
    color: #64748b;
    font-size: 0.875rem;
  }

  code {
    background: #e2e8f0;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-family: monospace;
    font-size: 0.85rem;
  }

  .edit-container {
    max-width: 700px;
  }
</style>
