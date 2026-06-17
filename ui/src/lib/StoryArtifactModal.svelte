<script>
  import LocationEditItem from './LocationEditItem.svelte'
  import ObjectEditItem from './ObjectEditItem.svelte'

  let {
    storyArtifact,
    storyId,
    onClose = () => {},
    onUpdate = () => {},
  } = $props()

  let expandedSections = $state({
    locations: false,
    objects: false,
    characters: false,
  })

  function toggleSection(section) {
    expandedSections[section] = !expandedSections[section]
  }

  function handleLocationSave(result) {
    onUpdate?.(result)
  }

  function handleObjectSave(result) {
    onUpdate?.(result)
  }
</script>

<div class="story-modal">
  <button class="modal-close" on:click={onClose} title="Close">✕</button>

  <div class="story-content">
    <h2>{storyArtifact.title || 'Untitled Story'}</h2>

    {#if storyArtifact.description}
      <div class="story-section">
        <p class="description">{storyArtifact.description}</p>
      </div>
    {/if}

    {#if storyArtifact.setting}
      <div class="story-section">
        <h3>Setting</h3>
        <p>{storyArtifact.setting}</p>
      </div>
    {/if}

    {#if storyArtifact.plot && Array.isArray(storyArtifact.plot) && storyArtifact.plot.length > 0}
      <div class="story-section">
        <h3>Plot</h3>
        <ol class="plot-list">
          {#each storyArtifact.plot as point}
            <li>{point}</li>
          {/each}
        </ol>
      </div>
    {/if}

    <!-- Locations (Expandable) -->
    {#if Array.isArray(storyArtifact.locations) && storyArtifact.locations.length > 0}
      <div class="story-section expandable">
        <button
          class="section-toggle"
          on:click={() => toggleSection('locations')}
          type="button"
        >
          <span class="toggle-icon">{expandedSections.locations ? '▼' : '▶'}</span>
          📍 Locations ({storyArtifact.locations.length})
        </button>

        {#if expandedSections.locations}
          <div class="section-content">
            {#each storyArtifact.locations as location, i}
              <LocationEditItem
                location={location}
                storyId={storyId}
                locationIndex={i}
                onSave={handleLocationSave}
              />
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Objects (Expandable) -->
    {#if Array.isArray(storyArtifact.objects) && storyArtifact.objects.length > 0}
      <div class="story-section expandable">
        <button
          class="section-toggle"
          on:click={() => toggleSection('objects')}
          type="button"
        >
          <span class="toggle-icon">{expandedSections.objects ? '▼' : '▶'}</span>
          🔧 Objects ({storyArtifact.objects.length})
        </button>

        {#if expandedSections.objects}
          <div class="section-content">
            {#each storyArtifact.objects as obj, i}
              <ObjectEditItem
                object={obj}
                storyId={storyId}
                objectIndex={i}
                onSave={handleObjectSave}
              />
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Characters (Expandable) -->
    {#if Array.isArray(storyArtifact.characters_artifact) && storyArtifact.characters_artifact.length > 0}
      <div class="story-section expandable">
        <button
          class="section-toggle"
          on:click={() => toggleSection('characters')}
          type="button"
        >
          <span class="toggle-icon">{expandedSections.characters ? '▼' : '▶'}</span>
          👥 Characters ({storyArtifact.characters_artifact.length})
        </button>

        {#if expandedSections.characters}
          <div class="section-content">
            {#each storyArtifact.characters_artifact as character, i}
              <div class="character-item">
                <h4>{character.name || `Character ${i + 1}`}</h4>
                {#if character.summary}
                  <p>{character.summary}</p>
                {/if}
                {#if character.details}
                  <p>{character.details}</p>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <div class="story-actions">
    <button class="close-btn" on:click={onClose}>Close</button>
  </div>
</div>

<style>
  .story-modal {
    position: relative;
    background: white;
    border-radius: 8px;
    padding: 2rem;
    max-height: 85vh;
    overflow-y: auto;
    display: grid;
    gap: 2rem;
    grid-template-rows: 1fr auto;
  }

  .modal-close {
    position: absolute;
    top: 1rem;
    right: 1rem;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 1.5rem;
    padding: 0;
    opacity: 0.6;
    transition: opacity 0.2s;
    z-index: 10;
  }

  .modal-close:hover {
    opacity: 1;
  }

  .story-content {
    display: grid;
    gap: 1.5rem;
  }

  h2 {
    margin: 0;
    font-size: 1.75rem;
    color: #1e293b;
  }

  h3 {
    margin: 0;
    font-size: 1.1rem;
    color: #1e293b;
  }

  h4 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
    color: #1e293b;
  }

  .story-section {
    display: grid;
    gap: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #e2e8f0;
  }

  .story-section:last-of-type {
    border-bottom: none;
  }

  .description {
    color: #475569;
    line-height: 1.6;
    margin: 0;
  }

  p {
    color: #475569;
    line-height: 1.6;
    margin: 0;
  }

  .plot-list {
    margin: 0;
    padding-left: 1.5rem;
    color: #475569;
  }

  .plot-list li {
    margin-bottom: 0.5rem;
  }

  .expandable .section-toggle {
    background: transparent;
    border: none;
    padding: 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: #1e293b;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    transition: color 0.2s;
  }

  .expandable .section-toggle:hover {
    color: #2563eb;
  }

  .toggle-icon {
    display: inline-block;
    width: 1rem;
    text-align: center;
  }

  .section-content {
    display: grid;
    gap: 1rem;
    margin-top: 1rem;
  }

  .character-item {
    padding: 1rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
  }

  .character-item p {
    margin: 0.5rem 0 0 0;
  }

  .story-actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
  }

  .close-btn {
    padding: 0.75rem 1.5rem;
    background: #2563eb;
    color: white;
    border: 1px solid #2563eb;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }

  .close-btn:hover {
    background: #1d4ed8;
  }
</style>
