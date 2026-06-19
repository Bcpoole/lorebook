<script>
  import GalleryPage from "./GalleryPage.svelte";

  const tabs = [
    { id: "world", label: "World", artifactType: "world" },
    { id: "story", label: "Story", artifactType: "story" },
  ];
</script>

<GalleryPage
  title="Lore"
  {tabs}
  initialTab="world"
  enableCharacterModal={false}
/>
