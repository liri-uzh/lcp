<template>
  <div class="corpus-graph-modal">
    <div class="row">
      <p class="title mb-0">{{ corpus.meta.name }}</p>
      <CorpusGraphViewNew :corpus="corpus" />
    </div>
  </div>
</template>

<script>
import CorpusGraphViewNew from "@/components/CorpusGraphViewNew.vue";

export default {
  name: "CorpusGraphModal",
  props: ["corpus"],
  components: {
    CorpusGraphViewNew
  }
};
</script>