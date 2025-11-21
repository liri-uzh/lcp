<template>
  <div id="plain-table-view">
    <PaginationComponent
      v-if="data"
      class="paggination"
      :resultCount="data.length"
      :resultsPerPage="resultsPerPage"
      :currentPage="currentPage"
      @update="updatePage"
      :key="data.length"
      :loading="loading"
    />
    <table class="table" v-if="data">
      <!-- <thead>
        <tr>
          <th scope="col" style="width: 100%">Result</th>
          <th scope="col">-</th>
        </tr>
      </thead> -->
      <tbody>
        <tr
          v-for="(item, resultIndex) in results"
          :key="`tr-results-${resultIndex}`"
          :data-index="resultIndex"
          :class="item.id == this.selectedLine && this.selectedPage == this.currentPage ? `selected ${this.detachSelectedLine ? 'detached' : ''}` : ''"
          @mousemove="hoverResultLine(item.id)"
          @mouseleave="hoverResultLine(null)"
          @click="selectLine(item.id, this.detachSelectedLine)"
        >
          <td scope="row" class="results">
            <div
              v-if="item.id == this.selectedLine && this.detachSelectedLine"
              class="unpin"
              @click="selectLine(item.id, false)"
            >
              <FontAwesomeIcon :icon="['fas', 'thumb-tack']" />
              Unpin
            </div>
            <span :title="$t('common-copy-clipboard')" @click="copyToClip(item)" class="action-button">
              <FontAwesomeIcon :icon="['fas', 'copy']" />
            </span>
            <span
              v-if="'mediaSlots' in corpora.corpus.meta"
              class="timetag"
              :title="meta[item.sentenceId][corpora.corpus.firstClass.document].name"
            >
              {{
                this.getTimestamps(...this.getFrameRange(item.id, this.corpora.corpus.firstClass.segment)).join(" ")
              }}
            </span>
            <span :title="$t('common-play-audio')" @click="playAudio(item.id)" class="action-button" v-if="showAudio(item.id)">
              <FontAwesomeIcon :icon="['fas', 'play']" />
            </span>
            <span :title="$t('common-play-video')" @click="playVideo(item.id)" class="action-button" v-if="showVideo(item.id)">
              <FontAwesomeIcon :icon="['fas', 'play']" />
            </span>
            <div
              v-for="(sid, sidIndex) in segmentSidSeries(item.sentenceId)"
              :key="`tr-results-${resultIndex}-${sidIndex}`"
            >
              <span
                v-if="Object.keys(meta).length && sid in meta"
                style="margin-right: 0.5em"
                @mousemove="showMeta(item.id, $event, sid)"
                @mouseleave="!stickMeta.x && !stickMeta.y && closeMeta()"
                @click="setStickMeta($event)"
                class="icon-info ms-2"
              >
                <FontAwesomeIcon :icon="['fas', 'circle-info']" />
              </span>
              <PlainTokens
                :item="formatTokens([sid, ...item.hits])"
                :columnHeaders="columnHeaders"
                :currentToken="currentToken"
                :resultIndex="item.id"
                @showPopover="showPopover"
                @closePopover="closePopover"
              />
            </div>
          </td>
          <td class="action-button"
            @click="showImage(...getImage(item.id), item.id, this.meta[item.sentenceId])"
            v-if="getImage(item.id)"
          >
            <FontAwesomeIcon :icon="['fas', 'image']" />
          </td>
          <td class="action-button" style="opacity: 0.5;" title="No or more than one images"
            v-else-if="Object.entries(this.meta[item.sentenceId] || {}).find((lp=>lp[1].xy_box))"
          >
            <FontAwesomeIcon :icon="['fas', 'image']" />
          </td>
          <td class="buttons">
            <button
              type="button"
              class="btn btn-secondary btn-sm"
              data-bs-toggle="modal"
              :data-bs-target="`#detailsModal${randInt}`"
              @click="showModal(item.id)"
            >
              {{ $t('common-details') }}
            </button>
          </td>
          <td :class="['audioplayer','audioplayer-'+item.id, playIndex == item.id ? 'visible' : '']"></td>
        </tr>
      </tbody>
    </table>
    <PaginationComponent
      v-if="data"
      class="paggination"
      :resultCount="data.length"
      :resultsPerPage="resultsPerPage"
      :currentPage="currentPage"
      @update="updatePage"
      :key="data.length"
      :loading="loading"
    />
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
              <span v-if="item == 'head'" v-html="headToken"> </span>
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
    <div
      class="popover-liri"
      v-if="currentMeta"
      :style="{
        top: `min(${stickMeta.y || popoverY}px, calc(100vh - 33vh))`,
        left: (stickMeta.x || popoverX) + 'px',
        overflowY: (stickMeta.x || stickMeta.y) ? 'scroll' : 'visible',
        maxHeight: stickMeta.y ? '33vh' : 'unset',
      }"
    >
      <span
        v-if="stickMeta.x && stickMeta.y"
        style="position:absolute; right: 7px; top: 2px; cursor: pointer;"
        @click="(stickMeta = {}) && this.closeMeta()"
      >
        <FontAwesomeIcon :icon="['fas', 'xmark']" />
      </span>
      <table class="popover-table">
        <template v-for="(meta, layer) in currentMeta" :key="`th-${layer}`">
          <tr v-if="layer in allowedMetaColums">
            <td @click="this.meta_fold(layer, /*flip=*/true)">
              <span class="text-bold">{{ this.meta_fold(layer) ? "&#9662;" : "&#9656;" }}{{ layer }}
                <span v-if="'mediaSlots' in corpora.corpus.meta" class="timetag nowrap">
                  {{
                    this.getTimestamps(...meta.frame_range
                      .map(fr=>fr-currentMeta[corpora.corpus.firstClass.document].frame_range[0])
                    ).join(' - ')
                  }}
                </span>
              </span>
              <table class="popover-deatils-table mb-2">
                <template v-for="(meta_value, meta_key) in meta" :key="`${layer}-${meta_key}`">
                  <tr v-if="allowedMetaColums[layer].includes(meta_key) && (!isEmpty(meta_value) || meta_fold(layer))">
                    <td>{{ meta_key }}</td>
                    <td v-if="(corpora.corpus.layer[layer].attributes[meta_key]||{}).type == 'image'">
                      <span
                        data-bs-toggle="modal"
                        :data-bs-target="`#imageModal${randInt}`"
                        @click="showImage(meta_value, layer, this.currentResultIndex)"
                        v-html="meta_value"
                      >
                      </span>
                    </td>
                    <td v-else v-html="meta_render(meta_value, layer, meta_key)"></td>
                  </tr>
                </template>
              </table>
            </td>
          </tr>
        </template>
      </table>
    </div>
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
                :data="data[modalIndex]"
                :sentences="sentences"
                :sentencesByStream="sentencesByStream"
                :meta="meta"
                :corpora="corpora"
                :languages="languages"
                :key="modalIndex"
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
  </div>
