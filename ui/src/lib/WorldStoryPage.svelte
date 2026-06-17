<script>
  import GalleryPage from './GalleryPage.svelte'

  const tabs = [
    { id: 'world', label: 'World', artifactType: 'world' },
    { id: 'story', label: 'Story', artifactType: 'story' },
  ]
</script>

<GalleryPage
  title="Worlds & Stories"
  {tabs}
  initialTab="world"
  enableCharacterModal={false}
/>
