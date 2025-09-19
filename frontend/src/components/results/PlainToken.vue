<template>
    <span
        v-for="(token) in item"
        :key="`form-${token.index}`"
        @mousemove="$emit('showPopover', token, resultIndex, $event)"
        @mouseleave="$emit('closePopover')"
    >
        <span class="token" :class="[
        (currentToken && columnHeaders && currentToken[columnHeaders.indexOf('head')] == token.index ? 'highlight' : ''),
        (token.group >= 0 ? `text-bold color-group-${token.group}` : '')
        ]">{{ token.form }}</span>
        <span class="space" v-if="token.spaceAfter !== 0">&nbsp;</span>
    </span>
</template>

<style scoped>
.token {
  /* padding-left: 2px;
  padding-right: 2px; */
  display: inline-block;
  transition: 0.3s all;
  border-radius: 2px;
}
.token:hover {
  background-color: #2a7f62;
  color: #fff;
  cursor: pointer;
}
.token.nospace {
  padding-right: 0px;
  margin-right: -2px; /* compensate for next token's padding-left */
}
.highlight {
  background-color: #1e999967 !important;
  color: #000 !important;
}
</style>

<script>
export default {
  name: "PlainToken",
  emits: ["showPopover", "closePopover"],
  props: [
    "item",
    "columnHeaders",
    "currentToken",
    "resultIndex"
  ],
  data() {
    return {};
  },
  components: {
  },
  methods: {
  },
  computed: {
  },
};
</script>
