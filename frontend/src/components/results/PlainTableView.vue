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
          :class="resultIndex == this.selectedLine ? 'selected' : ''"
          @mousemove="hoverResultLine(resultIndex)"
          @mouseleave="hoverResultLine(null)"
          @click="selectedLine = resultIndex"
        >
          <td scope="row" class="results">
            <span :title="$t('common-copy-clipboard')" @click="copyToClip(item)" class="action-button">
              <FontAwesomeIcon :icon="['fas', 'copy']" />
            </span>
            <span
              v-if="'mediaSlots' in corpora.corpus.meta"
              class="timetag"
              :title="meta[data[resultIndex][0]][corpora.corpus.firstClass.document].name"
            >
              {{
                this.getTimestamps(...this.getFrameRange(resultIndex, this.corpora.corpus.firstClass.segment)).join(" ")
              }}
            </span>
            <span :title="$t('common-play-audio')" @click="playAudio(resultIndex)" class="action-button" v-if="showAudio(resultIndex)">
              <FontAwesomeIcon :icon="['fas', 'play']" />
            </span>
            <span :title="$t('common-play-video')" @click="playVideo(resultIndex)" class="action-button" v-if="showVideo(resultIndex)">
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
          <td class="action-button"
            data-bs-toggle="modal"
            :data-bs-target="`#imageModal${randInt}`"
            @click="showImage(...getImage(resultIndex), this.meta[this.data[resultIndex][0]])"
            v-if="getImage(resultIndex)"
          >
            <FontAwesomeIcon :icon="['fas', 'image']" />
          </td>
          <td class="buttons">
            <button
              type="button"
              class="btn btn-secondary btn-sm"
              data-bs-toggle="modal"
              :data-bs-target="`#detailsModal${randInt}`"
              @click="showModal(resultIndex)"
            >
              {{ $t('common-details') }}
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
      :style="{
        top: `min(${stickMeta.y || popoverY}px, calc(100vh - 33vh))`,
        left: (stickMeta.x || popoverX) + 'px',
        overflowY: (stickMeta.x || stickMeta.y) ? 'scroll' : 'visible',
        maxHeight: '33vh',
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
                  <tr v-if="allowedMetaColums[layer].includes(meta_key) && (meta_value || meta_fold(layer))">
                    <td>{{ meta_key }}</td>
                    <td v-if="(corpora.corpus.layer[layer].attributes[meta_key]||{}).type == 'image'">
                      <span
                        data-bs-toggle="modal"
                        :data-bs-target="`#imageModal${randInt}`"
                        @click="showImage(meta_value, layer)"
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
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div
      class="modal fade modal-xl"
      :id="`imageModal${randInt}`"
      tabindex="-1"
      aria-labelledby="imageModalLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog modal-full">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="imageModalLabel">{{ $t('results-image-viewer') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              :aria-label="$t('common-close')"
            ></button>
          </div>
          <div class="modal-body text-start">
            <div class="modal-body-content">
              <ImageViewer
                :src="image.src"
                :name="image.name"
                :boxes="image.boxes"
                v-if="image"
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
import ImageViewer from "@/components/ImageViewer.vue";
import PaginationComponent from "@/components/PaginationComponent.vue";
import ResultsDetailsModalView from "@/components/results/DetailsModalView.vue";
import { useNotificationStore } from "@/stores/notificationStore";
import Utils from "@/utils.js";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import config from "@/config";

// import WaveSurfer from 'wavesurfer.js'
// import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'

class TokenToDisplay {
  constructor(tokenArray, index, groups, columnHeaders, annotations) {
    if (!(tokenArray instanceof Array) || tokenArray.length < 1)
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
  emits: ["updatePage", "hoverResultLine", "playMedia"],
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
      groups: this.data ? this.getGroups(this.data[0], true) : [],
      randInt: Math.floor(Math.random() * 1000),
      playIndex: -1,
      image: null,
      selectedLine: -1
    };
  },
  components: {
    ImageViewer,
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
      this.currentMeta = {...this.meta[sentenceId]};
      for (let layer in this.currentMeta) {
        const submeta = this.currentMeta[layer].meta;
        if (!submeta || (this.corpora.corpus.mapping[layer]||{}).hasMeta === false) continue
        delete this.currentMeta[layer].meta;
        for (let k in submeta) {
          if (k in this.currentMeta[layer]) continue;
          this.currentMeta[layer][k] = submeta[k];
        }
        for (let k in this.currentMeta[layer]) {
          const isString = typeof(submeta[k]) == "string";
          if (isString)
            this.currentMeta[layer][k] = this.currentMeta[layer][k].trim();
          if (isString && this.currentMeta[layer][k].match(/^0+(\.0+)?$/))
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
      for (let [layerName, props] of Object.entries(this.corpora.corpus.layer)) {
        let attrs = props.attributes || {};
        if ("meta" in attrs)
          attrs = {attrs, ...attrs.meta};
        for (let [aname, aprops] of Object.entries(attrs||{}))
          if (aprops.type == "image") return [
            this.meta[this.data[resultIndex][0]][layerName][aname],
            layerName
          ];
      }
      return null;
    },
    showImage(filename, imageLayer, meta=null) {
      if (meta===null)
        meta = this.currentMeta;
      if (!meta) return;
      const boxes = [];
      const colors = ["green","blue","orange","pink","brown"];
      let image_offset = [];
      let color = 1;
      for (let [layer, props] of Object.entries(meta||{})) {
        if (!props.xy_box)
          continue;
        let xy_box = props.xy_box.match(/\d+/g).map(v=>parseInt(v))
        if (xy_box[0] > xy_box[2])
          xy_box = [xy_box[2], xy_box[3], xy_box[0], xy_box[1]];
        if (imageLayer && imageLayer == layer) {
          image_offset = xy_box.slice(0,2);
          continue;
        }
        if (!this.corpora.corpus.layer[layer].anchoring.location)
          continue;
        boxes.push([...xy_box, colors[color % colors.length]]);
        color++;
      }
      for (let n = 0; image_offset.length && n < boxes.length; n++) {
        boxes[n][0] -= image_offset[0];
        boxes[n][1] -= image_offset[1];
        boxes[n][2] -= image_offset[0];
        boxes[n][3] -= image_offset[1];
      }
      this.image = {
        name: filename.replace(/\.[^.]+$/,""),
        src: this.baseMediaUrl + filename,
        boxes: boxes
      };
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
      this.$refs.audioplayer.pause();
      resultIndex = resultIndex + (this.currentPage - 1) * this.resultsPerPage;
      const sentenceId = this.data[resultIndex][0];
      let meta = this.meta[sentenceId];
      if (meta) {
        // corpus tamplete,
        let documentId = meta[this.corpora.corpus.firstClass.document].id;
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
      else if (typeof(meta_obj) == "string")
        ret = meta_obj
      else
        ret = Utils.dictToStr(meta_obj, {addTitles: true, reorder: x=>x[0]=="id"}); // small hack to put id first
      return ret;
    },
    meta_fold(layer, flip) {
      this.currentMeta._unfolded = (this.currentMeta._unfolded || {});
      if (flip)
        this.currentMeta._unfolded[layer] = !this.currentMeta._unfolded[layer];
      return this.currentMeta._unfolded[layer];
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
