<template>
  <div class="plain-table">
    <PaginationComponent
      v-if="data"
      class="pagination"
      :resultCount="data.length"
      :resultsPerPage="resultsPerPage"
      :currentPage="currentPage"
      @update="updatePage"
      :key="data.length"
      :loading="loading"
    />

    <SegmentTable
      :preparedRanges="preparedRangesCurrentPage"
      :languages="languages"
      :corpora="corpora"
      @playMedia="playMedia"
      @showImage="showImage"
      :resultsPerPage="resultsPerPage"
      :loading="loading"
    />

    <PaginationComponent
      v-if="data"
      class="pagination"
      :resultCount="data.length"
      :resultsPerPage="resultsPerPage"
      :currentPage="currentPage"
      @update="updatePage"
      :key="data.length"
      :loading="loading"
    />
  </div>
</template>

<script>
import PaginationComponent from '@/components/PaginationComponent.vue';
import SegmentTable from '@/components/SegmentTable.vue';
import { useNotificationStore } from '@/stores/notificationStore';
import Utils from '@/utils.js';
import { DataLine } from '@/classes/WSDataResults.js';

const SEGMENT_WINDOW = 2; // number of +/- characters to retrieve the surrounding sentences

export default {
  name: 'PlainTableView',
  components: {
    SegmentTable,
    PaginationComponent,
  },
  emits: ['updatePage', 'playMedia', 'showImage'],
  props: [
    'data',
    'languages',
    'attributes',
    'corpora',
    'resultsPerPage',
    'loading'
  ],
  data() {

    return {
      popoverY: 0,
      popoverX: 0,
      currentToken: null,
      currentResultIndex: null,
      showingAnnotations: false,
      annotationAxisPositions: [],
      annotationDisplayPosition: { x: 0, y: 0 },
      stickyAnnotations: { x: null, y: null },
      modalVisible: false,
      modalIndex: null,
      currentPage: 1,
      randInt: Math.floor(Math.random() * 1000),
      playIndex: -1,
      selectedLine: -1,
      selectedPage: -1,
      detachSelectedLine: false
    };
  },
  computed: {
    corpusConfig() {
      return this.corpora?.corpus || {};
    },
    segmentWindow() {
      return SEGMENT_WINDOW;
    },
    resultsCurrentPage() {
      let start = this.resultsPerPage * (this.currentPage - 1);
      let end = start + this.resultsPerPage;
      return this.data
        .slice(start, end)
        .map( (row, rowIndex) => new DataLine(row, rowIndex) );
    },
    preparedRangesCurrentPage() {
      return this.resultsCurrentPage.map(dl=>[dl.char_range.join(','),dl]);
    }
  },
  methods: {

    updatePage(currentPage) {
      this.currentPage = currentPage;
      this.$emit('updatePage', this.currentPage);
    },

    playMedia(data) {
      this.$emit('playMedia', data);
    },

    copyToClip(item) {
      Utils.copyToClip(item);
      useNotificationStore().add({
        type: 'success',
        text: 'Copied to clipboard'
      });
    },

    strPopover(attribute) {
      if (attribute && attribute.constructor.name === 'Object') {
        return Utils.dictToStr(attribute);
      } else {
        return attribute;
      }
    },

    showImage(image) {
      this.$emit("showImage", image);
    }

  }
};
</script>

<style scoped>
tr.selected {
  outline: solid 2px green;
}

tr.detached {
  position: fixed;
  bottom: 1em;
  z-index: 99;
  left: 2.5vw;
  width: 95vw;
  box-shadow: 0px 0px 14px 0px black;
}

td.results div:nth-child(2n) {
  background-color: cornsilk;
}

td.results div:nth-child(2n+1) {
  background-color: lavender;
}

div.unpin {
  position: absolute;
  right: 0;
  top: 0;
  transform: translate(2px, -100%);
  background-color: white;
  border-top: solid 2px green;
  border-right: solid 2px green;
  border-left: solid 2px green;
  border-radius: 0.1em;
}

td.buttons {
  min-width: 100px;
}

td.results {
  width: 100%;
}

span.timetag {
  display: inline-block;
  white-space: wrap;
  width: 5em;
  text-align: center;
  font-size: 0.8em;
  background: beige;
  box-shadow: 0px 0px 3px black;
  border-radius: 0.25em;
  margin-right: 0.5em;
  transform: translateY(0.25em);
}

span.timetag.nowrap {
  width: unset;
  white-space: nowrap;
  transform: translateY(-0.25em);
}

span.action-button {
  cursor: pointer;
  margin-right: 0.5em;
  color: #fff;
  transition: 0.3s all;
  background-color: #2a7f62;
  display: inline-block;
  width: 28px;
  text-align: center;
  padding: 2px;
  border-radius: 5px;
}

span.action-button:hover {
  opacity: 0.7;
}

.icon-info {
  cursor: pointer;
  color: #676767;
}

.pagination {
  float: right;
}

.pagination:after {
  clear: both;
  content: '';
}

.popover-table th {
  text-transform: uppercase;
  font-size: 10px;
}

.popover-table {
  margin-bottom: 0;
  padding: 5px;
}

.popover-liri {
  position: fixed;
  background: #cfcfcf;
  padding: 7px;
  border: #cbcbcb 1px solid;
  border-radius: 5px;
  z-index: 200;
}

.match-context {
  white-space: nowrap;
  text-align: center;
}

.token {
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
  margin-right: -2px;
}

.highlight {
  background-color: #1e999967 !important;
  color: #000 !important;
}

.popover-liri .popover-table td {
  max-width: 50vw;
}

.popover-liri .popover-table td:nth-child(2) {
  width: 100%;
  padding-left: 0.5em;
}

*[class^='color-group-'] {
  border-radius: 2px;
}

.audioplayer {
  display: none;
  position: absolute;
  width: 50vw;
  right: 10em;
  height: 32px;
  padding: 0px;
}

.audioplayer.visible {
  display: block;
}
</style>