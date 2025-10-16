<template>
  <div id="title-view">
    <h2 v-html="title" :class="isItalic ? 'italic' : ''"></h2>
    <slot></slot>
  </div>
</template>

<script>
export default {
  name: "TitleView",
  props: ["title", "isItalic"],
}
</script>
<style>
.italic {
  font-style: italic;
}
</style>
