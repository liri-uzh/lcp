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
        >
          <td scope="row" class="results">
            <span title="Copy to clipboard" @click="copyToClip(item)" class="action-button">
              <FontAwesomeIcon :icon="['fas', 'copy']" />
            </span>
            <span title="Play audio" @click="playAudio(resultIndex)" class="action-button" v-if="showAudio(resultIndex)">
              <FontAwesomeIcon :icon="['fas', 'play']" />
            </span>
            <span title="Play video" @click="playVideo(resultIndex)" class="action-button" v-if="showVideo(resultIndex)">
              <FontAwesomeIcon :icon="['fas', 'play']" />
            </span>
            <span
              v-if="Object.keys(meta).length"
              style="margin-right: 0.5em"
              @mousemove="showMeta(resultIndex, $event)"
              @mouseleave="!stickMeta.x && !stickMeta.y && closeMeta()"
              @click="setStickMeta($event)"
              class="icon-info ms-2"
            >
              <FontAwesomeIcon :icon="['fas', 'circle-info']" />
            </span>
            <span
              v-for="(token) in item"
              :key="`form-${token.index}`"
              @mousemove="showPopover(token, resultIndex, $event)"
              @mouseleave="closePopover"
            >
              <span class="token" :class="[
                (currentToken && columnHeaders && currentToken[columnHeaders.indexOf('head')] == token.index ? 'highlight' : ''),
                (token.group >= 0 ? `text-bold color-group-${token.group}` : '')
              ]">{{ token.form }}</span>
              <span class="space" v-if="token.spaceAfter !== 0">&nbsp;</span>
            </span>
            <!-- <template
              v-for="(group, groupIndex) in groups"
              :key="`tbody-${groupIndex}`"
            >
              <span
                class="token"
                v-for="(token, tokenIndex) in item[groupIndex * 2]"
                :key="`rc-${tokenIndex}`"
                :class="bgCheck(resultIndex, groupIndex, tokenIndex, item, 1)"
                @mousemove="showPopover(token, resultIndex, $event)"
                @mouseleave="closePopover"
              >
                {{ token[0] }}
              </span>
              <span
                class="token"
                v-for="(token, tokenIndex) in item[groupIndex * 2 + 1]"
                :key="`form-${tokenIndex}`"
                :class="bgCheck(resultIndex, groupIndex, tokenIndex, item, 2)"
                @mousemove="showPopover(token, resultIndex, $event)"
                @mouseleave="closePopover"
              >
                {{ token[0] }}
              </span>
            </template>
            <span
              class="token"
              v-for="(token, tokenIndex) in item[groups.length * 2]"
              :key="`lt-${tokenIndex}`"
              :class="
                bgCheck(resultIndex, groups.length - 1, tokenIndex, item, 3)
              "
              @mousemove="showPopover(token, resultIndex, $event)"
              @mouseleave="closePopover"
            >
              {{ token[0] }}
            </span> -->
          </td>
          <td class="buttons">
            <button
              type="button"
              class="btn btn-secondary btn-sm"
              data-bs-toggle="modal"
              :data-bs-target="`#detailsModal${randInt}`"
              @click="showModal(resultIndex)"
            >
              Details
            </button>
          </td>
          <td :class="['audioplayer','audioplayer-'+resultIndex, playIndex == resultIndex ? 'visible' : '']"></td>
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
      :style="{top: (stickMeta.y || popoverY) + 'px', left: (stickMeta.x || popoverX) + 'px' }"
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
            <td>
              <span class="text-bold">{{ layer }}</span>
              <table class="popover-deatils-table mb-2">
                <template v-for="(meta_value, meta_key) in meta" :key="`${layer}-${meta_key}`">
                  <tr v-if="allowedMetaColums[layer].includes(meta_key)">
                    <td>{{ meta_key }}</td>
                    <td v-html="meta_render(meta_value)"></td>
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
            <h5 class="modal-title" id="detailsModalLabel">Details</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body text-start">
            <div class="modal-body-content">
              <ResultsDetailsModalView
                :data="data[modalIndex]"
                :sentences="sentences[data[modalIndex][0]]"
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
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
    <audio controls ref="audioplayer" class="d-none">
        <source src="" type="audio/mpeg">
        Your browser does not support the audio element.
    </audio>
  </div>
</template>

