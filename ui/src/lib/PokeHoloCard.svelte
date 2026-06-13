<script>
  // Local holo effect inspired by https://github.com/simeydotme/pokemon-cards-css.
  let { item, onopen = () => {} } = $props()

  let cardEl = $state(null)

  function handlePointerMove(event) {
    if (!cardEl) return
    const rect = cardEl.getBoundingClientRect()
    const x = ((event.clientX - rect.left) / rect.width) * 100
    const y = ((event.clientY - rect.top) / rect.height) * 100
    cardEl.style.setProperty('--mx', `${x}%`)
    cardEl.style.setProperty('--my', `${y}%`)
  }

  function resetPointer() {
    if (!cardEl) return
    cardEl.style.setProperty('--mx', '50%')
    cardEl.style.setProperty('--my', '50%')
  }
</script>

<button
  class="holo-card"
  bind:this={cardEl}
  type="button"
  onclick={() => onopen(item.run_id)}
  onmousemove={handlePointerMove}
  onmouseleave={resetPointer}
  aria-label={`Open ${item.title}`}
>
  <div class="holo-mask"></div>
  {#if item.avatar_data}
    <img src={item.avatar_data} alt={item.avatar_name || item.title} />
  {:else}
    <div class="placeholder">No Avatar</div>
  {/if}
  <h3>{item.title}</h3>
  <p>{item.description}</p>
  {#if item.tags?.length}
    <p class="tags">{item.tags.join(', ')}</p>
  {/if}
</button>

<style>
  .holo-card {
    --mx: 50%;
    --my: 50%;
    position: relative;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 0.55rem;
    background: linear-gradient(155deg, #ffffff, #eef6ff);
    cursor: pointer;
    text-align: left;
    overflow: hidden;
    isolation: isolate;
    transform: perspective(900px) rotateX(0deg) rotateY(0deg);
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
  }

  .holo-card:hover {
    border-color: #7dd3fc;
    box-shadow: 0 14px 24px rgba(14, 165, 233, 0.22);
    transform: perspective(900px) rotateX(2deg) rotateY(-2deg) translateY(-1px);
  }

  .holo-mask {
    position: absolute;
    inset: -20%;
    background:
      radial-gradient(circle at var(--mx) var(--my), rgba(255, 255, 255, 0.6), transparent 28%),
      repeating-linear-gradient(120deg, rgba(56, 189, 248, 0.14) 0px, rgba(167, 139, 250, 0.14) 10px, rgba(244, 114, 182, 0.14) 20px);
    mix-blend-mode: screen;
    opacity: 0.8;
    pointer-events: none;
    z-index: 1;
  }

  img {
    width: 100%;
    aspect-ratio: 1 / 1;
    object-fit: cover;
    border-radius: 10px;
    border: 1px solid #dbeafe;
    background: #fff;
  }

  h3,
  p,
  .tags,
  img,
  .placeholder {
    position: relative;
    z-index: 2;
  }

  .placeholder {
    width: 100%;
    aspect-ratio: 1 / 1;
    border: 1px dashed #94a3b8;
    border-radius: 8px;
    display: grid;
    place-items: center;
    color: #64748b;
    background: #f8fafc;
  }

  h3 {
    margin: 0.45rem 0 0.25rem;
    color: #0f172a;
    font-size: 0.95rem;
  }

  p {
    margin: 0;
    color: #334155;
    font-size: 0.82rem;
    line-height: 1.3;
  }

  .tags {
    margin-top: 0.35rem;
    color: #0369a1;
    font-size: 0.76rem;
  }
</style>
