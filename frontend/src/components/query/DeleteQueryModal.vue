<template>
  <div class="delete-query-modal">
    <p>{{ $t('common-delete-query-sure') }}</p>
  </div>
</template>

<script>
export default {
  name: "DeleteQueryModal",
  emits: ["delete"],
  methods: {
    confirmDelete() {
      this.$emit('delete');
    }
  }
};
</script>