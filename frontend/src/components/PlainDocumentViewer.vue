<template>
  <div class="container-fuild">
    <div class="row" v-if="corpus">
      <div class="col-12 col-md-3">
        <div class="mb-3 mt-3">
          <!-- <label class="form-label">Document</label> -->
          <multiselect
            v-model="currentDocumentSelected"
            :options="documentOptions"
            :multiple="false"
            label="name"
            :placeholder="$t('common-select-document')"
            track-by="value"
          ></multiselect>
        </div>
      </div>
      <div v-if="currentDocumentSelected && meta.layer && meta.layer[corpus.document]" class="doc-info">
        <div v-html="dictToStr(meta.layer[corpus.document].byId[currentDocumentSelected.value.id], {addTitles: true})"></div>
      </div>
      <div class="col-12 col-md-4">
        <div class="mb-3 mt-3 text-center text-md-start">
          <button type="button" class="btn btn-primary" @click="$emit('switchToQueryTab')">{{ $t('common-query-corpus') }}</button>
        </div>
      </div>
    </div>
  </div>

  <LoadingView class="segment-loading" override="1" v-if="!currentDocumentSelected || !preparedRanges"/>
  <div
    id="viewer-container"
    :class="[minimize ? 'minimized' : '']"
    ref="viewerContainer"
    v-if="corpus && documentLayer && currentDocumentSelected && preparedRanges"
  >
    <SegmentTable
      :preparedRanges="preparedRanges"
      :languages="language"
      :corpora="{corpus: corpus}"
      :resultsPerPage="0"
      :details="'perSegment'"
      :hideContext="true"
    />
  </div>
</template>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useUserStore } from "@/stores/userStore";
import { useCorpusAnnotationsStore } from "@/stores/corpusAnnotations";

import LoadingView from "@/components/LoadingView.vue";
import SegmentTable from "@/components/SegmentTable.vue";

export default {
  name: "PlainDocumentViewer",
  components: {
    LoadingView,
    SegmentTable,
  },
  data() {
    const corpusAnnotations = useCorpusAnnotationsStore();
    corpusAnnotations.events.addEventListener("data", ()=> this.setPreparedRanges());
    return {
      preparedRanges: null,
      documentId: 0,
      tmpdocumentId: 0,
      currentDocumentSelected: null,
      documentOptions: [],
      annotationVisibility: {},
      randInt: Math.floor(Math.random() * 1000), // for modal
      modalVisible: false,
      currentPrepSentence: null
    }
  },
  props: [
    "name",
    "corpus",
    "documentIds",
    "minimize",
    "language"
  ],
  emits: ["getSegmentAnnotations", "switchToQueryTab"],
  methods: {
    getAnnotationName(layer, n, attributes) {
      if (attributes.form) return attributes.form;
      let name = layer;
      if (n!==null) name += " " + String(n + 1);
      return name;
    },
    loadDocuments() {
      useCorpusStore().fetchDocuments({
        room: this.roomId,
        user: this.userData.user.id,
        corpora_id: this.corpus.meta.id,
        kind: "plain",
        language: this.language
      });
    },
    setPreparedRanges() {
      if (!this.currentDocumentSelected?.value?.char_range) return;
      const char_range_str = this.currentDocumentSelected.value.char_range.join(",");
      this.preparedRanges = [[char_range_str, null]];
    }
  },
  computed: {
    ...mapState(useUserStore, ["userData", "roomId"]),
    ...mapState(useCorpusAnnotationsStore, {
      meta: "annotationsByLayer",
      events: "events",
    }),
    documentLayer() {
      return this.corpus.document;
    },
  },
  watch: {
    documentId() {
      // automatically resize and reposition segment here
      if (!this.currentDocumentSelected) return;
    },
    documentIds() {
      this.documentOptions = Object.entries(this.documentIds)
        .reduce((acc,[id, info])=>{
          try {
            let [char_start, char_end] = JSON.parse(info.char_range.replace(")","]"));
            const docObj = {
              name: info.name || (this.corpus.document + " " + id),
              value: {id: id, char_range: [char_start, char_end-1]}
            };
            acc.push(docObj);
          } catch (e) {
            console.error("Error processing document", id, e);
            // skip entry
          }
          return acc;
        }, []);
      if (!this.currentDocumentSelected)
        this.currentDocumentSelected = this.documentOptions[0];
    },
    currentDocumentSelected() {
      this.preparedRanges = null;
      if (!this.currentDocumentSelected || !this.currentDocumentSelected.value) return;
      const docId = this.currentDocumentSelected.value.id;
      const metaLayer = this.meta.layer || {};
      const docMeta = metaLayer[this.corpus.document];
      if (docMeta && docId in docMeta)
        return this.setPreparedRanges();
      useCorpusStore().fetchAnnotations({
        user: this.userData.user.id,
        room: this.roomId,
        corpus: this.corpus.meta.id,
        anchor: "stream",
        range: this.currentDocumentSelected.value.char_range,
        limit: 1000, // limit lines to 1000 to spare memory load
        language: this.language
      });
    },
    language() {
      this.currentDocumentSelected = null;
      this.documentOptions = [];
      this.loadDocuments();
    },
  },
  mounted() {
    this.loadDocuments();
  },
  beforeUnmount() {
    // pass
  }
};
</script>

<style>
.doc-info {
  position: relative;
  z-index: 99;
  width: 20vw;
  height: 4em;
  overflow: hidden;
  margin-top: 0.5em;
  padding: 0em;
  box-shadow: 0px 0px 10px lightgray;
  border-radius: 0.5em;
}
.doc-info::before {
  content: "info";
  position: absolute;
  right: 0;
  top: -0.25em;
  font-size: 0.75em;
  font-weight: bold;
}
.doc-info:hover {
  overflow: visible;
  box-shadow: unset;
  border-radius: 0em;
}
.doc-info > div {
  background-color: ivory;
  padding: 0.25em;
  box-shadow: 0px 0px 10px black;
  border-radius: 0.5em;
}

.segment-loading {
  position: absolute;
  top: 0;
  left: 0;
  width: 5em;
  height: 5em;
}
.segments {
  overflow-y: scroll;
  display: flex;
  flex-direction: column;
}
.segment.highlight {
  border: solid 2px green;
}
.segment .segment-info {
  display: none;
  position: absolute;
  background-color: beige;
  margin-top: -0.5em;
}
.segment .icon-info:hover .segment-info {
  display: block;
}
.segment .layer-name {
  font-weight: bold;
}
.segment .attribute-name {
  font-style: italic;
}

#prev-segment, #next-segment {
  position: absolute;
  height: 100%;
  z-index: 100;
  width: 2em;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}
#next-segment {
  right: 0;
}
#prev-segment:hover, #next-segment:hover {
  background-color: #9993;
  cursor: pointer;
}
#viewer-container {
  width: 100%;
  height: 50vh;
  position: relative;
  overflow: hidden scroll;
  resize: vertical;
}
#viewer-container.minimized {
  height: 4em;
}
</style>