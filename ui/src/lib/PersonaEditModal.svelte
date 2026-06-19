<script>
  /**
   * PersonaEditModal - Edit or create a persona with all prompts
   *
   * Each prompt gets its own PromptEditor with template fallback.
   * Empty prompts store empty string but show template as placeholder.
   */

  import PromptEditor from './PromptEditor.svelte'

  let {
    editingPersona = null,
    templatePersona = null,
    readonly = false,
    prefillTemplatePrompts = false,
    promptsOnly = false,
    onsave = () => {},
    onclose = () => {},
  } = $props()

  const isCreateMode = !editingPersona

  function withTemplatePrompts(personaPrompts = [], fillMissingWithTemplate = false) {
    const base = templatePersona?.prompts ?? []
    const byKey = Object.fromEntries((personaPrompts || []).map(p => [p.key, p]))
    return base.map((tp) => ({
      key: tp.key,
      name: tp.name,
      description: tp.description,
      system_prompt: byKey[tp.key]?.system_prompt ?? (fillMissingWithTemplate ? tp.system_prompt : ''),
    }))
  }

  function normalizeForCompare(data) {
    return {
      id: String(data?.id ?? '').trim(),
      name: String(data?.name ?? '').trim(),
      description: String(data?.description ?? '').trim(),
      tags: Array.isArray(data?.tags) ? data.tags.map((t) => String(t).trim()).filter(Boolean) : [],
      avatar: String(data?.avatar ?? '').trim(),
      prompts: (Array.isArray(data?.prompts) ? data.prompts : []).map((p) => ({
        key: p.key,
        system_prompt: String(p.system_prompt ?? ''),
      })),
    }
  }

  let formData = $state({
    id: editingPersona?.id ?? '',
    name: editingPersona?.name ?? '',
    description: editingPersona?.description ?? '',
    tags: [...(editingPersona?.tags ?? [])],
    avatar: editingPersona?.avatar ?? '',
    prompts: withTemplatePrompts(editingPersona?.prompts ?? [], isCreateMode && prefillTemplatePrompts),
  })
  let tagInput = $state('')

  const initialSnapshot = normalizeForCompare({
    id: editingPersona?.id ?? '',
    name: editingPersona?.name ?? '',
    description: editingPersona?.description ?? '',
    tags: [...(editingPersona?.tags ?? [])],
    avatar: editingPersona?.avatar ?? '',
    prompts: withTemplatePrompts(editingPersona?.prompts ?? [], isCreateMode && prefillTemplatePrompts),
  })

  const initialPromptByKey = Object.fromEntries((initialSnapshot.prompts || []).map((p) => [p.key, p.system_prompt]))

  let isDirty = $derived.by(() => {
    return JSON.stringify(normalizeForCompare(formData)) !== JSON.stringify(initialSnapshot)
  })
  let errors = $state({})
  let isSaving = $state(false)

  // Keep prompt list aligned to full schema/template.
  if (templatePersona && formData.prompts.length !== templatePersona.prompts.length) {
    formData.prompts = withTemplatePrompts(
      editingPersona?.prompts ?? formData.prompts,
      isCreateMode && prefillTemplatePrompts,
    )
  }

  const templates = $derived.by(() => {
    if (!templatePersona) return {}
    const result = {}
    for (const p of templatePersona.prompts) {
      result[p.key] = p.system_prompt
    }
    return result
  })

  function getTemplateValue(promptKey) {
    return templates[promptKey] ?? ''
  }

  function getSavedPromptValue(promptKey) {
    const saved = initialPromptByKey[promptKey]
    return typeof saved === 'string' ? saved : ''
  }

  function handlePromptChange(promptKey, newValue) {
    const idx = formData.prompts.findIndex(p => p.key === promptKey)
    if (idx >= 0) {
      formData.prompts[idx].system_prompt = newValue
    }
  }

  function handlePromptDirty() {}

  function handleAvatarUpload(event) {
    const file = event?.target?.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      errors.avatar = 'Please upload an image file'
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      formData.avatar = typeof reader.result === 'string' ? reader.result : ''
      errors.avatar = ''
    }
    reader.readAsDataURL(file)
  }

  function addTag(rawValue) {
    const tag = String(rawValue || '').trim()
    if (!tag) return
    if (formData.tags.some((existing) => existing.toLowerCase() === tag.toLowerCase())) {
      tagInput = ''
      return
    }
    formData.tags = [...formData.tags, tag]
    tagInput = ''
  }

  function removeTag(tagToRemove) {
    formData.tags = formData.tags.filter((tag) => tag !== tagToRemove)
  }

  function getAvatarSrc() {
    const raw = formData.avatar || ''
    if (!raw) return ''
    if (raw.startsWith('data:image/')) return raw
    if (raw.startsWith('/') || raw.startsWith('http://') || raw.startsWith('https://')) return raw
    return formData.id ? `/api/personas/${formData.id}/avatar` : ''
  }

  function validateForm() {
    if (readonly) return true
    errors = {}

    if (!formData.id.trim()) {
      errors.id = 'Persona ID is required'
    } else if (!formData.id.match(/^[a-zA-Z0-9_-]+$/)) {
      errors.id = 'ID must contain only alphanumeric, hyphen, or underscore'
    }

    if (!formData.name.trim()) {
      errors.name = 'Name is required'
    }

    if (!formData.description.trim()) {
      errors.description = 'Description is required'
    }

    return Object.keys(errors).length === 0
  }

  async function handleSubmit() {
    if (!validateForm()) return

    isSaving = true
    try {
      const promptsData = formData.prompts.map(p => ({
        key: p.key,
        name: p.name,
        system_prompt: p.system_prompt,
        description: p.description,
      }))

      onsave(new CustomEvent('save', {
        detail: {
          id: formData.id,
          name: formData.name,
          description: formData.description,
          avatar: formData.avatar,
          tags: formData.tags,
          prompts: promptsData,
        },
      }))
    } finally {
      isSaving = false
    }
  }

  function handleClickOutside(e) {
    if (e.target.classList.contains('modal-overlay')) {
      onclose()
    }
  }
