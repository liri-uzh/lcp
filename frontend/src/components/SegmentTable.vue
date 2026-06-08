<template>
  <table class="table" v-if="preparedRanges && Object.keys(preparedRanges).length > 0">
    <tbody>
      <tr
        v-for="([segments, document, dataLine], segmentsIndex) in preparedSegments"
        :key="`tr-segments-${segmentsIndex}`"
        :data-index="segmentsIndex"
        :class="
          dataLine?.id === this.selectedLine
          ? `selected ${this.detachSelectedLine ? 'detached' : ''}`
          : ''
        "
        @click="selectLine(dataLine, this.detachSelectedLine)"
      >
        <td scope="row" class="results">
          <div
            v-if="dataLine?.id === this.selectedLine && this.detachSelectedLine"
            class="unpin"
            @click="selectLine(dataLine, false)"
          >
            <FontAwesomeIcon :icon="['fas', 'thumb-tack']" />
            Unpin
          </div>
          
          <span
            v-if="!hideCopy && false"
            :title="$t('common-copy-clipboard')"
            @click="copyToClip(segments)"
            class="action-button"
          >
            <FontAwesomeIcon :icon="['fas', 'copy']" />
          </span>
          
          <span
            v-if="'mediaSlots' in corpusConfig.meta"
            class="timetag"
            :title="document?.name"
          >
            {{ 
              getTimestamps(
                ...getSegmentFrameRangesByIds(segments.map(s=>s.id))
              ).join(" ") }}
          </span>
          
          <span :title="$t('common-play-audio')" @click="playAudio(segments, document, dataLine)" class="action-button" v-if="showAudio(document)">
            <FontAwesomeIcon :icon="['fas', 'play']" />
          </span>
          
          <span :title="$t('common-play-video')" @click="playVideo(segments, document, dataLine)" class="action-button" v-if="showVideo(document)">
            <FontAwesomeIcon :icon="['fas', 'play']" />
          </span>

          <div
            v-for="(segment, sidIndex) in segments"
            :key="`tr-segments-${segmentsIndex}-${sidIndex}`"
            :id="`${store.corpusConfig.firstClass.segment}-${segment.id}`"
          >
            <span
              style="margin-right: 0.5em"
              @mousemove="!details && showAnnotations(segment.id, $event)"
              @mouseleave="!details && !stickyAnnotations.x && !stickyAnnotations.y && closeAnnotations()"
              @click="details ? showModal(getDataLine(segment.id, segment.char_range)) : setStickyAnnotations($event)"
              :data-bs-toggle="details ? 'modal' : ''"
              :data-bs-target="details ? `#detailsModal${randInt}` : ''"
              class="icon-info ms-2"
            >
              <FontAwesomeIcon :icon="['fas', 'circle-info']" />
            </span>

            <span
              v-if="!hideImage && getImageLayerAttribute(segment.id)"
              @click="showImage(segment.id, dataLine)"
              class="icon-info ms-2"
            >
              <FontAwesomeIcon :icon="['fas', 'image']" />
            </span>
            
            <PlainTokens
              :item="formatTokens(segment, dataLine)"
              :columnHeaders="columnHeaders"
              :currentToken="currentToken"
              :resultIndex="dataLine?.id"
              @showPopover="showPopover"
              @closePopover="closePopover"
            />
          </div>
        </td>
        
        <td class="buttons">
          <button
            v-if="!details"
            type="button"
            class="btn btn-secondary btn-sm"
            data-bs-toggle="modal"
            :data-bs-target="`#detailsModal${randInt}`"
            @click="showModal(dataLine)"
          >
            {{ $t('common-details') }}
          </button>
        </td>
        
        <td :class="['audioplayer','audioplayer-'+segmentsIndex, playIndex === segmentsIndex ? 'visible' : '']"></td>
      </tr>
    </tbody>
  </table>
  
  <!-- Token popover -->
  <div
    class="popover-liri"
    v-if="currentToken"
    :style="{ top: popoverY + 'px', left: popoverX + 'px' }"
  >
    <table class="table popover-table">
      <thead>
        <tr>
          <th v-for="(item, index) in currentToken.columnHeaders" :key="`th-${index}`">
            {{ item }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td v-for="(item, index) in currentToken.columnHeaders" :key="`tr-${index}`">
            <span v-if="item === 'head'" v-html="headToken"> </span>
            <span
              v-else
              :class="
                item.indexOf('pos') > -1
                  ? 'badge rounded-pill bg-secondary'
                  : ''
              "
              v-html="strPopover(currentToken.token[index])"
            ></span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Annotation display using the new reusable component -->
  <AnnotationDisplay
    v-if="showingAnnotations"
    :axisPositions="annotationAxisPositions"
    :stickyPosition="stickyAnnotations"
    :style="{ top: annotationDisplayPosition.y + 'px', left: annotationDisplayPosition.x + 'px' }"
    @close="closeAnnotations"
  />
  
  <!-- Details modal -->
  <div
    class="modal fade modal-xl"
    :id="`detailsModal${randInt}`"
    tabindex="-1"
    aria-labelledby="detailsModalLabel"
    aria-hidden="true"
  >
    <div class="modal-dialog modal-full">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="detailsModalLabel">{{ $t('common-details') }}</h5>
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
              :data="modalData"
              :corpora="corpora"
              :languages="languages"
              :key="modalData.id"
              :hideContext="hideContext"
              v-if="modalVisible"
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
  
  <audio controls ref="audioplayer" class="d-none">
    <source src="" type="audio/mpeg">
    {{ $t('results-audio-no-support') }}
  </audio>
</template>

<script>
import PlainTokens from '@/components/results/PlainToken.vue';
import ResultsDetailsModalView from '@/components/results/DetailsModalView.vue';
import AnnotationDisplay from '@/components/AnnotationDisplay.vue';
import { useNotificationStore } from '@/stores/notificationStore';
import { useCorpusAnnotationsStore } from '@/stores/corpusAnnotations';
import Utils from '@/utils.js';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import config from '@/config';
import { DataLine } from '@/classes/WSDataResults.js';

const TokenToDisplay = Utils.TokenToDisplay;
const SEGMENT_WINDOW = 2; // number of +/- characters to retrieve the surrounding sentences

export default {
  name: 'SegmentTable',
  components: {
    PlainTokens,
    ResultsDetailsModalView,
    FontAwesomeIcon,
    AnnotationDisplay
  },
  emits: ['updatePage', 'playMedia', 'showImage'],
  props: [
    'preparedRanges',
    'languages',
    'corpora',
    'resultsPerPage',
    'loading',
    "details",
    "hideCopy",
    "hideImage",
    "hideContext"
  ],
  data() {

    const corpusAnnotations = useCorpusAnnotationsStore();

    let allowedMetaColumns = {}
    const corpusConfig = this.corpora?.corpus || corpusAnnotations.corpusConfig;

    Object.keys(corpusConfig.layer || {}).forEach(layer => {
      if (corpusConfig.layer[layer].attributes) {
        allowedMetaColumns[layer] = [
          ...Object.keys(corpusConfig.layer[layer].attributes),
          ...Object.keys(corpusConfig.layer[layer].attributes.meta || {})
        ];
        if (allowedMetaColumns[layer].includes('meta')) {
          delete allowedMetaColumns.meta;
        }
        if (corpusConfig.meta.mediaSlots && layer === corpusConfig.firstClass.document) {
          allowedMetaColumns[layer].push('name');
        }
      }
    });

    return {
      store: corpusAnnotations,
      sentences: corpusAnnotations.segments,
      sentencesByStream: corpusAnnotations.sentencesByStream,
      popoverY: 0,
      popoverX: 0,
      currentToken: null,
      currentResultIndex: null,
      showingAnnotations: false,
      annotationAxisPositions: [],
      annotationDisplayPosition: { x: 0, y: 0 },
      stickyAnnotations: { x: null, y: null },
      modalVisible: false,
      modalData: null,
      currentPage: 1,
      allowedMetaColumns: allowedMetaColumns,
      randInt: Math.floor(Math.random() * 1000),
      playIndex: -1,
      selectedLine: -1,
      selectedPage: -1,
      detachSelectedLine: false
    };
  },
  computed: {
    corpusConfig() {
      return this.corpora?.corpus || this.store.corpusConfig;
    },
    
    segmentWindow() {
      return SEGMENT_WINDOW;
    },
    
    imageLayerAttribute() {
      if (!this.corpusConfig) return ['', ''];
      for (let [layerName, props] of Object.entries(this.corpusConfig.layer)) {
        let attrs = props.attributes || {};
        if ('meta' in attrs) {
          attrs = { ...attrs, ...attrs.meta };
        }
        for (let [aname, aprops] of Object.entries(attrs || {})) {
          if (aprops.type === 'image') {
            return [layerName, aname];
          }
        }
      }
      return ['', ''];
    },
    
    headToken() {
      let token = '-';
      let headIndex = this.columnHeaders.indexOf('head');
      let lemmaIndex = this.columnHeaders.indexOf('lemma');
      if (headIndex) {
        let tokenId = this.currentToken[headIndex];
        if (tokenId) {
          let sentenceId = this.data[this.currentResultIndex][0];
          if (sentenceId in this.sentences) {
            const sentence = this.sentences[sentenceId];
            let startId = sentence[0];
            let tokenIndexInList = tokenId - startId;
            token = sentence[1][tokenIndexInList][lemmaIndex];
          }
        }
      }
      return token;
    },
    
    columnHeaders() {
      let partitions = this.corpusConfig.partitions
        ? this.corpusConfig.partitions.values
        : [];
      let columns = this.corpusConfig.mapping?.layer?.[this.corpusConfig.segment];
      if (partitions.length) {
        columns = columns?.partitions?.[partitions[0]];
      }
      return columns?.prepared?.columnHeaders || [];
    },
    
    baseMediaUrl() {
      let retval = '';
      if (this.corpusConfig) {
        retval = `${config.baseMediaUrl}/${this.corpusConfig.schema_path}/`;
      }
      return retval;
    },


    /**
     * Get pairs of [PreparedSegment,(DataLine)]
     * @returns {Array} - Array of [PreparedSegment,(DataLine)]
     */
    preparedSegments() {
      const documentLayerName = this.corpusConfig.firstClass?.document;
      if (!documentLayerName) return [];
      const docAnnotations = this.store.annotationsByLayer[documentLayerName];
      if (!docAnnotations) return [];
      const docStream = docAnnotations.byStream;

      const prepared = [];
      for (let [strRange,dataLine] of Object.entries(this.preparedRanges)) {
        let range = strRange.split(",").map(x=>parseInt(x));
        const doc = docStream.searchValue(range)[0];
        if (doc && dataLine) {
          // has hits to display: show preceding and following segments
          range[0] = Math.max(range[0]-2, doc.char_range[0]);
          range[1] = Math.min(range[1]+2, doc.char_range[1]);
        }
        const segments = this.store.getSegmentsByCharRange(range);
        if (!segments || segments.length == 0) continue;
        if (!dataLine)
          dataLine = this.getDataLine(segments[0].id, range, segments.length);
        // no hits: create a dataLine with segment ID and char_range
        prepared.push([segments, doc, dataLine]);
      }
      return prepared;
    }
  },
  methods: {
    getDataLine(segmentId, range, n) {
      return new DataLine(
        [segmentId, [], range] // no hits
        ,
        n
      );
    },

    getSegmentFrameRangesByIds(ids) {
      const segAnns = this.store.getSegmentAnnotations();
      if (!segAnns || !segAnns.byId) return [];
      return this.getFrameRange( ids.map(id=>segAnns.byId[id]) );
       
    },

    getSegmentAnnotations(annotations) {
      const segLayerName = this.corpusConfig.firstClass?.segment;
      if (!segLayerName) return {};
      return annotations[segLayerName] || {};
    },
    
    selectLine(dataLine, detach) {
      if (!dataLine) return;
      const index = dataLine.id;
      this.detachSelectedLine = detach;
      this.selectedLine = index;
      this.selectedPage = this.currentPage;
    },
    
    showPopover(token, resultIndex, event) {
      this.popoverY = event.clientY + 10;
      this.popoverX = event.clientX + 10;
      this.currentToken = token;
      this.currentResultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
    },
    
    closePopover() {
      this.currentToken = null;
      this.currentResultIndex = null;
    },
    
    showAnnotations(sentenceId, event, overwriteSid) {
      if (this.stickyAnnotations.x || this.stickyAnnotations.y) return;
      this.closePopover();
      this.currentResultIndex = sentenceId;
      if (overwriteSid)
        sentenceId = overwriteSid;
      
      // Get axis positions for this segment from store
      this.annotationAxisPositions = this.store.getSegmentAxisPositions(sentenceId);
      
      if (this.annotationAxisPositions.length === 0) {
        this.closeAnnotations();
        return;
      }
      
      this.annotationDisplayPosition = {
        x: event.clientX + 10,
        y: event.clientY + 10
      };
      this.showingAnnotations = true; 
    },
    
    closeAnnotations() {
      this.showingAnnotations = false;
      this.stickyAnnotations = { x: null, y: null };
    },
    
    setStickyAnnotations(event) {
      if (this.stickyAnnotations.x && this.stickyAnnotations.y) {
        this.stickyAnnotations = { x: null, y: null };
      } else {
        this.stickyAnnotations = { x: event.clientX, y: event.clientY };
      }
    },
    
    getImageLayerAttribute(segmentId) {
      const layers = this.corpusConfig?.layer;
      if (!layers || !this.sentences || !(segmentId in this.sentences)) return null;
      const segAnnotations = this.sentences[segmentId].annotations;
      for (let layer in segAnnotations) {
        if (!(layer in layers)) continue;
        const attribute = Object.entries(layers[layer].attributes || {}).find(kv=>kv[1].type == "image")
        if (attribute)
          return [layer, attribute[0]];
      }
      return null;
    },

    showImage(segmentId, dataLine) {
      const sentence = this.sentences[segmentId];
      if (!sentence) return;
      let image = null;
      const imageLayerAttribute = this.getImageLayerAttribute(segmentId);
      if (!imageLayerAttribute) return;
      const [layer, aName] = imageLayerAttribute;
      const aId = sentence.annotations[layer];
      const meta = this.store.annotationsByLayer[layer];
      if (!meta || !aId || !(aId in meta.byId)) return;
      const props = meta.byId[aId];
      const filename = props[aName];
      image = {
        name: filename.replace(/\.[^.]+$/,""),
        src: this.baseMediaUrl + filename,
        resultSegment: segmentId,
        layer: layer,
        layerId: aId,
        dataLine: dataLine
      };
      if (!image) return;
      this.detachSelectedLine = true;
      console.log("emitting showImage", image);
      this.$emit("showImage", image);
    },

    showModal(dataLine) {
      this.modalData = dataLine;
      this.modalVisible = true;
    },
    
    updatePage(currentPage) {
      this.currentPage = currentPage;
      this.$emit('updatePage', this.currentPage);
    },
    
    copyToClip(item) {
      Utils.copyToClip(item);
      useNotificationStore().add({
        type: 'success',
        text: 'Copied to clipboard'
      });
    },
    
    getMedia(document) {
      if (!document) return "";
      let media = document.media;
      if (!media) return '';
      try {
        media = JSON.parse(media);
      } catch { /* empty */ }
      const media_name = Object.keys(this.corpusConfig.meta.mediaSlots || {'': 0})[0];
      if (!media_name) return '';
      return media[media_name];
    },

    showAudio(document) {
      let retval = false;
      if (config.appType === 'soundscript' || config.appType === 'lcp')
        retval = !!this.getMedia(document);
      return retval;
    },
    
    getTimestamps(lower_frame, upper_frame) {
      const lfs = lower_frame / 25.0;
      const ufs = upper_frame / 25.0;
      let min_l = Math.floor(lfs / 60);
      let min_u = Math.floor(ufs / 60);
      let sec_l = Math.round(100 * (lfs % 60)) / 100;
      let sec_u = Math.round(100 * (ufs % 60)) / 100;
      if (min_l < 10) min_l = `0${min_l}`;
      if (min_u < 10) min_u = `0${min_u}`;
      if (sec_l < 10) sec_l = `0${sec_l}`;
      if (sec_u < 10) sec_u = `0${sec_u}`;
      return [`${min_l}:${sec_l}`, `${min_u}:${sec_u}`];
    },

    /**
     * Get the max frame_range of the passed annotations
     * @param {Array} ranges - Array of annotations
     * @returns {Array} - Array, frame_range [start,end]
     */
    getFrameRange(annotations) {
      const noMatch = [-1,-1];
      const allLayerFrames = annotations.map(l=>l.frame_range).filter(x=>x instanceof Array).flat();
      if (allLayerFrames.length == 0) return noMatch;
      let layerFrames = [Math.min(...allLayerFrames), Math.max(...allLayerFrames)];
      const docAnnotations = this.store.getDocumenttAnnotations();
      const docMatches = docAnnotations.byTime.searchValue(layerFrames);
      if (docMatches.length == 0) return noMatch;
      const allDocFrames = docMatches.map(d=>d.frame_range).filter(x=>x instanceof Array);
      const docFrameStart = Math.min(...allDocFrames.flat());
      return [
        Math.min(...allLayerFrames.flat()) - docFrameStart,
        Math.max(...allLayerFrames.flat()) - docFrameStart
      ];
    },
    
    playAudio(segments, document, dataLine) {
      try {
        this.$refs.audioplayer.pause();
      } catch { /* empty */ }
      const audio = this.getMedia(document);
      if (!audio) return;
      const segFrames = this.getSegmentFrameRangesByIds(segments.map(s=>s.id));
      const [startTime, endTime] = segFrames.map(x=>x/25.0);
      this.$emit('playMedia', {
        documentId: document._id,
        filename: audio,
        startTime: startTime,
        endTime: endTime,
        type: 'audio'
      });
      this.selectLine(dataLine.id, true);
    },

    showVideo(document) {
      let retval = false;
      if (config.appType === 'videoscope' || config.appType === 'lcp')
        retval = !!this.getMedia(document);
      return retval;
    },

    playVideo(segments, document, dataLine) {
      try {
        this.$refs.videooplayer.pause();
      } catch { /* empty */ }
      const video = this.getMedia(document);
      if (!video) return;
      const segFrames = this.getSegmentFrameRangesByIds(segments.map(s=>s.id));
      const [startTime, endTime] = segFrames.map(x=>x/25.0);
      this.$emit('playMedia', {
        documentId: document._id,
        filename: video,
        startTime: startTime,
        endTime: endTime,
        type: 'video'
      });
      this.selectLine(dataLine.id, true);
    },

    strPopover(attribute) {
      if (attribute && attribute.constructor.name === 'Object') {
        return Utils.dictToStr(attribute);
      } else {
        return attribute;
      }
    },
    
    formatTokens(sentence, dataLine) {
      const startIndex = sentence.offset;
      const annotations = sentence.annotations;
      const hits = dataLine?.hits || [];
      let tokens = sentence.content;

      const tokenData = hits.map(tokenIdOrSet => (tokenIdOrSet instanceof Array ? [...tokenIdOrSet] : [tokenIdOrSet]).flat());
      tokens = tokens.map((token, idx) => new TokenToDisplay(
        token,
        startIndex + idx,
        tokenData,
        this.columnHeaders,
        annotations
      ));

      return tokens;
    }
  },
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