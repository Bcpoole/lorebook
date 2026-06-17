<script>
  import Toast from './Toast.svelte'

  let {
    object,
    storyId,
    objectIndex = 0,
    onSave = () => {},
    onCancel = () => {},
  } = $props()

  let editing = $state(false)
  let formData = $state(structuredClone(object))
  let saving = $state(false)
  let errors = $state({})
  let toastMessage = $state('')
  let toastVisible = $state(false)

  const MATERIAL_OPTIONS = ['wood', 'metal', 'stone', 'crystal', 'cloth', 'glass', 'ceramic', 'leather', 'bone', 'magical', 'unknown']

  function toggleEdit() {
    if (editing) {
      formData = structuredClone(object)
    }
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
      const res = await fetch(`/api/story/${storyId}/update-object`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          object_index: objectIndex,
          updated_object: {
            name: formData.name,
            description: formData.description,
            material: formData.material || null,
            purpose: formData.purpose || null,
            origin: formData.origin || null,
            properties: formData.properties || null,
          },
        }),
      })

      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}))
        throw new Error(errPayload?.detail || 'Failed to save object')
      }

      const result = await res.json()
      onSave(result)
      editing = false
      toastMessage = `✓ "${formData.name}" updated & saved as artifact`
      toastVisible = true
    } catch (err) {
      errors.submit = err.message || 'Failed to save object'
      toastMessage = `Error: ${errors.submit}`
      toastVisible = true
    } finally {
      saving = false
    }
  }
</script>

<div class="object-item">
  {#if !editing}
    <div class="item-read">
      <div class="item-header">
        <h4>{object.name}</h4>
        <button class="edit-btn" on:click={toggleEdit} type="button" title="Edit object">✏️</button>
      </div>
      <p class="description">{object.description}</p>
      {#if object.material}
        <p class="meta">
          <span class="badge">{object.material}</span>
        </p>
      {/if}
    </div>
  {:else}
    <div class="item-edit">
      <div class="edit-form">
        <div class="form-group">
          <label for="obj-{objectIndex}-name">Name</label>
          <input
            id="obj-{objectIndex}-name"
            type="text"
            bind:value={formData.name}
            placeholder="Object name"
            aria-invalid={!!errors.name}
          />
          {#if errors.name}
            <p class="error-text">{errors.name}</p>
          {/if}
        </div>

        <div class="form-group">
          <label for="obj-{objectIndex}-desc">Description</label>
          <textarea
            id="obj-{objectIndex}-desc"
            bind:value={formData.description}
            placeholder="What is this object?"
            rows="3"
            aria-invalid={!!errors.description}
          ></textarea>
          {#if errors.description}
            <p class="error-text">{errors.description}</p>
          {/if}
        </div>

        <div class="form-group">
          <label for="obj-{objectIndex}-material">Material</label>
          <select id="obj-{objectIndex}-material" bind:value={formData.material}>
            <option value="">None</option>
            {#each MATERIAL_OPTIONS as opt}
              <option value={opt}>{opt}</option>
            {/each}
          </select>
        </div>

        <div class="form-group">
          <label for="obj-{objectIndex}-purpose">Purpose</label>
          <textarea id="obj-{objectIndex}-purpose" bind:value={formData.purpose} rows="2" placeholder="What is it used for?" />
        </div>

        <div class="form-group">
          <label for="obj-{objectIndex}-origin">Origin & History</label>
          <textarea id="obj-{objectIndex}-origin" bind:value={formData.origin} rows="2" placeholder="Where did it come from?" />
        </div>

        <div class="form-group">
          <label for="obj-{objectIndex}-properties">Special Properties</label>
          <textarea id="obj-{objectIndex}-properties" bind:value={formData.properties} rows="2" placeholder="Magical abilities or limitations" />
        </div>

        {#if errors.submit}
          <div class="error-box">{errors.submit}</div>
        {/if}

        <div class="edit-actions">
          <button type="button" class="save-btn" on:click={handleSave} disabled={saving}>
            {saving ? '⏳ Saving...' : '💾 Save & Create Artifact'}
          </button>
          <button type="button" class="cancel-btn" on:click={toggleEdit} disabled={saving}>✕ Cancel</button>
        </div>
      </div>
    </div>
  {/if}

  <Toast message={toastMessage} visible={toastVisible} on:close={() => (toastVisible = false)} />
</div>

<style>
  .object-item {
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
    background: #fef3c7;
    color: #92400e;
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
