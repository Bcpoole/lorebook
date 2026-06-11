<script>
  let { message = '', visible = $bindable(false), duration = 3000 } = $props()

  $effect(() => {
    if (visible) {
      const timer = setTimeout(() => { visible = false }, duration)
      return () => clearTimeout(timer)
    }
  })
</script>

{#if visible}
  <div class="toast">{message}</div>
{/if}

<style>
  .toast {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    background: #1e293b;
    color: #f1f5f9;
    padding: 0.75rem 1.25rem;
    border-radius: 8px;
    font-size: 0.9rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    z-index: 100;
    animation: slide-in 0.2s ease;
  }

  @keyframes slide-in {
    from {
      transform: translateY(0.5rem);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
</style>