</template>

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
td.icons {
  min-width: 100px;
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
.paggination {
  float: right;
}
.paggination:after {
  clear: both;
  content: "";
}
.header-form {
  text-align: center;
}
.popover-table th {
  text-transform: uppercase;
  font-size: 10px;
}
.popover-table {
  margin-bottom: 0;
  padding: 5px;
}
.popover-deatils-table {
  border-radius: 4px;
  background-color: #ffffff82;
}
.header-left {
  text-align: right;
}
.left-context {
  text-align: right;
  overflow: hidden;
  white-space: nowrap;
  max-width: 0;
  direction: rtl;
  width: 40%;
  text-overflow: ellipsis;
}
.middle-context {
  /* white-space: nowrap;
  overflow: visible;
  max-width: 0;
  width: 10%; */
  text-align: center;
}
.right-context {
  white-space: nowrap;
  overflow: hidden;
  white-space: nowrap;
  max-width: 0;
  width: 40%;
  text-overflow: ellipsis;
  text-align: left;
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
  /* padding-left: 2px;
  padding-right: 2px; */
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
  margin-right: -2px; /* compensate for next token's padding-left */
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
*[class^="color-group-"] {
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

<script>
import PlainTokens from "@/components/results/PlainToken.vue";
import PaginationComponent from "@/components/PaginationComponent.vue";
import ResultsDetailsModalView from "@/components/results/DetailsModalView.vue";
import { useNotificationStore } from "@/stores/notificationStore";
import Utils from "@/utils.js";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import config from "@/config";

class DataLine {
  constructor(line, n) {
    this.id = n;
    this.sentenceId = line[0];
    this.hits = line.slice(1,);
  }
}

const TokenToDisplay = Utils.TokenToDisplay;

const SEGMENT_WINDOW = 2; // number of +/- characters to retrieve the surrounding sentences

export default {
  name: "ResultsPlainTableView",
  emits: ["updatePage", "hoverResultLine", "playMedia", "showImage"],
  props: [
    "data",
    "sentences",
    "sentencesByStream",
    "languages",
    "attributes",
    "meta",
    "corpora",
    "resultsPerPage",
    "loading",
  ],
  data() {
    let allowedMetaColums = {}

    Object.keys(this.corpora.corpus.layer).forEach( layer => {
      if (this.corpora.corpus.layer[layer].attributes/* && this.corpora.corpus.layer[layer].attributes.meta*/) {
        // allowedMetaColums[layer] = Object.keys(this.corpora.corpus.layer[layer].attributes.meta)
        allowedMetaColums[layer] = [
          ...Object.keys(this.corpora.corpus.layer[layer].attributes),
          ...Object.keys(this.corpora.corpus.layer[layer].attributes.meta||{})
        ];
        if ("meta" in allowedMetaColums)
          delete allowedMetaColums.meta;
        if (this.corpora.corpus.meta.mediaSlots && layer == this.corpora.corpus.firstClass.document)
          allowedMetaColums[layer].push("name");
      }
    });

    return {
      popoverY: 0,
      popoverX: 0,
      currentToken: null,
      currentResultIndex: null,
      currentMeta: null,
      stickMeta: {},
      modalVisible: false,
      modalIndex: null,
      currentPage: 1,
      allowedMetaColums: allowedMetaColums,
      randInt: Math.floor(Math.random() * 1000),
      playIndex: -1,
      image: null,
      selectedLine: -1,
      selectedPage: -1,
      detachSelectedLine: false
    };
  },
  components: {
    PlainTokens,
    ResultsDetailsModalView,
    PaginationComponent,
    FontAwesomeIcon
},
  methods: {
    segmentSidSeries(sid) {
      if (!(sid in this.sentences)) return [];
      const sentence = this.sentences[sid];
      const range = sentence.find(x=>x instanceof Array && x.length == 2 && x.every(y=>typeof(y)=="number"));
      if (!range) return [sid];
      return this.sentencesByStream
        .search(range.map((x,i)=>x + (i==0?-1:1) * this.segmentWindow))
        .sort((x,y)=>x.low > y.low)
        .map(x=>x.value)
        .filter(s=>s in this.sentences);
    },
    selectLine(index, detach) {
      if (detach && (this.showAudio(index) || this.showVideo(index) || this.imageLayerAttribute[0]))
        this.detachSelectedLine = true;
      else
        this.detachSelectedLine = false;
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
    showMeta(resultIndex, event, overwriteSid) {
      if (this.stickMeta.x || this.stickMeta.y) return;
      this.closePopover();
      resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
      let sentenceId = this.data[resultIndex][0];
      const layer = this.corpora.corpus.layer;
      this.currentResultIndex = resultIndex;
      if (overwriteSid)
        sentenceId = overwriteSid;
      this.currentMeta = Object.fromEntries(Object.entries(this.meta[sentenceId]).sort((x,y)=>y[0] != layer[x[0]]?.contains));
      for (let layer in this.currentMeta) {
        const submeta = this.currentMeta[layer].meta;
        if (!submeta || (this.corpora.corpus.mapping[layer]||{}).hasMeta === false) continue
        delete this.currentMeta[layer].meta;
        for (let k in submeta) {
          if (k in this.currentMeta[layer]) continue;
          this.currentMeta[layer][k] = submeta[k];
        }
        for (let k in this.currentMeta[layer]) {
          if (!(k in submeta)) continue;
          const isString = typeof(submeta[k]) == "string";
          if (isString)
            this.currentMeta[layer][k] = submeta[k].trim();
          if (isString && submeta[k].match(/^0+(\.0+)?$/))
            this.currentMeta[layer][k] = "<span>0</span>";
          if (typeof(this.currentMeta[layer][k]) == "object" && Object.keys(this.currentMeta[layer][k]).length == 0)
            this.currentMeta[layer][k] = null;
        }
      }
      this.popoverY = event.clientY + 10;
      this.popoverX = event.clientX + 10;
    },
    closeMeta() {
      this.currentMeta = null;
    },
    setStickMeta(event) {
      this.stickMeta = (this.stickMeta.x && this.stickMeta.y ? {} : {x: event.clientX, y: event.clientY});
    },
    showModal(index) {
      this.modalIndex = index + (this.currentPage - 1) * this.resultsPerPage;
      this.modalVisible = true;
    },
    getImage(resultIndex) {
      if (!this.corpora.corpus) return null;
      const [layerName, aname] = this.imageLayerAttribute;
      if (!layerName || !aname) return null;
      const meta = this.meta[this.data[resultIndex][0]];
      if (!meta || !(layerName in meta)) return null;
      const filename = meta[layerName][aname];
      if (!filename)
        return null;
      return [filename, layerName];
    },
    showImage(filename, imageLayer, resultIndex, meta=null) {
      if (meta===null)
        meta = this.currentMeta;
      if (!meta) return;
      const segId = this.data[resultIndex][0];
      const layerId = this.meta[segId][imageLayer]._id;
      const dataForGroups = (this.data || []).find(r=>r[0]==segId);
      let groups = [];
      try {
        groups = dataForGroups ? JSON.parse(JSON.stringify(dataForGroups[1])) : [];
      } catch { null }
      this.image = {
        name: filename.replace(/\.[^.]+$/,""),
        src: this.baseMediaUrl + filename,
        resultSegment: segId,
        groups: groups,
        layer: imageLayer,
        layerId: layerId,
        columnHeaders: this.columnHeaders
      };
      this.detachSelectedLine = true;
      this.$emit("showImage", this.image);
    },
    hoverResultLine(resultIndex) {
      let line = null;
      if (resultIndex !== null) {
        const adjustedIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
        line = this.data[adjustedIndex]
      }
      this.$emit("hoverResultLine", line);
    },
    updatePage(currentPage) {
      this.currentPage = currentPage;
      this.$emit("updatePage", this.currentPage);
    },
    bgCheck(resultIndex, groupIndex, tokenIndexInResultset, range, type) {
      let classes = [];

      if (type == 2) {
        classes.push('text-bold')
        classes.push(`color-group-${groupIndex}`)
      }

      if (this.currentResultIndex == resultIndex && this.currentToken) {
        // Because of pages
        resultIndex =
          resultIndex + (this.currentPage - 1) * this.resultsPerPage;

        let sentenceId = this.data[resultIndex][0];
        let startId = this.sentences[sentenceId][0];
        let currentTokenId = 0;
        let groupStartIndex = 0;

        // Left context of resultset
        if (type == 1) {
          // Beacuse of reverse
          // if (range[groupIndex].length >= tokenIndexInResultset) {
          //   tokenIndexInResultset = range[groupIndex].length - tokenIndexInResultset - 1
          // }
          if (groupIndex > 0) {
            groupStartIndex = range[range.length - 1][groupIndex - 1].at(-1) + 1;
          }
        } else if (type == 3) {
          groupStartIndex = range[range.length - 1].at(-1).at(-1) + 1;
        } else if (type == 2) {
          groupStartIndex = range[range.length - 1][groupIndex][0];
        }

        currentTokenId = groupStartIndex + tokenIndexInResultset;
        classes.push(`TR-${currentTokenId}-L${groupStartIndex}`)

        currentTokenId = startId + groupStartIndex + tokenIndexInResultset;

        let headIndex = this.columnHeaders.indexOf("head");
        let currentTokenHeadId = this.currentToken[headIndex];
        if (currentTokenId == currentTokenHeadId) {
          classes.push("highlight");
        }
      }
      return classes;
    },
    copyToClip(item) {
      Utils.copyToClip(item);
      useNotificationStore().add({
        type: "success",
        text: "Copied to clipboard",
      });
    },
    getAudio(resultIndex) {
      const sentenceId = this.data[resultIndex][0];
      let meta = this.meta[sentenceId];
      if (!meta) return "";
      const doc_meta = meta[this.corpora.corpus.firstClass.document];
      if (!doc_meta) return "";
      let media = doc_meta.media;
      if (!media) return "";
      try {
        media = JSON.parse(media)
      } catch {
        null;
      }
      const media_name = Object.keys(this.corpora.corpus.meta.mediaSlots||{'':0})[0];
      if (!media_name) return "";
      return media[media_name];
    },
    showAudio(resultIndex) {
      let retval = false;
      // Just for soundscript
      if (config.appType == "soundscript" || config.appType == "lcp") {
        resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
        if (this.getAudio(resultIndex)) {
          retval = true;
        }
      }
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
    getFrameRange(resultIndex, layer) {
      const sentenceId = this.data[resultIndex][0];
      const meta = this.meta[sentenceId];
      const docLayer = this.corpora.corpus.firstClass.document;
      if (!meta || !(layer in meta) || !(docLayer in meta))
        return [0,0];
      const docLower = meta[docLayer].frame_range[0];
      return meta[layer].frame_range.map(fr=>fr-docLower);
    },
    playAudio(resultIndex) {
      try {
        this.$refs.audioplayer.pause();
      } catch {
        // pass
      }
      resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
      const sentenceId = this.data[resultIndex][0];
      let meta = this.meta[sentenceId];
      if (meta) {
        // corpus tamplete,
        const doc_layer = this.corpora.corpus.firstClass.document;
        let documentId = meta[doc_layer]._id;
        let filename = this.getAudio(resultIndex); // meta[this.corpora.corpus.firstClass.document].audio
        let [startFrameSeg, endFrameSeg] = this.getFrameRange(resultIndex, this.corpora.corpus.firstClass.segment);
        let startTime = startFrameSeg / 25.0;
        let endTime = endFrameSeg / 25.0;

        this.$emit("playMedia", {
          documentId: documentId,
          filename: filename,
          startTime: startTime,
          endTime: endTime,
          type: "audio"
        });

        this.selectLine(resultIndex, true);
      }
    },
    showVideo(resultIndex) {
      let retval = false;
      // Just for soundscript
      if (config.appType == "videoscope" || config.appType == "lcp") {
        resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
        if (this.getAudio(resultIndex)) {
          retval = true;
        }
      }
      return retval;
    },
    playVideo(resultIndex) {
      this.$refs.audioplayer.pause();
      resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
      const sentenceId = this.data[resultIndex][0];
      let meta = this.meta[sentenceId];
      if (meta) {
        let documentId = meta[this.corpora.corpus.firstClass.document]._id;
        let filename = this.getAudio(resultIndex); // meta[this.corpora.corpus.firstClass.document].audio
        let [startFrameDoc, endFrameDoc] = this.getFrameRange(resultIndex, this.corpora.corpus.firstClass.document);
        let [startFrameSeg, endFrameSeg] = this.getFrameRange(resultIndex, this.corpora.corpus.firstClass.segment);
        let startTime = startFrameSeg / 25.0;
        let endTime = endFrameSeg / 25.0;

        this.$emit("playMedia", {
          documentId: documentId,
          filename: filename,
          startFrame: startFrameDoc,
          endFrame: endFrameDoc,
          startTime: startTime,
          endTime: endTime,
          type: "video"
        })
      }
      this.selectLine(resultIndex, true);
    },
    strPopover(attribute) {
      if (attribute && attribute.constructor.name == 'Object')
        return Utils.dictToStr(attribute);
      else
        return attribute;
    },
    meta_render(meta_value) {
      let ret = "";
      let meta_obj = null;
      try {
        meta_obj = JSON.parse(meta_value.replace(/'/gi, '"'))
      }
      catch {
        meta_obj = meta_value;
      }
      if (Array.isArray(meta_obj))
        ret = meta_obj.join(", ")
      else if (typeof(meta_obj) in {string: 1, number: 1})
        ret = meta_obj
      else
        ret = Utils.dictToStr(meta_obj, {addTitles: true, reorder: x=>x[0]=="id"}); // small hack to put id first
      return ret;
    },
    isEmpty(value) {
      return (typeof(value) != "number" && !value) || (value instanceof Object && Object.keys(value).length == 0);
    },
    meta_fold(layer, flip) {
      this.currentMeta._unfolded = (this.currentMeta._unfolded || {});
      if (flip)
        this.currentMeta._unfolded[layer] = !this.currentMeta._unfolded[layer];
      return this.currentMeta._unfolded[layer];
    },
    formatTokens(row) {
      const sentenceId = row[0];
      const startIndex = this.sentences[sentenceId][0];
      const annotations = this.sentences[sentenceId][2];
      let tokens = this.sentences[sentenceId][1];

      let tokenData = JSON.parse(JSON.stringify(row[1])); // tokens are already gouped in sets/sequences
      tokenData = tokenData.map( tokenIdOrSet => tokenIdOrSet instanceof Array ? tokenIdOrSet : [tokenIdOrSet] );
      // Return a list of TokenToDisplay instances
      tokens = tokens.map( (token,idx) => new TokenToDisplay(token, startIndex + idx, tokenData, this.columnHeaders, annotations) );

      return tokens;
    }
  },
  computed: {
    segmentWindow() { return SEGMENT_WINDOW; },
    imageLayerAttribute() {
      if (!this.corpora.corpus) return ["",""];
      for (let [layerName, props] of Object.entries(this.corpora.corpus.layer)) {
        let attrs = props.attributes || {};
        if ("meta" in attrs)
          attrs = {attrs, ...attrs.meta};
        for (let [aname, aprops] of Object.entries(attrs||{})) {
          if (aprops.type == "image")
            return [layerName,aname];
        }
      }
      return ["",""];
    },
    headToken() {
      let token = "-";
      let headIndex = this.columnHeaders.indexOf("head");
      let lemmaIndex = this.columnHeaders.indexOf("lemma");
      if (headIndex) {
        let tokenId = this.currentToken[headIndex];
        if (tokenId) {
          let sentenceId = this.data[this.currentResultIndex][0];
          let startId = this.sentences[sentenceId][0];
          let tokenIndexInList = tokenId - startId;
          token = this.sentences[sentenceId][1][tokenIndexInList][lemmaIndex];
        }
      }
      return token;
    },
    results() {
      let start = this.resultsPerPage * (this.currentPage - 1);
      let end = start + this.resultsPerPage;
      const ret = this.data
        .map((row,rowIndex)=>new DataLine(row, rowIndex))
        .filter(line => {
          return line.id >= start && line.id < end && this.sentences[line.sentenceId] && this.sentences[line.sentenceId][1] instanceof Array;
        })
        // Sort by range
        .sort((x,y)=>(this.sentences[x.sentenceId]||[0]).at(-1) > (this.sentences[y.sentenceId]||[0]).at(-1));
      return ret;
    },
    columnHeaders() {
      let partitions = this.corpora.corpus.partitions
        ? this.corpora.corpus.partitions.values
        : [];
      let columns = this.corpora.corpus["mapping"]["layer"][this.corpora.corpus["segment"]];
      if (partitions.length) {
        columns = columns["partitions"][partitions[0]];
      }
      return columns["prepared"]["columnHeaders"];
    },
    baseMediaUrl() {
      let retval = ""
      if (this.corpora && this.corpora.corpus) {
        retval = `${config.baseMediaUrl}/${this.corpora.corpus.schema_path}/`
      }
      return retval
    },
  },
};
</script>
