<script>
  /**
   * PersonaPage - Main persona management and CRUD editor
   *
   * Features:
   * - List all personas with cards
   * - Create new personas via wizard
   * - Edit existing personas
   * - Delete personas
   * - View/copy template persona
   */

  import { onMount } from "svelte";
  import PersonaCard from "./PersonaCard.svelte";
  import PersonaEditModal from "./PersonaEditModal.svelte";
  import PersonaWizard from "./PersonaWizard.svelte";
  import Toast from "./Toast.svelte";
  let {
    onpersonaschanged = async () => {},
    addCopyTagOnDuplicate = true,
  } = $props();

  let personas = $state([]);
  let templatePersona = $state(null);
  let loading = $state(true);
  let error = $state("");
  let toastMessage = $state("");
  let toastVisible = $state(false);
  let showWizard = $state(false);
  let showEditModal = $state(false);
  let editingPersona = $state(null);
  let editModalReadonly = $state(false);
  let editModalPrefillTemplate = $state(false);
  let editModalPromptsOnly = $state(false);
  let templateSectionExpanded = $state(true);
  let searchQuery = $state("");
  let sortBy = $state("name"); // 'name', 'created', 'prompts'

  onMount(async () => {
    await loadPersonas();
    await loadTemplate();
  });

  async function notifyPersonasChanged() {
    await onpersonaschanged();
  }

  async function loadPersonas() {
    try {
      loading = true;
      error = "";
      const response = await fetch("/api/personas");
      if (!response.ok) throw new Error("Failed to load personas");
      personas = await response.json();
    } catch (err) {
      error = err.message || "Failed to load personas";
      showToast("Error: " + error, "error");
    } finally {
      loading = false;
    }
  }

  async function loadTemplate() {
    try {
      const response = await fetch("/api/personas/template");
      if (response.ok) {
        templatePersona = await response.json();
      }
    } catch (err) {
      console.error("Failed to load template:", err);
    }
  }

  async function handleSavePersona(event) {
    const { id, name, description, tags, avatar, prompts } = event.detail;

    try {
      const url = editingPersona
        ? `/api/personas/${editingPersona.id}`
        : "/api/personas";
      const method = editingPersona ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id,
          name,
          description,
          avatar,
          tags,
          prompts,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to save persona");
      }

      showToast(
        editingPersona
          ? `Persona updated (${editingPersona.id})`
          : "Persona created",
        "success",
      );
      showEditModal = false;
      editingPersona = null;
      await loadPersonas();
      await notifyPersonasChanged();
    } catch (err) {
      showToast("Error: " + (err.message || "Failed to save persona"), "error");
    }
  }

  async function handleDeletePersona(event) {
    const { personaId } = event.detail;

    if (!confirm(`Delete persona "${personaId}"? This cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/personas/${personaId}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Failed to delete persona");

      showToast("Persona deleted", "success");
      await loadPersonas();
      await notifyPersonasChanged();
    } catch (err) {
      showToast(
        "Error: " + (err.message || "Failed to delete persona"),
        "error",
      );
    }
  }

  async function handleDuplicatePersona(event) {
    const { persona } = event.detail;
    try {
      const response = await fetch(`/api/personas/${persona.id}`);
      if (!response.ok) throw new Error("Failed to load persona for duplication");
      const source = await response.json();

      const usedIds = new Set(personas.map((p) => p.id));
      let candidateId = `${source.id}-copy`;
      let index = 2;
      while (usedIds.has(candidateId)) {
        candidateId = `${source.id}-copy-${index}`;
        index++;
      }

      async function toDataUrl(imageUrl) {
        if (!imageUrl) return "";
        const imageResponse = await fetch(imageUrl, { cache: "no-store" });
        if (!imageResponse.ok) return "";
        const blob = await imageResponse.blob();
        return await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
          reader.onerror = () => reject(new Error("Failed to read avatar image"));
          reader.readAsDataURL(blob);
        });
      }
      const copiedAvatar = await toDataUrl(source.avatarUrl || "");
      const sourceTags = Array.isArray(source.tags) ? source.tags : [];
      const hasCopyTag = sourceTags.some(
        (tag) => String(tag || "").trim().toLowerCase() === "copy",
      );
      const duplicateTags =
        addCopyTagOnDuplicate && !hasCopyTag
          ? [...sourceTags, "copy"]
          : sourceTags;

      const createResponse = await fetch("/api/personas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: candidateId,
          name: `${source.name} (Copy)`,
          description: source.description,
          tags: duplicateTags,
          favorite: false,
          avatar: copiedAvatar,
          prompts: source.prompts || [],
        }),
      });
      if (!createResponse.ok) {
        const data = await createResponse.json();
        throw new Error(data.detail || "Failed to duplicate persona");
      }

      showToast(`Persona duplicated (${candidateId})`, "success");
      await loadPersonas();
      await notifyPersonasChanged();
    } catch (err) {
      showToast("Error: " + (err.message || "Failed to duplicate persona"), "error");
    }
  }

  async function handleToggleFavoritePersona(event) {
    const { persona } = event.detail;
    try {
      const response = await fetch(`/api/personas/${persona.id}`);
      if (!response.ok) throw new Error("Failed to load persona");
      const source = await response.json();

      const updateResponse = await fetch(`/api/personas/${persona.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: source.id,
          name: source.name,
          description: source.description,
          tags: source.tags || [],
          favorite: !source.favorite,
          avatar: source.avatar || "",
          prompts: source.prompts || [],
        }),
      });

      if (!updateResponse.ok) {
        const data = await updateResponse.json();
        throw new Error(data.detail || "Failed to update favorite");
      }

      showToast(
        !source.favorite ? `Favorited (${persona.id})` : `Unfavorited (${persona.id})`,
        "success",
      );
      await loadPersonas();
      await notifyPersonasChanged();
    } catch (err) {
      showToast("Error: " + (err.message || "Failed to toggle favorite"), "error");
    }
  }

  async function handleCreateFromWizard(event) {
    const { persona } = event.detail;

    try {
      const response = await fetch("/api/personas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(persona),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to create persona");
      }

      showToast("Persona created from wizard", "success");
      showWizard = false;
      await loadPersonas();
      await notifyPersonasChanged();
    } catch (err) {
      showToast(
        "Error: " + (err.message || "Failed to create persona"),
        "error",
      );
    }
  }

  async function handleEditPersona(event) {
    const { persona } = event.detail;
    try {
      const response = await fetch(`/api/personas/${persona.id}`);
      if (!response.ok) {
        if (response.status === 404 && persona.id === (templatePersona?.id || 'blank') && templatePersona) {
          editingPersona = templatePersona;
          editModalReadonly = true;
          editModalPrefillTemplate = false;
          editModalPromptsOnly = true;
          showEditModal = true;
          return;
        }
        throw new Error("Failed to load persona details");
      }
      editingPersona = await response.json();
      editModalReadonly = false;
      editModalPrefillTemplate = false;
      editModalPromptsOnly = false;
      showEditModal = true;
    } catch (err) {
      showToast("Error: " + (err.message || "Failed to load persona"), "error");
    }
  }

  function showToast(message, type = "info") {
    toastMessage = message;
    toastVisible = true;
    setTimeout(() => {
      toastVisible = false;
    }, 4000);
  }

  function openCreateWizard() {
    showWizard = true;
  }

  function openCreateFromTemplate() {
    editingPersona = null;
    editModalReadonly = false;
    editModalPrefillTemplate = true;
    editModalPromptsOnly = false;
    showEditModal = true;
  }

  function openTemplateReadonly() {
    if (!templatePersona) return;
    editingPersona = templatePersona;
    editModalReadonly = true;
    editModalPrefillTemplate = false;
    editModalPromptsOnly = true;
    showEditModal = true;
  }

  function toggleTemplateSection() {
    templateSectionExpanded = !templateSectionExpanded;
  }

  function closeWizard() {
    showWizard = false;
  }

  function closeEditModal() {
    showEditModal = false;
    editingPersona = null;
    editModalReadonly = false;
    editModalPrefillTemplate = false;
    editModalPromptsOnly = false;
  }

  const filteredPersonas = $derived.by(() => {
    let result = personas;

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.id.toLowerCase().includes(query) ||
          p.name.toLowerCase().includes(query) ||
          p.description.toLowerCase().includes(query) ||
          p.tags.some((t) => t.toLowerCase().includes(query)),
      );
    }

    // Sort
    if (sortBy === "name") {
      result = [...result].sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortBy === "prompts") {
      result = [...result].sort(
        (a, b) => (b.promptCount ?? 0) - (a.promptCount ?? 0),
      );
    }

    return result;
  });
