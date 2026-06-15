<script>
  import './styles/cards/index.css'

  // Third-party attribution:
  // Portions of the holo card effect are derived from simeydotme/pokemon-cards-css
  // (GPL-3.0): https://github.com/simeydotme/pokemon-cards-css/tree/acb1197633e749a1fba4412231db2f6581586d00
  // See THIRD_PARTY_NOTICES for project-level notice details.
  let { item, onopen = () => {}, holo = false, variant = null } = $props()

  let cardEl = $state(null)
  let active = $state(false)

  // variant overrides holo boolean
  let effectiveVariant = $derived(variant ?? (holo ? 'holo' : null))

  function setVars(el, px, py) {
    const fromCenter = Math.min(Math.hypot(px - 0.5, py - 0.5) * 2, 1)
    el.style.setProperty('--pointer-x', `${px * 100}%`)
    el.style.setProperty('--pointer-y', `${py * 100}%`)
    el.style.setProperty('--pointer-from-left', `${px}`)
    el.style.setProperty('--pointer-from-top', `${py}`)
    el.style.setProperty('--pointer-from-center', `${fromCenter}`)
    el.style.setProperty('--background-x', `${50 + (px - 0.5) * 50}%`)
    el.style.setProperty('--background-y', `${50 + (py - 0.5) * 50}%`)
    el.style.setProperty('--rotate-x', `${(px - 0.5) * 25}deg`)
    el.style.setProperty('--rotate-y', `${(0.5 - py) * 15}deg`)
    el.style.setProperty('--card-scale', '1.05')
    el.style.setProperty('--card-opacity', '1')
    el.style.setProperty('--translate-x', '0px')
    el.style.setProperty('--translate-y', '-4px')
  }

  function resetVars(el) {
    el.style.setProperty('--pointer-x', '50%')
    el.style.setProperty('--pointer-y', '50%')
    el.style.setProperty('--pointer-from-left', '0.5')
    el.style.setProperty('--pointer-from-top', '0.5')
    el.style.setProperty('--pointer-from-center', '0')
    el.style.setProperty('--background-x', '50%')
    el.style.setProperty('--background-y', '50%')
    el.style.setProperty('--rotate-x', '0deg')
    el.style.setProperty('--rotate-y', '0deg')
    el.style.setProperty('--card-scale', '1')
    el.style.setProperty('--card-opacity', '0')
    el.style.setProperty('--translate-x', '0px')
    el.style.setProperty('--translate-y', '0px')
  }

  function handlePointerEnter(event) {
    if (!cardEl) return
    active = true
    const rect = cardEl.getBoundingClientRect()
    setVars(cardEl, (event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height)
  }

  function handlePointerMove(event) {
    if (!cardEl || !active) return
    const rect = cardEl.getBoundingClientRect()
    setVars(cardEl, (event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height)
  }

  function handlePointerLeave() {
    active = false
    if (!cardEl) return
    resetVars(cardEl)
  }
</script>

<button
  class="card"
  class:holo-enabled={effectiveVariant !== null}
  class:active
  class:holo-variant-holo={effectiveVariant === 'holo'}
  class:holo-variant-reverse-holo={effectiveVariant === 'reverse-holo'}
  class:holo-variant-cosmos-holo={effectiveVariant === 'cosmos-holo'}
  bind:this={cardEl}
  type="button"
  onclick={() => onopen(item.run_id)}
  onpointerenter={handlePointerEnter}
  onpointermove={handlePointerMove}
  onpointerleave={handlePointerLeave}
  aria-label={`Open ${item.title}`}
>
  <div class="card__translater">
    <div class="card__rotator">
      {#if item.avatar_data}
        <img class="card__front" src={item.avatar_data} alt={item.avatar_name || item.title} />
      {:else}
        <div class="card__front card__placeholder">
          <span>{item.avatar_name || item.title}</span>
        </div>
      {/if}
      <div class="card__shine"></div>
      <div class="card__glare"></div>
    </div>
  </div>
  <div class="card__meta">
    <h3>{item.avatar_name || item.title}</h3>
    {#if item.avatar_summary}
      <p class="card__summary">{item.avatar_summary}</p>
    {/if}
    {#if item.tags?.length}
      <p class="card__tags">{item.tags.map((t) => `#${t}`).join(' ')}</p>
    {/if}
  </div>
</button>
