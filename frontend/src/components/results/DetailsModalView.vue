<template>
  <div id="result-details-view">
    <nav>
      <div class="nav nav-tabs" id="nav-tab" role="tablist">
        <button
          class="nav-link active"
          id="nav-context-tab"
          data-bs-toggle="tab"
          data-bs-target="#nav-context"
          type="button"
          role="tab"
          aria-controls="nav-context"
          aria-selected="true"
          v-if="showContext"
        >
          {{ $t('modal-results-tab-context') }}
        </button>
        <button
          class="nav-link"
          id="nav-dependency-tab"
          data-bs-toggle="tab"
          data-bs-target="#nav-dependency"
          type="button"
          role="tab"
          aria-controls="nav-dependency"
          aria-selected="true"
          v-if="hasDepRel"
        >
          {{ $t('modal-results-tab-graph') }}
        </button>
        <button
          class="nav-link"
          :class="hideContext ? ['active'] : []"
          id="nav-details-tab"
          data-bs-toggle="tab"
          data-bs-target="#nav-details"
          type="button"
          role="tab"
          aria-controls="nav-details"
          aria-selected="false"
        >
          {{ $t('modal-results-tab-tabular') }}
        </button>
      </div>
    </nav>
    <div class="tab-content" id="nav-tabContent">
      <div
        class="tab-pane fade show active"
        id="nav-context"
        role="tabpanel"
        aria-labelledby="nav-dependency-context"
        v-if="showContext"
      >
        <div>
        Context:
        <select v-model="context">
          <option v-for="metaLayer in metaLayers" :value="metaLayer.value" :key="metaLayer.value">{{ metaLayer.text }}</option>
        </select>
        </div>
        <ol>
          <li v-for="(prep, n) in getSentencesInContext(sentencesByStream)" :key="`prep-${n}`">
            <span
              style="margin-right: 0.5em"
              class="icon-info ms-2"
            >
              <FontAwesomeIcon :icon="['fas', 'circle-info']" />
              <!-- <AnnotationDisplay
                :axisPositions="annotationAxisPositions"
                :corpusConfig="corpusConfig"
                :stickyPosition="stickyAnnotations"
                :style="{ top: annotationDisplayPosition.y + 'px', left: annotationDisplayPosition.x + 'px' }"
                @close="closeAnnotations"
              /> -->
            </span>
            <PlainTokens
              :item="prep"
              :columnHeaders="columnHeaders"
              :resultIndex="0"
              @showPopover="()=>null"
              @closePopover="()=>null"
            />
          </li>
        </ol>
      </div>
      <div
        class="tab-pane fade"
        id="nav-dependency"
        role="tabpanel"
        aria-labelledby="nav-dependency-tab"
        v-if="hasDepRel"
      >
        <DepRelView :data="data" :sentence="sentence" :columnHeaders="columnHeaders" />
      </div>
      <div
        class="tab-pane fade"
        :class="hideContext ? ['show','active'] : []"
        id="nav-details"
        role="tabpanel"
        aria-labelledby="nav-details-tab"
      >
        <DetailsTableView :data="data" :sentence="sentence" :columnHeaders="columnHeaders" :corpora="corpora" :isModal="true" />
      </div>
    </div>
  </div>
</template>

<style scoped>
#nav-dependency,
#nav-details {
  overflow: auto;
}
li span .popover-details-table {
  display: none;
  position: absolute;
  background-color: beige;
  padding: 0.25em;
  border-radius: 0.5em;
}
li span:hover .popover-details-table {
  display: block;
}
.popover-details-table tr {
  vertical-align: top;
}
ol li:nth-child(2n) {
  background-color: cornsilk;
}
ol li:nth-child(2n+1) {
  background-color: lavender;
}
</style>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useUserStore } from "@/stores/userStore";
import { useWsStore } from "@/stores/wsStore";
import { useCorpusAnnotationsStore } from '@/stores/corpusAnnotations';

// import AnnotationDisplay from '@/components/AnnotationDisplay.vue';
import DepRelView from "@/components/DepRelView.vue";
import DetailsTableView from "@/components/results/DetailsTableView.vue";
import PlainTokens from "@/components/results/PlainToken.vue";
import Utils from "@/utils.js";

