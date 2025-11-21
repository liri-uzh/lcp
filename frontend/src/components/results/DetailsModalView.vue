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
      >
        <div>
        Context:
        <select v-model="context">
          <option v-for="metaLayer in metaLayers" :value="metaLayer.value" :key="metaLayer.value">{{ metaLayer.text }}</option>
        </select>
        </div>
        <ol>
          <li v-for="(prep, n) in sentencesInContext" :key="`prep-${n}`">
            <span
              v-if="Object.keys(meta).length"
              style="margin-right: 0.5em"
              class="icon-info ms-2"
            >
              <FontAwesomeIcon :icon="['fas', 'circle-info']" />
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
        <DepRelView :data="data" :sentences="sentence" :columnHeaders="columnHeaders" />
      </div>
      <div
        class="tab-pane fade"
        id="nav-details"
        role="tabpanel"
        aria-labelledby="nav-details-tab  "
      >
        <DetailsTableView :data="data" :sentences="sentence" :columnHeaders="columnHeaders" :corpora="corpora" :isModal="true" />
      </div>
    </div>
  </div>
</template>

<style scoped>
#nav-dependency,
#nav-details {
  overflow: auto;
}
</style>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useUserStore } from "@/stores/userStore";
import { useWsStore } from "@/stores/wsStore";


import DepRelView from "@/components/DepRelView.vue";
import DetailsTableView from "@/components/results/DetailsTableView.vue";
import PlainTokens from "@/components/results/PlainToken.vue";
import Utils from "@/utils.js";

export default {
  name: "ResultsDetailsModalView",
  props: ["data", "sentences", "sentencesByStream", "meta", "languages", "corpora"],
  data() {
    let lang = (this.languages||[])[0];
    let segment = this.corpora.corpus.segment;
    let mapping = this.corpora.corpus.mapping.layer[segment];
    if (lang && "partitions" in mapping) {
      mapping = mapping.partitions[lang]
    }
    let columnHeaders = mapping.prepared.columnHeaders;
    let deprel = Object.values(columnHeaders).indexOf("head") >= 0;
    console.log(
      "data",
      JSON.parse(JSON.stringify(this.data)),
      JSON.parse(JSON.stringify(this.sentences)),
      JSON.parse(JSON.stringify(this.meta)),
      JSON.parse(JSON.stringify(this.corpora))
    );
    return {
      context: this.corpora.corpus.firstClass.segment,
      hasDepRel: deprel,
      columnHeaders: columnHeaders,
      metaPerLayer: {}
    }
  },
  methods: {
    plainTokens(sentence) {
      const [startIndex, tokens, annotations, char_range] = sentence;
      console.log("char_range", char_range);

      let tokenData = JSON.parse(JSON.stringify(this.data[1]));
      tokenData = tokenData.map( tokenIdOrSet => tokenIdOrSet instanceof Array ? tokenIdOrSet : [tokenIdOrSet] );
      // Return a list of TokenToDisplay instances
      return tokens.map( (token,idx) => new Utils.TokenToDisplay(token, startIndex + idx, tokenData, this.columnHeaders, annotations) );
    }
  },
  computed: {
    ...mapState(useUserStore, ["userData", "roomId", "debug"]),
    ...mapState(useWsStore, ["messages"]),
    sentenceId() {
      return this.data[0];
    },
    sentence() {
      return this.sentences[this.sentenceId] || [];
    },
    metaLayers() {
      if (!(this.sentenceId in this.meta)) return [];
      return Object.keys(this.meta[this.sentenceId]).map(k=>Object({
        text: k == this.corpora.corpus.firstClass.segment ? `${k} (-/+ 1)` : k,
        value: k
      }));
    },
    sentencesInContext() {
      let char_range = this.sentence.at(-1);
      char_range = [char_range[0] - 2, char_range[1] + 2];
      if (this.context != this.corpora.corpus.firstClass.segment && this.context in (this.meta[this.sentenceId] || {}))
        char_range = this.meta[this.sentenceId][this.context].char_range;
      const sentenceIds = this.sentencesByStream.searchValue([char_range[0] - 2, char_range[1] + 2]);
      console.log("sentenceIds", sentenceIds);
      return sentenceIds.filter(sid=>sid in this.sentences).map(sid=>this.plainTokens(this.sentences[sid]));
    },
  },
  watch: {
    context() {
      console.log("context", this.context, this.metaPerLayer);
      if (this.context == this.corpora.corpus.firstClass.segment) return;
      if (this.context in this.metaPerLayer) return;
      if (!(this.context in (this.meta[this.sentenceId] || {}))) return;
      const char_range = this.meta[this.sentenceId][this.context].char_range;
      this.metaPerLayer[this.context] = true;
      const corpus = this.corpora.corpus.meta.id;
      console.log("corpus", corpus);
      const data = {
        user: this.userData.user.id,
        room: this.roomId,
        corpus: corpus,
        anchor: "stream",
        range: char_range
      };
      useCorpusStore().fetchAnnotations(data);
    },
    messages: {
      handler() {
        console.log("sentences by stream", this.sentencesByStream);
        const ctx = this.context;
        this.context = this.corpora.corpus.firstClass.segment;
        setTimeout(() => this.context = ctx, 1); // force a refresh
      },
      immediate: true,
      deep: true,
    },
  },
  components: {
    DepRelView,
    DetailsTableView,
    PlainTokens
  },
}
</script>