</script>

<div class="modal-overlay" onclick={handleClickOutside}>
  <div class="modal" onclick={(e) => e.stopPropagation()}>
    <div class="modal-header">
      <h2>
        {#if readonly}
          {#if promptsOnly}
            🔍 Default Template
          {:else}
            🔍 {editingPersona?.name ? `View Persona — ${editingPersona.name}` : 'View Persona'}
          {/if}
        {:else if isCreateMode}
          ✨ Create New Persona
        {:else}
          ✏️ Edit Persona — {editingPersona?.name || 'Unnamed'}
        {/if}
      </h2>
      <button
        type="button"
        class="close-btn"
        onclick={onclose}
        aria-label="Close"
      >
        ✕
      </button>
    </div>

    <div class="modal-content">
      {#if !promptsOnly}
      <div class="form-section meta-section">
        <h3>Persona Details</h3>

        {#if isCreateMode}
          <div class="form-group">
            <label for="persona-id">ID *</label>
            <input
              id="persona-id"
              type="text"
              class:error={errors.id}
              placeholder="my-custom-persona"
              bind:value={formData.id}
              disabled={readonly}
            />
            {#if errors.id}
              <span class="error-text">{errors.id}</span>
            {/if}
            <span class="hint-text">Cannot be changed after creation</span>
          </div>
        {/if}

        <div class="form-group">
          <label for="persona-name">Name *</label>
          <input
            id="persona-name"
            type="text"
            class:error={errors.name}
            placeholder="My Custom Persona"
            bind:value={formData.name}
            disabled={readonly}
          />
          {#if errors.name}
            <span class="error-text">{errors.name}</span>
          {/if}
        </div>

        <div class="form-group">
          <label for="persona-description">Description *</label>
          <textarea
            id="persona-description"
            class:error={errors.description}
            placeholder="Brief description of this persona's purpose and style..."
            bind:value={formData.description}
            rows={3}
            disabled={readonly}
          ></textarea>
          {#if errors.description}
            <span class="error-text">{errors.description}</span>
          {/if}
        </div>

        <div class="form-group">
          <label for="persona-tags">Tags</label>
          <div class="tag-input-wrapper" class:readonly={readonly}>
            {#each formData.tags as tag (tag)}
              <span class="tag-chip">
                {tag}
                {#if !readonly}
                  <button
                    type="button"
                    class="tag-remove-btn"
                    aria-label={`Remove tag ${tag}`}
                    onclick={() => removeTag(tag)}
                  >
                    ×
                  </button>
                {/if}
              </span>
            {/each}
            {#if !readonly}
              <input
                id="persona-tags"
                class="tag-input"
                type="text"
                placeholder="Add tag and press Enter"
                bind:value={tagInput}
                onkeydown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addTag(tagInput)
                  } else if (e.key === 'Backspace' && !tagInput && formData.tags.length > 0) {
                    removeTag(formData.tags[formData.tags.length - 1])
                  }
                }}
                onblur={() => addTag(tagInput)}
              />
            {/if}
          </div>
          <span class="hint-text">Press Enter to add tags</span>
        </div>

        <div class="form-group">
          <label for="persona-avatar">Avatar</label>
          <input
            id="persona-avatar"
            class="avatar-file-input"
            type="file"
            accept="image/*"
            onchange={handleAvatarUpload}
            disabled={readonly}
          />
          {#if getAvatarSrc()}
            <div class="avatar-preview">
              <img src={getAvatarSrc()} alt="Persona avatar" />
              {#if !readonly}
                <div class="avatar-overlay-actions">
                  <label for="persona-avatar" class="avatar-overlay-btn" title="Choose File" aria-label="Choose File">
                    📁
                  </label>
                  <button
                    type="button"
                    class="avatar-overlay-btn danger"
                    title="Clear Avatar"
                    aria-label="Clear Avatar"
                    onclick={() => {
                      formData.avatar = ''
                    }}
                  >
                    ✕
                  </button>
                </div>
              {/if}
            </div>
          {:else if !readonly}
            <label for="persona-avatar" class="btn btn-secondary btn-sm avatar-upload-btn">Choose File</label>
          {/if}
          {#if errors.avatar}
            <span class="error-text">{errors.avatar}</span>
          {/if}
        </div>
      </div>
      {/if}

      <div class="form-section prompts-section">
        <h3>System Prompts</h3>
        <p class="section-hint">
          Empty prompts will use the template value. Edit to customize or leave blank to use defaults.
        </p>

        <div class="prompts-list">
          {#each formData.prompts as prompt (prompt.key)}
            {#if readonly}
              <div class="readonly-prompt">
                <div class="readonly-prompt-header">{prompt.name}</div>
                <p class="readonly-prompt-description">{prompt.description}</p>
                <textarea
                  class="readonly-prompt-text"
                  rows={4}
                  value={prompt.system_prompt}
                  placeholder={getTemplateValue(prompt.key)}
                  disabled
                ></textarea>
              </div>
            {:else}
              <PromptEditor
                promptKey={prompt.key}
                promptName={prompt.name}
                value={prompt.system_prompt}
                savedValue={getSavedPromptValue(prompt.key)}
                templateValue={getTemplateValue(prompt.key)}
                description={prompt.description}
                personaDescription={formData.description}
                onchange={(newVal) => handlePromptChange(prompt.key, newVal)}
                ondirty={handlePromptDirty}
              />
            {/if}
          {/each}
        </div>
      </div>
    </div>

    <div class="modal-footer">
      <button
        type="button"
        class="btn btn-secondary"
        onclick={onclose}
        disabled={isSaving}
      >
        {readonly ? 'Close' : 'Cancel'}
      </button>

      {#if !readonly}
        <button
          type="button"
          class="btn btn-primary"
          onclick={handleSubmit}
          disabled={isSaving || !isDirty}
        >
          {isSaving ? '💾 Saving...' : isDirty ? '✓ Save' : 'No Changes'}
        </button>
      {/if}
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(2, 6, 23, 0.7);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    padding: 1rem;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .modal {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
    box-shadow: 0 20px 60px rgba(2, 6, 23, 0.5);
    display: flex;
    flex-direction: column;
    max-width: 900px;
    width: 100%;
    max-height: 90vh;
    animation: slideIn 0.3s ease;
  }

  @keyframes slideIn {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #334155;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  }

  .modal-header h2 {
    margin: 0;
    font-size: 1.35rem;
    color: #f8fafc;
    letter-spacing: 0.02em;
  }

  .close-btn {
    padding: 0.5rem;
    background: transparent;
    border: 1px solid transparent;
    color: #94a3b8;
    font-size: 1.5rem;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    color: #f8fafc;
    background: rgba(71, 85, 105, 0.2);
  }

  .modal-content {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  .form-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .form-section h3 {
    margin: 0;
    font-size: 1.15rem;
    color: #f8fafc;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  .section-hint {
    margin: 0;
    font-size: 0.9rem;
    color: #94a3b8;
  }

  .meta-section {
    border-bottom: 1px solid #334155;
    padding-bottom: 1.5rem;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .form-group label {
    font-size: 0.95rem;
    font-weight: 600;
    color: #cbd5e1;
  }

  .form-group input,
  .form-group textarea {
    padding: 0.75rem 1rem;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #1e293b;
    color: #e2e8f0;
    font-size: 0.95rem;
    font-family: inherit;
    transition: all 0.15s ease;
  }

  .form-group input:focus,
  .form-group textarea:focus {
    outline: none;
    border-color: #0ea5e9;
    background: #1a2332;
    box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
  }

  .form-group input.error,
  .form-group textarea.error {
    border-color: #dc2626;
    background: rgba(220, 38, 38, 0.05);
  }

  .form-group input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background: rgba(30, 41, 59, 0.5);
  }

  .avatar-preview {
    border: 1px solid #334155;
    border-radius: 8px;
    overflow: hidden;
    background: #0b1220;
    max-width: 220px;
    position: relative;
  }

  .avatar-preview img {
    display: block;
    width: 100%;
    height: auto;
    max-height: 220px;
    object-fit: cover;
  }

  .avatar-file-input {
    display: none;
  }

  .avatar-upload-btn {
    width: fit-content;
  }

  .avatar-overlay-actions {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    display: flex;
    gap: 0.5rem;
  }

  .avatar-overlay-btn {
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.45);
    background: rgba(15, 23, 42, 0.55);
    color: #e2e8f0;
    font-size: 0.9rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    backdrop-filter: blur(2px);
    transition: all 0.15s ease;
  }

  .avatar-overlay-btn:hover {
    background: rgba(15, 23, 42, 0.8);
    border-color: rgba(148, 163, 184, 0.75);
  }

  .avatar-overlay-btn.danger:hover {
    border-color: rgba(248, 113, 113, 0.85);
    color: #fecaca;
  }

  .error-text {
    font-size: 0.85rem;
    color: #fca5a5;
    font-weight: 500;
  }

  .hint-text {
    font-size: 0.85rem;
    color: #64748b;
  }

  .tag-input-wrapper {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    align-items: center;
    min-height: 2.8rem;
    padding: 0.45rem 0.55rem;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #1e293b;
    transition: all 0.15s ease;
  }

  .tag-input-wrapper:focus-within {
    border-color: #0ea5e9;
    background: #1a2332;
    box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
  }

  .tag-input-wrapper.readonly {
    opacity: 0.85;
    background: rgba(30, 41, 59, 0.55);
  }

  .tag-input {
    flex: 1 1 9rem;
    min-width: 9rem;
    border: none !important;
    background: transparent !important;
    padding: 0.35rem 0.45rem !important;
    box-shadow: none !important;
  }

  .tag-input:focus {
    outline: none;
  }

  .tag-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.26rem 0.55rem;
    border-radius: 999px;
    background: rgba(37, 99, 235, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.35);
    color: #dbeafe;
    font-size: 0.82rem;
    font-weight: 500;
    line-height: 1.1;
  }

  .tag-remove-btn {
    width: 1rem;
    height: 1rem;
    padding: 0;
    border: none;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.45);
    color: #bfdbfe;
    font-size: 0.75rem;
    line-height: 1;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .tag-remove-btn:hover {
    background: rgba(15, 23, 42, 0.8);
    color: #ffffff;
  }

  .prompts-list {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .readonly-prompt {
    border: 1px solid #334155;
    border-radius: 8px;
    background: #0f172a;
    padding: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }

  .readonly-prompt-header {
    color: #f8fafc;
    font-weight: 600;
    font-size: 0.95rem;
  }

  .readonly-prompt-description {
    margin: 0;
    color: #94a3b8;
    font-size: 0.83rem;
  }

  .readonly-prompt-text {
    width: 100%;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 0.65rem 0.8rem;
    background: #1e293b;
    color: #dbeafe;
    font-size: 0.9rem;
    font-family: inherit;
    resize: vertical;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.5rem;
    border-top: 1px solid #334155;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  }

  .btn {
    padding: 0.7rem 1.4rem;
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }

  .btn-sm {
    padding: 0.45rem 0.75rem;
    font-size: 0.82rem;
  }

  .btn-primary {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: #eff6ff;
    border-color: #1d4ed8;
  }

  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #1d4ed8, #1e40af);
    box-shadow: 0 8px 16px rgba(37, 99, 235, 0.3);
  }

  .btn-secondary {
    background: rgba(51, 65, 85, 0.4);
    color: #cbd5e1;
    border-color: #334155;
  }

  .btn-secondary:hover:not(:disabled) {
    background: rgba(71, 85, 105, 0.5);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 600px) {
    .modal {
      max-width: 100%;
      max-height: 100vh;
      border-radius: 0;
    }

    .modal-content {
      max-height: calc(100vh - 140px);
    }
  }
</style>
