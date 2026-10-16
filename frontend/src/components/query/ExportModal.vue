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
            <select  class="col-2" v-model="localExportTab">
              <option value="xml">*.xml</option>
              <option value="csv">*.csv</option>
              <option v-if="isSwissdox" value="swissdox">*.swissdox</option>
            </select>
          </div>
          <div class="row" style="margin-top: 1em;" v-if="showInclude">
            <div>Include supra-{{ corpus.segment }} annotations in KWICs:</div>
            <div v-for="(lattrs, lname) in layerAttrs" :key="`include_${lname}`">
              <input type="checkbox" :id="`include_${lname}`" :value="`${lname}`" v-model="this.includeLayers"  @change="updateInclude"/>
              <label :for="`include_${lname}`"><strong>{{ lname  }}</strong></label>
              <div v-if="includeLayers.includes(lname) && layerAttrs[lname].length > 1">
                <span v-for="(aname, n) in lattrs" :key="`include_${lname}_${n}`">
                  <input type="checkbox" :id="`include_${lname}_${n}`" :value="`${aname}`" v-model="this.includeAttributes[lname]" @change="updateInclude"/>
                  <label :for="`include_${lname}_${n}`" style="margin-right: 1em;">{{ aname  }}</label>
                </span>
              </div>
            </div>
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
import Utils from "@/utils";

export default {
  name: "ExportModal",
  props: ["exportTab", "nameExport", "nExport", "isSwissdox", "query", "corpus"],
  emits: ["save", "update"],
  data() {
    return {
      localExportTab: this.exportTab,
      localNameExport: this.nameExport,
      localNExport: this.nExport,
      includeLayers: [],
      // start with all the attributes checked by default
      includeAttributes: Object.fromEntries(
        Object.keys(this.corpus.layer)
          .map((lname)=>[
            lname,
            Object.keys(this.corpus.layer[lname].attributes || {})
          ])
      )
    };
  },
  methods: {
    updateInclude() {
      const includeToSend = {};
      for (const lname of this.includeLayers) {
        const checkedAttrs = this.includeAttributes[lname];
        const allAttrs = Object.keys(this.corpus.layer[lname].attributes || {});
        // pass an empty array if selecting all the attributes
        includeToSend[lname] = allAttrs.some(x=>!checkedAttrs.includes(x)) ? checkedAttrs : [];
      }
      this.$emit('update', 'include', includeToSend);
    }
  },
  computed: {
    showInclude() {
      const query = JSON.parse(this.query || "{}");
      const results = query.results || [];
      return this.localExportTab == "csv" && results.some(x=>"resultsPlain" in x);
    },
    layerAttrs() {
      return Object.fromEntries(
        Object.keys(this.corpus.layer)
          .filter(lname=>Utils.contains(lname, this.corpus.token, this.corpus.layer))
          .sort((l1,l2)=>Utils.contains(l1,l2,this.corpus.layer) ? -1 : 1)
          .map(lname=>[lname, Object.keys(this.corpus.layer[lname].attributes || {})])
      );
    }
  },
  watch: {
    localExportTab(newVal) {
      this.$emit('update', 'exportTab', newVal);
    },
    localNameExport(newVal) {
      this.$emit('update', 'nameExport', newVal);
    },
    localNExport(newVal) {
      this.$emit('update', 'nExport', newVal);
    }
  }
};
</script>