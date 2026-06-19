<script>
  import Toast from './Toast.svelte'

  let {
    location = $bindable(null),
    onSave,
    onCancel,
  } = $props()

  let formData = $state({
    name: location?.name || '',
    description: location?.description || '',
    atmosphere: location?.atmosphere || '',
    accessibility: location?.accessibility || '',
    inhabitants: location?.inhabitants || '',
    history: location?.history || '',
    newImageFile: null,
  })

  let saving = $state(false)
  let errors = $state({})
  let toastMessage = $state('')
  let toastVisible = $state(false)
  let imagePreview = $state(location?.image_data || location?.image_file || null)

  const ATMOSPHERE_OPTIONS = [
    'cozy',
    'mysterious',
    'grand',
    'dark',
    'bright',
    'eerie',
    'peaceful',
    'bustling',
    'ancient',
    'modern',
  ]

  function validate() {
    errors = {}
    if (!formData.name.trim()) {
      errors.name = 'Name is required'
    }
    if (!formData.description.trim()) {
      errors.description = 'Description is required'
    }
    return Object.keys(errors).length === 0
  }

  function handleImageChange(event) {
    const file = event.target.files?.[0]
    if (!file) return

    formData.newImageFile = file
    const reader = new FileReader()
    reader.onload = (e) => {
      imagePreview = e.target.result
    }
    reader.readAsDataURL(file)
  }

  async function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  async function handleSave() {
    if (!validate()) return

    saving = true
    errors = {}

    try {
      let imageData = null
      if (formData.newImageFile) {
        imageData = await fileToBase64(formData.newImageFile)
      }

      const payload = {
        artifact_type: 'location',
        ...(location?.id && { artifact_id: location.id }),
        name: formData.name,
        description: formData.description,
        atmosphere: formData.atmosphere || null,
        accessibility: formData.accessibility || null,
        inhabitants: formData.inhabitants || null,
        history: formData.history || null,
        ...(imageData && { image_data: imageData }),
      }

      const res = await fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}))
        throw new Error(errPayload?.detail || 'Failed to save location')
      }

      const updated = await res.json()
      toastMessage = 'Location saved ✓'
      toastVisible = true
      onSave?.(updated)
    } catch (err) {
      errors.submit = err.message || 'Failed to save location'
      toastMessage = `Error: ${errors.submit}`
      toastVisible = true
    } finally {
      saving = false
    }
  }

  function handleCancel() {
    onCancel?.()
  }
</script>

<div class="edit-panel">
  <h3>Edit Location</h3>
  <form onsubmit={(event) => {
    event.preventDefault()
    void handleSave()
  }}>
    <div class="form-group">
      <label for="name">Name *</label>
      <input
        id="name"
        type="text"
        bind:value={formData.name}
        placeholder="e.g., Sky Dock, Ancient Ruins"
        aria-invalid={!!errors.name}
      />
      {#if errors.name}
        <p class="error-text">{errors.name}</p>
      {/if}
    </div>

    <div class="form-group">
      <label for="description">Description *</label>
      <textarea
        id="description"
        bind:value={formData.description}
        placeholder="What is this location? What does it look like?"
        rows="4"
        aria-invalid={!!errors.description}
      ></textarea>
      {#if errors.description}
        <p class="error-text">{errors.description}</p>
      {/if}
    </div>

    <div class="form-group">
      <label for="atmosphere">Atmosphere</label>
      <select id="atmosphere" bind:value={formData.atmosphere}>
        <option value="">Select an atmosphere...</option>
        {#each ATMOSPHERE_OPTIONS as opt}
          <option value={opt}>{opt}</option>
        {/each}
      </select>
    </div>

    <div class="form-group">
      <label for="accessibility">How to Access</label>
      <textarea
        id="accessibility"
        bind:value={formData.accessibility}
        placeholder="e.g., Hidden cave, requires climbing. Open only at dusk."
        rows="3"
      ></textarea>
    </div>

    <div class="form-group">
      <label for="inhabitants">Inhabitants</label>
      <textarea
        id="inhabitants"
        bind:value={formData.inhabitants}
        placeholder="Who or what lives here?"
        rows="3"
      ></textarea>
    </div>

    <div class="form-group">
      <label for="history">History & Significance</label>
      <textarea
        id="history"
        bind:value={formData.history}
        placeholder="Background, legends, historical importance..."
        rows="3"
      ></textarea>
    </div>

    <div class="form-group">
      <label for="image">Image</label>
      {#if imagePreview}
        <div class="image-preview">
          <img src={imagePreview} alt="Location preview" />
        </div>
      {/if}
      <input id="image" type="file" accept="image/*" onchange={handleImageChange} />
      <p class="help-text">PNG, JPG, or WebP (optional)</p>
    </div>

    {#if errors.submit}
      <div class="error-box">{errors.submit}</div>
    {/if}

    <div class="button-group">
      <button type="submit" disabled={saving} class="primary">
        {saving ? '💾 Saving...' : '💾 Save Location'}
      </button>
      <button type="button" onclick={handleCancel} disabled={saving}>✕ Cancel</button>
    </div>
  </form>

  <Toast message={toastMessage} visible={toastVisible} on:close={() => (toastVisible = false)} />
</div>

<style>
  .edit-panel {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }

  h3 {
    margin: 0 0 1rem 0;
    font-size: 1.25rem;
    color: #1e293b;
  }

  form {
    display: grid;
    gap: 1.5rem;
  }

  .form-group {
    display: grid;
    gap: 0.5rem;
  }

  label {
    font-weight: 600;
    font-size: 0.95rem;
    color: #475569;
  }

  input[type='text'],
  input[type='file'],
  textarea,
  select {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 0.75rem;
    font-family: inherit;
    font-size: 0.95rem;
  }

  input[type='text']:focus,
  textarea:focus,
  select:focus {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  textarea {
    resize: vertical;
    min-height: 80px;
  }

  input[aria-invalid='true'],
  textarea[aria-invalid='true'] {
    border-color: #dc2626;
  }

  .error-text {
    color: #dc2626;
    font-size: 0.875rem;
    margin: 0;
  }

  .help-text {
    color: #64748b;
    font-size: 0.875rem;
    margin: 0;
  }

  .image-preview {
    width: 100%;
    max-width: 300px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    overflow: hidden;
  }

  .image-preview img {
    width: 100%;
    height: auto;
    display: block;
  }

  .error-box {
    background: #fee2e2;
    border: 1px solid #fecaca;
    border-radius: 6px;
    padding: 0.75rem;
    color: #991b1b;
    font-size: 0.95rem;
  }

  .button-group {
    display: flex;
    gap: 0.75rem;
    margin-top: 1rem;
  }

  button {
    padding: 0.75rem 1.5rem;
    border: 1px solid transparent;
    border-radius: 6px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  button.primary {
    background: #2563eb;
    color: #fff;
    border-color: #2563eb;
  }

  button.primary:hover:not(:disabled) {
    background: #1d4ed8;
  }

  button:not(.primary) {
    background: #f1f5f9;
    color: #334155;
    border-color: #cbd5e1;
  }

  button:not(.primary):hover:not(:disabled) {
    background: #e2e8f0;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