</script>

<div class="persona-page">
  <div class="page-header">
    <div>
      <h1>🎭 Personas</h1>
      <p class="subtitle">
        Create and manage AI personas with custom system prompts
      </p>
    </div>

    <div class="header-actions">
      <button
        type="button"
        class="btn btn-primary"
        onclick={openCreateWizard}
        title="Create persona with wizard"
        aria-label="Create persona with wizard"
      >
        ✨ New Persona (Wizard)
      </button>
    </div>
  </div>

  {#if error}
    <div class="error-banner">
      <p>⚠️ {error}</p>
      <button
        type="button"
        class="btn btn-sm btn-secondary"
        onclick={loadPersonas}
      >
        Retry
      </button>
    </div>
  {/if}

  <div class="search-bar">
    <input
      type="text"
      class="search-input"
      placeholder="Search personas by name, description, or tags..."
      bind:value={searchQuery}
    />

    <select class="sort-select" bind:value={sortBy}>
      <option value="name">Sort: Name</option>
      <option value="prompts">Sort: Prompt Count</option>
    </select>
  </div>

  <div class="template-section" class:template-section-collapsed={!templateSectionExpanded}>
    <button
      type="button"
      class="template-badge"
      onclick={toggleTemplateSection}
      aria-expanded={templateSectionExpanded}
      aria-controls="template-section-content"
      title={templateSectionExpanded ? "Collapse templates" : "Expand templates"}
    >
      📋 Template {templateSectionExpanded ? "▾" : "▸"}
    </button>
    {#if templateSectionExpanded}
      <div class="template-grid" id="template-section-content">
        <article class="template-card">
          <div class="template-card-header">
            <h3>Default</h3>
            <div class="template-actions template-actions-final">
              <button
                type="button"
                class="template-btn template-btn-final-icon"
                onclick={openTemplateReadonly}
                title="View template"
                aria-label="View template"
              >
                👁
              </button>
              <button
                type="button"
                class="template-btn template-btn-final-icon"
                onclick={openCreateFromTemplate}
                title="Create new persona from template"
                aria-label="Create new persona from template"
              >
                ➕
              </button>
            </div>
          </div>
          <p>Simple default system prompts.</p>
        </article>
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading personas...</p>
    </div>
  {:else if filteredPersonas.length === 0}
    <div class="empty-state">
      <div class="empty-icon">🎭</div>
      <h3>No personas yet</h3>
      <p>Create your first persona to get started</p>
      <div class="empty-actions">
        <button
          type="button"
          class="btn btn-primary"
          onclick={openCreateWizard}
          title="Create persona with wizard"
          aria-label="Create persona with wizard"
        >
          ✨ Create with Wizard
        </button>
      </div>
    </div>
  {:else}
    <div class="personas-grid">
      {#each filteredPersonas as persona (persona.id)}
        <PersonaCard
          {persona}
          onfavorite={() => handleToggleFavoritePersona({ detail: { persona } })}
          onedit={() => handleEditPersona({ detail: { persona } })}
          onduplicate={() => handleDuplicatePersona({ detail: { persona } })}
          ondelete={() =>
            handleDeletePersona({ detail: { personaId: persona.id } })}
        />
      {/each}
    </div>
  {/if}
</div>

{#if showWizard}
  <PersonaWizard onclose={closeWizard} oncreate={handleCreateFromWizard} />
{/if}

{#if showEditModal}
  <PersonaEditModal
    {editingPersona}
    {templatePersona}
    readonly={editModalReadonly}
    prefillTemplatePrompts={editModalPrefillTemplate}
    promptsOnly={editModalPromptsOnly}
    onsave={handleSavePersona}
    onclose={closeEditModal}
  />
{/if}

<Toast message={toastMessage} visible={toastVisible} />

<style>
  .persona-page {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2rem;
    padding: 2rem 1.5rem 2rem 1rem;
    max-width: 1400px;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
    min-height: 100vh;
    background: linear-gradient(135deg, #0f172a 0%, #1a1f35 50%, #0f172a 100%);
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #334155;
  }

  .page-header h1 {
    margin: 0;
    font-size: 2.5rem;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.02em;
  }

  .subtitle {
    margin: 0.5rem 0 0 0;
    font-size: 1.05rem;
    color: #94a3b8;
    font-weight: 400;
  }

  .header-actions {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .btn {
    padding: 0.7rem 1.4rem;
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .btn-primary {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: #eff6ff;
    border-color: #1d4ed8;
  }

  .btn-primary:hover {
    background: linear-gradient(135deg, #1d4ed8, #1e40af);
    box-shadow: 0 8px 16px rgba(37, 99, 235, 0.3);
    transform: translateY(-2px);
  }

  .btn-secondary {
    background: rgba(51, 65, 85, 0.4);
    color: #cbd5e1;
    border-color: #334155;
  }

  .btn-secondary:hover {
    background: rgba(71, 85, 105, 0.5);
    border-color: #475569;
  }

  .btn-sm {
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
  }

  .error-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid #7f1d1d;
    border-radius: 8px;
    background: rgba(127, 29, 29, 0.1);
    color: #fca5a5;
  }

  .error-banner p {
    margin: 0;
    font-weight: 500;
  }

  .search-bar {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .search-input {
    flex: 1;
    padding: 0.75rem 1rem;
    border: 1px solid #334155;
    border-radius: 8px;
    background: #1e293b;
    color: #e2e8f0;
    font-size: 0.95rem;
    transition: all 0.15s ease;
  }

  .search-input:focus {
    outline: none;
    border-color: #0ea5e9;
    background: #1a2332;
    box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
  }

  .search-input::placeholder {
    color: #64748b;
  }

  .sort-select {
    padding: 0.75rem 1rem;
    border: 1px solid #334155;
    border-radius: 8px;
    background: #1e293b;
    color: #e2e8f0;
    font-size: 0.95rem;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .sort-select:focus {
    outline: none;
    border-color: #0ea5e9;
  }

  .template-section {
    margin: 1rem 0;
    position: relative;
    border: 2px dashed #334155;
    border-radius: 12px;
    background: rgba(6, 182, 212, 0.05);
    padding: 1.5rem;
    transition: padding 0.15s ease;
  }

  .template-section.template-section-collapsed {
    padding: 0.55rem 1rem 0.65rem;
  }

  .template-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.75rem;
  }

  .template-card {
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1rem;
    background: rgba(15, 23, 42, 0.45);
  }

  .template-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .template-badge {
    position: absolute;
    top: -0.85rem;
    left: 1.5rem;
    display: inline-block;
    padding: 0.35rem 0.85rem;
    background: linear-gradient(135deg, #06b6d4, #0891b2);
    color: white;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    border: none;
    cursor: pointer;
    white-space: nowrap;
  }

  .template-badge:hover {
    filter: brightness(1.05);
  }

  .template-badge:focus-visible {
    outline: 2px solid #67e8f9;
    outline-offset: 2px;
  }

  .template-card h3 {
    margin: 0;
    font-size: 1.05rem;
    color: #f8fafc;
  }

  .template-card p {
    margin: 0;
    color: #94a3b8;
    font-size: 0.95rem;
  }

  .template-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .template-btn {
    border-radius: 8px;
    border: 1px solid #334155;
    background: #1e293b;
    color: #e2e8f0;
    padding: 0.4rem 0.7rem;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .template-btn:hover {
    transform: translateY(-1px);
  }

  .template-actions-final .template-btn-final-icon {
    width: 2.8rem;
    min-width: 2.8rem;
    padding-left: 0.25rem;
    padding-right: 0.25rem;
    text-align: center;
    font-size: 1rem;
    border-color: transparent;
    background: transparent;
    color: #e2e8f0;
  }

  .template-actions-final .template-btn-final-icon:hover {
    background: rgba(30, 41, 59, 0.45);
    border-color: #475569;
  }

  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 3rem;
    color: #94a3b8;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #334155;
    border-top-color: #2563eb;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
  }

  .empty-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
  }

  .empty-state h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.5rem;
    color: #f8fafc;
  }

  .empty-state p {
    margin: 0 0 2rem 0;
    color: #94a3b8;
  }

  .empty-actions {
    display: flex;
    gap: 1rem;
    justify-content: center;
    flex-wrap: wrap;
  }

  .personas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1.5rem;
  }

  @media (max-width: 900px) {
    .page-header {
      flex-direction: column;
    }

    .personas-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
