<script>
  let { message = '', visible = $bindable(false), duration = 3000 } = $props()

  let timer = null
  let startedAt = 0
  let remainingMs = 3000

  function clearTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function startTimer(ms) {
    clearTimer()
    startedAt = Date.now()
    timer = setTimeout(() => {
      visible = false
      timer = null
    }, ms)
  }

  function pauseTimer() {
    if (!timer) return
    const elapsed = Date.now() - startedAt
    remainingMs = Math.max(0, remainingMs - elapsed)
    clearTimer()
  }

  function resumeTimer() {
    if (!visible) return
    if (remainingMs <= 0) {
      visible = false
      return
    }
    startTimer(remainingMs)
  }

  $effect(() => {
    const _message = message
    const _duration = duration
    if (visible) {
      remainingMs = duration
      startTimer(duration)
      return () => clearTimer()
    }
    clearTimer()
  })
</script>

{#if visible}
  <div class="toast" role="status" aria-live="polite" onmouseenter={pauseTimer} onmouseleave={resumeTimer}>{message}</div>
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
