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

  <LoadingView class="segment-loading" override="1" v-if="!currentDocumentSelected"/>
  <div
    id="viewer-container"
    :class="[minimize ? 'minimized' : '']"
    ref="viewerContainer"
    v-if="corpus && documentLayer && currentDocumentSelected"
  >
    <div class="segments" v-if="allPrepared instanceof Array && allPrepared.length > 0">
      <div
        class="segment"
        v-for="(prep, n) in allPrepared"
        :key="`segment-prepared-${n}`"
        :class="prep._highlight > 0 ? 'highlight' : ''"
      >
        <span
          v-if="Object.keys(meta).length"
          style="margin-right: 0.5em"
          class="icon-info ms-2"
        >
          <FontAwesomeIcon :icon="['fas', 'circle-info']" />
          <div class="segment-info" v-html="metaForSentence(prep._sid, prep._char_range)"></div>
        </span>
        <PlainTokens
          :item="prep"
          :columnHeaders="columnHeaders"
          :currentToken="currentToken"
          :resultIndex="0"
          @showPopover="()=>null"
          @closePopover="()=>null"
        />
        <button
          type="button"
          class="btn btn-secondary btn-sm"
          data-bs-toggle="modal"
          :data-bs-target="`#detailsModalDocViewer${randInt}`"
          @click="showModal(prep)"
        >
          {{ $t('common-details') }}
        </button>
      </div>
    </div>
    <div
      class="modal fade modal-xl"
      :id="`detailsModalDocViewer${randInt}`"
      tabindex="-1"
      aria-labelledby="detailsModalDocViewerLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog modal-full">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="detailsModalDocViewerLabel">{{ $t('common-details') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              :aria-label="$t('common-close')"
            ></button>
          </div>
          <div class="modal-body text-start">
            <div class="modal-body-content">
              <ResultsDetailsModalView
                :data="[currentPrepSentence._sid, currentPrepSentence]"
                :sentences="sentences"
                :sentencesByStream="sentencesByStream"
                :meta="meta"
                :metaByLayer="metaByLayer"
                :corpora="{corpus: corpus}"
                :languages="language ? [language] : []"
                :hideContext="true"
                v-if="modalVisible && currentPrepSentence && currentPrepSentence._sid"
              />
            </div>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useUserStore } from "@/stores/userStore";

import LoadingView from "@/components/LoadingView.vue";
import PlainTokens from "@/components/results/PlainToken.vue";
import ResultsDetailsModalView from "@/components/results/DetailsModalView.vue";

import Utils from "@/utils";

const TokenToDisplay = Utils.TokenToDisplay;

export default {
  name: "PlainDocumentViewer",
  components: {
    PlainTokens,
    LoadingView,
    ResultsDetailsModalView,
  },
  data() {
    return {
      documentId: 0,
      tmpdocumentId: 0,
      currentToken: null,
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
    "meta",
    "metaByLayer",
    "sentences",
    "sentencesByStream",
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
    showModal(prepSentence) {
      this.currentPrepSentence = prepSentence;
      this.modalVisible = true;
    },
    dictToStr(...args) {
      return Utils.dictToStr(...args);
    },
    metaForSentence(sid, char_range) {
      if (!this.meta || !this.meta.layer) return "";
      const segMeta = this.meta.layer[this.corpus.segment];
      if (!segMeta) return "";
      if (!(sid in segMeta.byId)) return "";
      const processedAnnotations = {};
      const annotationsArray = [];
      for (const layer in this.meta.layer) {
        if (layer == this.corpus.document) continue;
        processedAnnotations[layer] = {};
        const layerStream = this.meta.layer[layer].byStream;
        if (!layerStream) continue;
        const annotations = layerStream.searchValue(char_range);
        if (!annotations || !annotations.length) continue;
        for (const annotation of annotations) {
          const aid = annotation._id;
          if (aid) {
            if (aid in processedAnnotations[layer]) continue;
            processedAnnotations[layer][aid] = 1;
          }
          const annotationArray = Object.entries(annotation).filter(
            kv=>!kv[0].startsWith("_") && !["char_range","frame_range","xy_box"].includes(kv[0])
          );
          if (annotationArray.length == 0) continue;
          annotationsArray.push([layer, annotationArray]);
        }
      }
      if (annotationsArray.length == 0) return "";
      const rows = annotationsArray.map(
        ([layer,annotations]) => `
        <tr><td colspan="2" class="layer-name">${layer}</td></tr>
        ${
          annotations.map(
            ([k,v])=>'<tr><td class="attribute-name">'+k+'</td><td>'+v+'</td></tr>'
          ).join('')
        }
      `).join('');
      const ret = `<table>${rows}</table>`;
      return ret;
    }
  },
  computed: {
    ...mapState(useUserStore, ["userData", "roomId"]),
    documentLayer() {
      return this.corpus.document;
    },
    columnHeaders() {
      if (!this.corpus) return [];
      const seg = this.corpus.segment;
      let segMapping = this.corpus.mapping.layer[seg];
      if (!("prepared" in segMapping)) {
        try {
          segMapping = segMapping.partitions[this.language];
        } catch {
          console.error("Could not find the column headers in", segMapping, "for", this.language);
        }
      }
      return segMapping.prepared.columnHeaders;
    },
    allPrepared() {
      if (!this.currentDocumentSelected) return [];
      const char_range = this.currentDocumentSelected.value.char_range;
      if (!(this.corpus.segment in this.meta.layer)) return [];
      const prepared = [];
      const segments = this.meta.layer[this.corpus.segment].byStream.searchValue(char_range);
      for (let segment of segments.sort((a,b)=>a.char_range[0] - b.char_range[0])) {
        if (!(segment._id in this.sentences)) continue;
        const [segOffset, preTokens] = this.sentences[segment._id];
        if (!preTokens) continue
        let groups = [];
        const tokens = preTokens.map((t,i)=>new TokenToDisplay(t, (segOffset||1)+i, groups, this.columnHeaders, {}));
        tokens._highlight = groups.length;
        tokens._sid = segment._id;
        tokens._char_range = segment.char_range;
        prepared.push(tokens);
      }
      return prepared;
    }
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
    meta() {
      if (!this.meta.layer) return;
    },
    currentDocumentSelected() {
      if (!this.currentDocumentSelected || !this.currentDocumentSelected.value) return;
      const docId = this.currentDocumentSelected.value.id;
      const docMeta = this.meta.layer[this.corpus.document];
      if (docMeta && docId in docMeta) return;
      useCorpusStore().fetchAnnotations({
        user: this.userData.user.id,
        room: this.roomId,
        corpus: this.corpus.meta.id,
        anchor: "stream",
        range: this.currentDocumentSelected.value.char_range,
        limit: 500,
        language: this.language
      });
    },
    language() {
      this.currentDocumentSelected = null;
      this.documentOptions = [];
      this.loadDocuments();
    }
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