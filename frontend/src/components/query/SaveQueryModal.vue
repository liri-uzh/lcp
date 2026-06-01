<template>
  <div class="save-query-modal">
    <label for="queryName" class="form-label">{{ $t('common-query-name') }}</label>
    <input type="text" class="form-control" id="queryName" v-model="queryName" />
  </div>
</template>

<script>
export default {
  name: "SaveQueryModal",
  props: ["initialQueryName"],
  emits: ["update"],
  data() {
    return {
      queryName: this.initialQueryName || ""
    };
  },
  watch: {
    queryName(newVal) {
      this.$emit('update', newVal.length > 0, { queryName: newVal });
    }
  }
};
</script>