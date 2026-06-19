<script>
  import Toast from './Toast.svelte'

  let {
    location,
    storyId,
    locationIndex = 0,
    onSave = () => {},
    onCancel = () => {},
  } = $props()

  let editing = $state(false)
  let formData = $state({})
  let saving = $state(false)
  let errors = $state({})
  let toastMessage = $state('')
  let toastVisible = $state(false)

  const ATMOSPHERE_OPTIONS = ['cozy', 'mysterious', 'grand', 'dark', 'bright', 'eerie', 'peaceful', 'bustling', 'ancient', 'modern']

  function toggleEdit() {
    formData = structuredClone(location)
    editing = !editing
  }

  function validate() {
    errors = {}
    if (!formData.name?.trim()) errors.name = 'Name required'
    if (!formData.description?.trim()) errors.description = 'Description required'
    return Object.keys(errors).length === 0
  }

  async function handleSave() {
    if (!validate()) return
    saving = true
    errors = {}

    try {
      const res = await fetch(`/api/story/${storyId}/update-location`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location_index: locationIndex,
          updated_location: {
            name: formData.name,
            description: formData.description,
            atmosphere: formData.atmosphere || null,
            accessibility: formData.accessibility || null,
            inhabitants: formData.inhabitants || null,
            history: formData.history || null,
          },
        }),
      })

      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}))
        throw new Error(errPayload?.detail || 'Failed to save location')
      }

      const result = await res.json()
      onSave(result)
      editing = false
      toastMessage = `✓ "${formData.name}" updated & saved as artifact`
      toastVisible = true
    } catch (err) {
      errors.submit = err.message || 'Failed to save location'
      toastMessage = `Error: ${errors.submit}`
      toastVisible = true
    } finally {
      saving = false
    }
  }
</script>

<div class="location-item">
  {#if !editing}
    <div class="item-read">
      <div class="item-header">
        <h4>{location.name}</h4>
        <button class="edit-btn" onclick={toggleEdit} type="button" title="Edit location">✏️</button>
      </div>
      <p class="description">{location.description}</p>
      {#if location.atmosphere}
        <p class="meta">
          <span class="badge">{location.atmosphere}</span>
        </p>
      {/if}
    </div>
  {:else}
    <div class="item-edit">
      <div class="edit-form">
        <div class="form-group">
          <label for="loc-{locationIndex}-name">Name</label>
          <input
            id="loc-{locationIndex}-name"
            type="text"
            bind:value={formData.name}
            placeholder="Location name"
            aria-invalid={!!errors.name}
          />
          {#if errors.name}
            <p class="error-text">{errors.name}</p>
          {/if}
        </div>

        <div class="form-group">
          <label for="loc-{locationIndex}-desc">Description</label>
          <textarea
            id="loc-{locationIndex}-desc"
            bind:value={formData.description}
            placeholder="What is this location?"
            rows="3"
            aria-invalid={!!errors.description}
          ></textarea>
          {#if errors.description}
            <p class="error-text">{errors.description}</p>
          {/if}
        </div>

        <div class="form-group">
          <label for="loc-{locationIndex}-atm">Atmosphere</label>
          <select id="loc-{locationIndex}-atm" bind:value={formData.atmosphere}>
            <option value="">None</option>
            {#each ATMOSPHERE_OPTIONS as opt}
              <option value={opt}>{opt}</option>
            {/each}
          </select>
        </div>

        <div class="form-group">
          <label for="loc-{locationIndex}-access">How to Access</label>
          <textarea id="loc-{locationIndex}-access" bind:value={formData.accessibility} rows="2" placeholder="e.g., 'Hidden behind waterfall'"></textarea>
        </div>

        <div class="form-group">
          <label for="loc-{locationIndex}-inhabitants">Inhabitants</label>
          <textarea id="loc-{locationIndex}-inhabitants" bind:value={formData.inhabitants} rows="2" placeholder="Who lives here?"></textarea>
        </div>

        <div class="form-group">
          <label for="loc-{locationIndex}-history">History</label>
          <textarea id="loc-{locationIndex}-history" bind:value={formData.history} rows="2" placeholder="Background & significance"></textarea>
        </div>

        {#if errors.submit}
          <div class="error-box">{errors.submit}</div>
        {/if}

        <div class="edit-actions">
          <button type="button" class="save-btn" onclick={handleSave} disabled={saving}>
            {saving ? '⏳ Saving...' : '💾 Save & Create Artifact'}
          </button>
          <button type="button" class="cancel-btn" onclick={toggleEdit} disabled={saving}>✕ Cancel</button>
        </div>
      </div>
    </div>
  {/if}

  <Toast message={toastMessage} visible={toastVisible} on:close={() => (toastVisible = false)} />
</div>

<style>
  .location-item {
    padding: 1rem;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #f8fafc;
    margin-bottom: 0.75rem;
  }

  .item-read {
    display: grid;
    gap: 0.5rem;
  }

  .item-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  h4 {
    margin: 0;
    font-size: 1rem;
    color: #1e293b;
  }

  .edit-btn {
    flex-shrink: 0;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 1rem;
    padding: 0.25rem;
    opacity: 0.7;
    transition: opacity 0.2s;
  }

  .edit-btn:hover {
    opacity: 1;
  }

  .description {
    color: #475569;
    font-size: 0.9rem;
    line-height: 1.4;
    margin: 0;
  }

  .meta {
    margin: 0;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .badge {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    background: #dbeafe;
    color: #1e40af;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .item-edit {
    padding: 0;
  }

  .edit-form {
    display: grid;
    gap: 1rem;
  }

  .form-group {
    display: grid;
    gap: 0.4rem;
  }

  label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #475569;
  }

  input[type='text'],
  textarea,
  select {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 0.5rem;
    font-size: 0.9rem;
    font-family: inherit;
  }

  input[type='text']:focus,
  textarea:focus,
  select:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  textarea {
    resize: vertical;
    min-height: 60px;
  }

  input[aria-invalid='true'],
  textarea[aria-invalid='true'] {
    border-color: #dc2626;
  }

  .error-text {
    color: #dc2626;
    font-size: 0.8rem;
    margin: 0;
  }

  .error-box {
    background: #fee2e2;
    border: 1px solid #fecaca;
    border-radius: 4px;
    padding: 0.5rem;
    color: #991b1b;
    font-size: 0.85rem;
  }

  .edit-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  button {
    padding: 0.5rem 1rem;
    border: 1px solid;
    border-radius: 4px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .save-btn {
    background: #2563eb;
    color: white;
    border-color: #2563eb;
    flex: 1;
  }

  .save-btn:hover:not(:disabled) {
    background: #1d4ed8;
  }

  .cancel-btn {
    background: #f1f5f9;
    color: #334155;
    border-color: #cbd5e1;
  }

  .cancel-btn:hover:not(:disabled) {
    background: #e2e8f0;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
