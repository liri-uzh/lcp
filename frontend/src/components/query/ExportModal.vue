<template>
  <div class="export-modal">
    <div class="form-floating mb-3">
      <div class="tab-content" id="nav-exportxml-tabContent">
        <div class="tab-pane fade show active pt-3" id="nav-exportxml" role="tabpanel" aria-labelledby="nav-exportxml-tab">
          <div class="row">
            <label class="col" for="nameExport">Filename:</label>
            <label class="col-2" for="extension">Export as</label>
          </div>
          <div class="row">
            <input
              type="text"
              class="form-control col"
              id="nameExport"
              name="nameExport"
              v-model="localNameExport"
            />
            <select v-if="isSwissdox" class="col-2" v-model="localExportTab">
              <option value="xml">*.xml</option>
              <option value="swissdox">*.swissdox</option>
            </select>
            <span v-else class="col-2" style="margin-top: 0.33em;">
              *.{{ exportTab }}
            </span>
          </div>
          <div class="row" style="margin-top: 1em;">
            <label for="nExport" v-if="!isSwissdox || exportTab == 'xml'">Number of hits:</label>
          </div>
          <div class="row">
            <input
              type="text"
              class="form-control col"
              id="nExport"
              name="nExport"
              v-model="localNExport"
              :style="`margin-right: 1em; visibility: ${isSwissdox && exportTab == 'swissdox' ? 'hidden;' : 'visible'};`"
            />
            <button type="button" @click="$emit('save', exportTab)" class="btn btn-primary me-1 col-2" data-bs-dismiss="modal">
              Download
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "ExportModal",
  props: ["exportTab", "nameExport", "nExport", "isSwissdox"],
  emits: ["save"],
  data() {
    return {
      localExportTab: this.exportTab,
      localNameExport: this.nameExport,
      localNExport: this.nExport
    };
  },
  watch: {
    localExportTab(newVal) {
      this.$emit('update:exportTab', newVal);
    },
    localNameExport(newVal) {
      this.$emit('update:nameExport', newVal);
    },
    localNExport(newVal) {
      this.$emit('update:nExport', newVal);
    }
  }
};
</script>