export default {
  name: "ResultsDetailsModalView",
  props: ["data", "languages", "corpora", "hideContext"],
  data() {
    let lang = (this.languages||[])[0];
    let segment = this.corpora.corpus.segment;
    let mapping = this.corpora.corpus.mapping.layer[segment];
    if (lang && "partitions" in mapping) {
      mapping = mapping.partitions[lang]
    }
    let columnHeaders = mapping.prepared.columnHeaders;
    let deprel = Object.values(columnHeaders).indexOf("head") >= 0;
    return {
      context: this.corpora.corpus.firstClass.segment,
      hasDepRel: deprel,
      columnHeaders: columnHeaders,
      annotationsFetched: {},
      showContext: this.hideContext ? false : true
    }
  },
  methods: {
    filterMetaAttrs(attrs) {
      return Object.fromEntries(Object.entries(attrs).filter(kv=>!(kv[0] in {char_range:1,frame_range:1,xy_box:1,_id:1})));
    },
    plainTokens(sentence) {
      const startIndex = sentence.offset;
      const annotations = sentence.annotations;
      const hits = this.data?.hits || [];
      const tokens = sentence.content || [];
      const tokenData = hits.map( tokenIdOrSet => tokenIdOrSet instanceof Array ? tokenIdOrSet : [tokenIdOrSet] );
      // Return a list of TokenToDisplay instances
      return tokens.map( (token,idx) => new Utils.TokenToDisplay(
        token,
        startIndex + idx,
        tokenData || [],
        this.columnHeaders,
        annotations
      ));
    },
    // Pass stream as an argument to update as needed
    getSentencesInContext(stream) {
      let char_range = this.sentence.char_range;
      char_range = [char_range[0] - 2, char_range[1] + 2];
      const meta = this.segmentAnnotations[this.sentenceId] || {};
      if (this.context != this.corpora.corpus.firstClass.segment && this.context in meta) {
        const metaId = meta[this.context];
        const metaAnnotations = this.annotationsByLayer[this.context].byId[metaId];
        char_range = metaAnnotations.char_range || char_range;
      }
      const sentenceIds = stream.search(char_range).sort((x,y)=>x.low - y.low).map(x=>x.value);
      return sentenceIds
        .filter(sid=>sid in this.segments)
        .filter( (sid,i,ar) => i+1>=ar.length || sid != ar[i+1] ) // filter duplicates
        .map( sid => {
          const sentence = this.segments[sid].data;
          const ret = this.plainTokens(sentence);
          ret._char_range = sentence.char_range;
          ret._sid = sid;
          return ret;
        });
    },
  },
  computed: {
    ...mapState(useUserStore, ["userData", "roomId", "debug"]),
    ...mapState(useWsStore, ["messages"]),
    ...mapState(useCorpusAnnotationsStore, ["segments", "sentencesByStream", "segmentAnnotations", "annotationsByLayer"]),
    sentenceId() {
      return this.data.sentenceId;
    },
    // PreparedSegment
    sentence() {
      const sent = this.segments[this.sentenceId];
      return sent?.data;
    },
    metaLayers() {
      if (!(this.sentenceId in this.segmentAnnotations)) return [];
      return Object.keys(this.segmentAnnotations[this.sentenceId]).map(k=>Object({
        text: k == this.corpora.corpus.firstClass.segment ? `${k} (-/+ 1)` : k,
        value: k
      }));
    },
  },
  watch: {
    context() {
      if (this.context == this.corpora.corpus.firstClass.segment) return;
      if (this.sentenceId in this.annotationsFetched && this.context in this.annotationsFetched[this.sentenceId])
        return;
      const meta = this.segmentAnnotations[this.sentenceId] || {};
      if (!(this.context in meta)) return;
      const contextId = meta[this.context][0];
      if (!(this.context in this.annotationsByLayer)) return;
      const contextAnnotations = this.annotationsByLayer[this.context].byId[contextId];
      const char_range = contextAnnotations.char_range;
      this.annotationsFetched[this.sentenceId] = this.annotationsFetched[this.sentenceId] || {};
      this.annotationsFetched[this.sentenceId][this.context] = 1;
      const corpus = this.corpora.corpus.meta.id;
      const data = {
        user: this.userData.user.id,
        room: this.roomId,
        corpus: corpus,
        anchor: "stream",
        range: char_range,
        language: (this.languages || [""])[0]
      };
      useCorpusStore().fetchAnnotations(data);
    },
  },
  components: {
    // AnnotationDisplay,
    DepRelView,
    DetailsTableView,
    PlainTokens
  },
}
</script>
