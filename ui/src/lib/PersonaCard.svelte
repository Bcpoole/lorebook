<script>
  /**
   * PersonaCard - Individual persona card for list display
   */

  let {
    persona = {},
    variant = 'default',
    highlightFavoriteBorder = false,
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

<div
  class={`persona-card persona-card-variant-${variant}`}
  class:hovering={isHovering}
  class:favorite-highlight={highlightFavoriteBorder && Boolean(persona?.favorite)}
>
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
        <span class="icon-star">{persona?.favorite ? '★' : '☆'}</span>
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

  .persona-card.favorite-highlight {
    border-color: #f59e0b;
    background: linear-gradient(145deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.92)),
      radial-gradient(circle at top right, rgba(251, 191, 36, 0.2), transparent 58%);
    box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.35), 0 10px 22px rgba(2, 6, 23, 0.28);
  }

  .persona-card.favorite-highlight:hover,
  .persona-card.favorite-highlight.hovering {
    border-color: #fbbf24;
    background: linear-gradient(145deg, rgba(30, 41, 59, 0.92), rgba(15, 23, 42, 0.95)),
      radial-gradient(circle at top right, rgba(251, 191, 36, 0.28), transparent 58%);
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.45), 0 12px 24px rgba(2, 6, 23, 0.3);
  }

  .persona-card-variant-soft {
    background: linear-gradient(145deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.92));
    border-color: rgba(148, 163, 184, 0.28);
  }

  .persona-card-variant-soft:hover {
    border-color: rgba(148, 163, 184, 0.45);
  }

  .persona-card-variant-glow {
    border-color: rgba(99, 102, 241, 0.65);
    background: linear-gradient(145deg, rgba(30, 27, 75, 0.92), rgba(15, 23, 42, 0.96));
    box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.28), 0 10px 22px rgba(2, 6, 23, 0.32);
  }

  .persona-card-variant-glow:hover {
    border-color: rgba(167, 139, 250, 0.78);
    box-shadow: 0 0 0 1px rgba(167, 139, 250, 0.35), 0 12px 24px rgba(2, 6, 23, 0.35);
  }

  .persona-card-variant-flat {
    background: #0b1220;
    border-color: #1f2937;
    border-radius: 8px;
    box-shadow: none;
  }

  .persona-card-variant-flat:hover {
    background: #0f1a2d;
    border-color: #334155;
    box-shadow: 0 8px 18px rgba(2, 6, 23, 0.24);
  }

  .persona-card-variant-glass {
    background: linear-gradient(160deg, rgba(15, 23, 42, 0.58), rgba(30, 41, 59, 0.52));
    border-color: rgba(56, 189, 248, 0.4);
    backdrop-filter: blur(6px);
  }

  .persona-card-variant-glass:hover {
    border-color: rgba(103, 232, 249, 0.65);
  }

  .persona-card-variant-contrast {
    background: linear-gradient(145deg, #1f2937 0%, #0b1220 100%);
    border-color: rgba(16, 185, 129, 0.52);
    box-shadow: inset 3px 0 0 rgba(16, 185, 129, 0.95);
  }

  .persona-card-variant-contrast:hover {
    border-color: rgba(52, 211, 153, 0.75);
    box-shadow: inset 3px 0 0 rgba(52, 211, 153, 1);
  }

  .persona-card-variant-glow .tag {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(129, 140, 248, 0.4);
    color: #ddd6fe;
  }

  .persona-card-variant-contrast .tag {
    background: rgba(16, 185, 129, 0.12);
    border-color: rgba(16, 185, 129, 0.38);
    color: #a7f3d0;
  }

  .persona-card-variant-soft .btn-secondary {
    border-color: transparent;
    background: transparent;
  }

  .persona-card-variant-soft .btn-secondary:hover {
    background: rgba(30, 41, 59, 0.45);
    border-color: #475569;
  }

  .persona-card-variant-glow .header-actions {
    gap: 0.35rem;
  }

  .persona-card-variant-glow .btn-icon {
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    border-color: rgba(129, 140, 248, 0.55);
    background: rgba(79, 70, 229, 0.25);
    color: #ddd6fe;
  }

  .persona-card-variant-glow .btn-secondary:hover {
    background: rgba(99, 102, 241, 0.38);
    border-color: rgba(167, 139, 250, 0.78);
    color: #f5f3ff;
    transform: translateY(-1px);
  }

  .persona-card-variant-glow .btn-danger {
    border-color: rgba(251, 113, 133, 0.5);
    background: rgba(190, 24, 93, 0.22);
    color: #fecdd3;
  }

  .persona-card-variant-flat .header-actions {
    gap: 0.25rem;
  }

  .persona-card-variant-flat .btn-icon {
    width: 1.9rem;
    height: 1.9rem;
    border-radius: 3px;
    border-color: rgba(100, 116, 139, 0.6);
    background: rgba(15, 23, 42, 0.18);
    color: #cbd5e1;
    font-size: 0.9rem;
  }

  .persona-card-variant-flat .btn-secondary:hover {
    background: rgba(51, 65, 85, 0.55);
    border-color: #94a3b8;
    color: #f8fafc;
  }

  .persona-card-variant-flat .btn-danger {
    border-color: rgba(248, 113, 113, 0.5);
    color: #fca5a5;
  }

  .persona-card-variant-glass .header-actions {
    gap: 0.4rem;
  }

  .persona-card-variant-glass .btn-icon {
    width: 2.1rem;
    height: 2.1rem;
    border-radius: 999px;
    border-color: rgba(148, 163, 184, 0.45);
    background: rgba(15, 23, 42, 0.38);
    color: #e2e8f0;
    backdrop-filter: blur(6px);
  }

  .persona-card-variant-glass .btn-secondary:hover {
    background: rgba(51, 65, 85, 0.42);
    border-color: rgba(125, 211, 252, 0.6);
    color: #e0f2fe;
  }

  .persona-card-variant-glass .btn-danger:hover {
    border-color: rgba(248, 113, 113, 0.65);
  }

  .persona-card-variant-contrast .header-actions {
    gap: 0.3rem;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 999px;
    padding: 0.16rem;
  }

  .persona-card-variant-contrast .btn-icon {
    width: 1.95rem;
    height: 1.95rem;
    border-radius: 999px;
    border-color: transparent;
    color: #a7f3d0;
  }

  .persona-card-variant-contrast .btn-secondary:hover {
    background: rgba(16, 185, 129, 0.25);
    border-color: rgba(16, 185, 129, 0.55);
    color: #ecfdf5;
  }

  .persona-card-variant-contrast .btn-danger {
    color: #fca5a5;
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

  .icon-star {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1em;
    height: 1em;
    line-height: 1;
    transform: translateY(-0.02em);
  }
</style>
