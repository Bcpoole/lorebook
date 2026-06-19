<script>
  /**
   * PersonaCard - Individual persona card for list display
   */

  let {
    persona = {},
    onfavorite = () => {},
    onedit = () => {},
    onduplicate = () => {},
    ondelete = () => {},
  } = $props()

  let isHovering = $state(false)

  function handleDelete(e) {
    e.stopPropagation()
    ondelete()
  }

  function getAvatarSrc() {
    const raw = persona?.avatar || persona?.avatarUrl || ''
    if (!raw) return ''
    if (raw.startsWith('data:image/')) return raw
    if (raw.startsWith('/') || raw.startsWith('http://') || raw.startsWith('https://')) return raw
    return `/api/personas/${persona.id}/avatar`
  }
</script>

<div class="persona-card" class:hovering={isHovering}>
  <div class="card-header">
    <div class="name-row">
      {#if getAvatarSrc()}
        <img class="avatar-thumb" src={getAvatarSrc()} alt={`${persona.name} avatar`} />
      {/if}
      <h3 class="persona-name">{persona.name}</h3>
    </div>
    <div class="header-actions">
      <button
        type="button"
        class="btn btn-icon btn-secondary"
        aria-label={persona?.favorite ? 'Unfavorite persona' : 'Favorite persona'}
        title={persona?.favorite ? 'Unfavorite persona' : 'Favorite persona'}
        onclick={(e) => {
          e.stopPropagation()
          onfavorite()
        }}
      >
        {persona?.favorite ? '★' : '☆'}
      </button>

      <button
        type="button"
        class="btn btn-icon btn-secondary"
        aria-label="Duplicate persona"
        title="Duplicate persona"
        onclick={(e) => {
          e.stopPropagation()
          onduplicate()
        }}
      >
        ⧉
      </button>

      <button
        type="button"
        class="btn btn-icon btn-secondary"
        aria-label="Edit persona"
        title="Edit persona"
        onclick={(e) => {
          e.stopPropagation()
          onedit()
        }}
      >
        ✏️
      </button>

      <button
        type="button"
        class="btn btn-icon btn-danger"
        aria-label="Delete persona"
        title="Delete persona"
        onclick={handleDelete}
      >
        🗑️
      </button>
    </div>
  </div>

  <p class="description">{persona.description}</p>

  {#if persona.tags && persona.tags.length > 0}
    <div class="tags">
      {#each persona.tags as tag}
        <span class="tag">{tag}</span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .persona-card {
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1.25rem;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    transition: all 0.2s ease;
    cursor: pointer;
    position: relative;
    overflow: hidden;
  }

  .persona-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(
      circle at top right,
      rgba(37, 99, 235, 0.05) 0%,
      transparent 60%
    );
    pointer-events: none;
  }

  .persona-card:hover {
    border-color: #475569;
    background: linear-gradient(135deg, #1e293b 0%, #1a2540 100%);
    box-shadow: 0 12px 24px rgba(2, 6, 23, 0.3);
    transform: translateY(-2px);
  }

  .persona-card.hovering {
    border-color: #0ea5e9;
    box-shadow: 0 0 0 1px #0ea5e9, 0 12px 24px rgba(6, 182, 212, 0.1);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 0 0 auto;
  }

  .name-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    min-width: 0;
    flex: 1;
  }

  .avatar-thumb {
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    object-fit: cover;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: #0b1220;
    flex-shrink: 0;
  }

  .persona-name {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 600;
    color: #f8fafc;
    letter-spacing: 0.02em;
    flex: 1;
  }

  .description {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.4;
    flex: 1;
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .tag {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    background: rgba(148, 163, 184, 0.1);
    color: #cbd5e1;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
    border: 1px solid rgba(148, 163, 184, 0.2);
  }

  .btn {
    padding: 0.5rem 0.75rem;
    border: 1px solid transparent;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    background: transparent;
  }

  .btn-secondary {
    border-color: transparent;
    background: transparent;
    color: #cbd5e1;
  }

  .btn-secondary:hover {
    background: rgba(30, 41, 59, 0.45);
    border-color: #475569;
  }

  .btn-danger {
    border-color: transparent;
    background: transparent;
    color: #fca5a5;
  }

  .btn-danger:hover {
    background: rgba(127, 29, 29, 0.22);
    border-color: #b91c1c;
  }

  .btn-icon {
    width: 2.2rem;
    height: 2.2rem;
    padding: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    flex: 0 0 auto;
  }
</style>