<style scoped>
td.icons {
  min-width: 100px;
}
td.buttons {
  min-width: 100px;
}
td.results {
  width: 100%;
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
import ResultsDetailsModalView from "@/components/results/DetailsModalView.vue";
import PaginationComponent from "@/components/PaginationComponent.vue";
import { useNotificationStore } from "@/stores/notificationStore";
import Utils from "@/utils.js";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import config from "@/config";

// import WaveSurfer from 'wavesurfer.js'
// import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'

class TokenToDisplay {
  constructor(tokenArray, index, groups, columnHeaders, annotations) {
    if (!(tokenArray instanceof Array) || tokenArray.length < 2)
      throw Error(`Invalid format for token ${JSON.stringify(tokenArray)}`);
    if (isNaN(Number(index)) || index<=0)
      throw Error(`Invalid index (${index}) for token ${JSON.stringify(tokenArray)}`);
    if (!(groups instanceof Array) || groups.find(g=>!(g instanceof Array)))
      throw Error(`Invalid groups (${JSON.stringify(groups)}) for token ${JSON.stringify(tokenArray)}`);
    columnHeaders.forEach( (header,i) => this[header] = tokenArray[i] );
    this.token = tokenArray;
    this.index = index;
    this.group = groups.findIndex( g => g.find(id=>id==index) );
    this.columnHeaders = columnHeaders.filter(ch=>ch!= 'spaceAfter');
    for (let [annotation_name, annotation_occurences] of Object.entries(annotations||{})) {
      for (let [ann_start_idx, ann_num_toks, annotation] of annotation_occurences) {
        if (index < ann_start_idx || index > (ann_start_idx+(ann_num_toks-1)))
          continue;
        this.columnHeaders.push(annotation_name);
        tokenArray.push(annotation);
        // tokenArray.push(
        //   Object.entries(annotation)
        //     .filter(a=>a[1])
        //     .map((([attr_name,attr_value])=>`<abbr title="${attr_name}">${attr_value}</abbr>`))
        //     .join(", ")
        // );
      }
    }
  }
}

export default {
  name: "ResultsPlainTableView",
  emits: ["updatePage"],
  props: [
    "data",
    "sentences",
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
      }
    })

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
      groups: this.data ? this.getGroups(this.data[0], true) : [],
      randInt: Math.floor(Math.random() * 1000),
      playIndex: -1,
    };
  },
  components: {
    ResultsDetailsModalView,
    PaginationComponent,
    FontAwesomeIcon
},
  methods: {
    // getGroups1(data) {
    //   let groups = [];
    //   let tmpGroup = [];
    //   let tokenData = JSON.parse(JSON.stringify(data));
    //   tokenData = tokenData.splice(1, tokenData.length)[0];
    //   tokenData.forEach((tokenId, idx) => {
    //     if (idx > 0 && Math.abs(tokenData[idx] - tokenData[idx - 1]) > 1) {
    //       if (tmpGroup.length > 0) {
    //         groups.push(tmpGroup.sort());
    //       }
    //       tmpGroup = [];
    //     }
    //     tmpGroup.push(tokenId);
    //   });
    //   groups.push(tmpGroup.sort());
    //   return groups;
    // },
    getGroups(data, initial=false) {
      let groups = [];
      let tmpGroup = [];
      let tokenData = JSON.parse(JSON.stringify(data));
      tokenData = tokenData.splice(1, tokenData.length).sort();
      if (initial === true) {
        tokenData = tokenData[0]
      }
      tokenData.forEach((tokenId, idx) => {
        if (idx > 0 && Math.abs(tokenData[idx] - tokenData[idx - 1]) > 1) {
          if (tmpGroup.length > 0) {
            groups.push(tmpGroup.sort());
          }
          tmpGroup = [];
        }
        tmpGroup.push(tokenId);
      });
      groups.push(tmpGroup.sort());
      return groups;
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
    showMeta(resultIndex, event) {
      if (this.stickMeta.x || this.stickMeta.y) return;
      this.closePopover();
      resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
      const sentenceId = this.data[resultIndex][0];
      this.currentMeta = this.meta[sentenceId];
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
      const media = doc_meta.media;
      if (!media) return "";
      const media_name = Object.keys(this.corpora.corpus.meta.mediaSlots||{'':0})[0];
      if (!media_name) return "";
      return JSON.parse(media)[media_name];
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
    playAudio(resultIndex) {
      this.$refs.audioplayer.pause();
      resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
      const sentenceId = this.data[resultIndex][0];
      let meta = this.meta[sentenceId];
      if (meta) {
        // corpus tamplete,
        let documentId = meta[this.corpora.corpus.firstClass.document].id;
        let filename = this.getAudio(resultIndex); // meta[this.corpora.corpus.firstClass.document].audio
        let startFrame = meta[this.corpora.corpus.firstClass.document].frame_range[0]
        let startTime = (meta[this.corpora.corpus.firstClass.segment].frame_range[0] - startFrame)/25.
        let endTime = (meta[this.corpora.corpus.firstClass.segment].frame_range[1] - startFrame)/25.

        this.$emit("playMedia", {
          documentId: documentId,
          filename: filename,
          startTime: startTime,
          endTime: endTime,
          type: "audio"
        })
        // console.log(filename, startTime, endTime)
        // let startTime = meta["Utterance"].start
        // let endTime = meta[this.corpora.corpus.firstClass.segment].end
        // if (filename) {
        //   // TODO: get path from config
        //   this.$refs.audioplayer.src = this.baseMediaUrl + filename;
        //   this.$refs.audioplayer.currentTime = startTime;
        //   this.$refs.audioplayer.ontimeupdate = () => {
        //     if (this.$refs.audioplayer.currentTime >= endTime) {
        //       this.$refs.audioplayer.pause();
        //     }
        //   };
        //   this.$refs.audioplayer.play();
        //   try {
        //     const wavesurfer = WaveSurfer.create({
        //       container: `.audioplayer-${resultIndex}`,
        //       waveColor: '#4F4A85',
        //       progressColor: '#383351',
        //       url: this.baseMediaUrl + filename,
        //       // media: this.$refs.audioplayer, // <- this is the important part
        //       height: 32
        //     })
        //     wavesurfer.on('interaction', () => {
        //       wavesurfer.play()
        //     })
        //     // Initialize the Regions plugin
        //     const wsRegions = wavesurfer.registerPlugin(RegionsPlugin.create())
        //     // Create some regions at specific time ranges
        //     wavesurfer.on('decode', () => {
        //       // Regions
        //       wsRegions.addRegion({
        //         start: startTime,
        //         end: endTime,
        //         content: '',
        //         color: 'rgba(255, 0, 0, 0.1)',
        //         drag: false,
        //         resize: false,
        //       })
        //     })
        //   }
        //   catch (e){
        //     console.log("Couldn't create the waveform", e);
        //   }
        //   this.playIndex = resultIndex;
        // }
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
        let documentId = meta[this.corpora.corpus.firstClass.document].id;
        let filename = this.getAudio(resultIndex); // meta[this.corpora.corpus.firstClass.document].audio
        let startFrame = meta[this.corpora.corpus.firstClass.document].frame_range[0]
        let endFrame = meta[this.corpora.corpus.firstClass.document].frame_range[1]
        let startTime = (meta[this.corpora.corpus.firstClass.segment].frame_range[0] - startFrame)/25.
        let endTime = (meta[this.corpora.corpus.firstClass.segment].frame_range[1] - startFrame)/25.

        this.$emit("playMedia", {
          documentId: documentId,
          filename: filename,
          startFrame: startFrame,
          endFrame: endFrame,
          startTime: startTime,
          endTime: endTime,
          type: "video"
        })
      }
    },
    strPopover(attribute) {
      if (attribute && attribute.constructor.name == 'Object')
        return Utils.dictToStr(attribute);
      else
        return attribute;
    },
    meta_render(meta_value) {
      let ret = "";
      try {
        let metaJSON = JSON.parse(meta_value.replace(/'/gi, '"'))
        if (Array.isArray(metaJSON)) {
          ret = metaJSON.join(", ")
        }
        else {
          ret = Utils.dictToStr(metaJSON, {addTitles: true, reorder: x=>x[0]=="id"}); // small hack to put id first
        }
      }
      catch {
        ret = meta_value;
      }
      return ret;
    }
  },
  computed: {
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
      return this.data
        .filter((row, rowIndex) => {
          let sentenceId = row[0];
          return rowIndex >= start && rowIndex < end && this.sentences[sentenceId];
        })
        .map((row) => {
          let sentenceId = row[0];
          let startIndex = this.sentences[sentenceId][0];
          let tokens = this.sentences[sentenceId][1];
          let annotations = this.sentences[sentenceId][2];

          let tokenData = JSON.parse(JSON.stringify(row[1])); // tokens are already gouped in sets/sequences
          tokenData = tokenData.map( tokenIdOrSet => tokenIdOrSet instanceof Array ? tokenIdOrSet : [tokenIdOrSet] );
          // Return a list of TokenToDisplay instances
          tokens = tokens.map( (token,idx) => new TokenToDisplay(token, startIndex + idx, tokenData, this.columnHeaders, annotations) );

          return tokens;
          // let range = tokenData.map( (tokensArr) =>
          //   tokensArr.map( (tokenId) => tokenId - startIndex )
          // );

          // let retval = [
          //   // Before first match
          //   // Revert when in table
          //   // tokens.filter((_, index) => index < range[0][0]).reverse(),
          //   tokens.filter((_, index) => index < range[0][0])
          // ];

          // for (let index = 0; index < range.length; index++) {
          //   retval.push(
          //     tokens.filter(
          //       (_, tokenIndex) =>
          //         tokenIndex >= range[index][0] &&
          //         tokenIndex <= range[index].at(-1)
          //     )
          //   );
          //   // Context between forms
          //   if (index + 1 < range.length) {
          //     retval.push(
          //       tokens.filter(
          //         (_, tokenIndex) =>
          //           tokenIndex > range[index].at(-1) &&
          //           tokenIndex < range[index + 1][0]
          //       )
          //     );
          //   }
          // }

          // // After last form
          // retval.push(tokens.filter((_, index) => index > range.at(-1).at(-1)));
          // retval.push(range);
          // return retval;
        });
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
