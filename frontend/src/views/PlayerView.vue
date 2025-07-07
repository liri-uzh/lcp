<template>
  <div class="player mb-5">
    <div class="container mt-4">
      <div class="row">
        <div class="col-5">
          <label class="form-label">{{ $t('common-corpus') }}</label>
          <select v-model="selectedCorpora" class="form-select">
            <option v-for="corpora in corpusList" :value="corpora" v-html="corpora.name" :key="corpora.value"></option>
          </select>
        </div>
        <!--<div class="col-5">
          <label class="form-label">Document</label>
          <!- - <span v-if="loading">Loading ...</span> - ->
          <select v-model="currentDocument" class="form-select">
            <option
              v-for="document in corpusData.filter(corpus => Object.values(documentDict).includes(corpus[1]))"
              :value="document"
              v-html="document[1]"
              :key="document[0]"
            ></option>
          </select>
        </div>-->
      </div>
      <div class="row mt-4" v-if="selectedCorpora">
        <div class="col">
          <nav>
            <div class="nav nav-tabs" id="nav-tab" role="tablist">
              <button v-for="document in corpusData.filter(corpus => Object.values(documentDict).includes(corpus[1]))"
                :key="document[0]" class="nav-link"
                :class="currentDocument && currentDocument[2] == document[2] ? 'active' : ''"
                :id="`nav-${document[0]}-tab`" data-bs-toggle="tab" :data-bs-target="`#nav-${document[0]}`"
                type="button" role="tab" @click="setDocument(document)" :aria-controls="`nav-${document[0]}`"
                aria-selected="true">
                {{ document[1] }}
              </button>
            </div>
          </nav>
          <!-- <div class="tab-content pt-3" id="nav-tabContent">
            <div
              v-for="(document, index) in corpusData.filter(corpus => Object.values(documentDict).includes(corpus[1]))"
              :key="document[0]"
              class="tab-pane fade"
              :class="index == -1 ? 'active show' : ''"
              :id="`nav-${document[0]}`"
              role="tabpanel"
              aria-labelledby="nav-results-tab"
            >
            </div>
          </div> -->
        </div>
      </div>
    </div>

    <!-- <div id="eventdrops-demo" style="width: 90%" class="mt-4"></div> -->

    <div v-if="currentDocument">
      <div class="container mt-4 mb-4">
        <div class="video-box">
          <div class="video-text" v-html="subtext"></div>
          <div :class="mainVideo == 1 ? 'active' : ''">
            <video ref="videoPlayer1" @timeupdate="timeupdate" @canplay="videoPlayer1CanPlay">
              <source :src="baseMediaUrl + currentDocument[2][0]" type="video/mp4" />
            </video>
          </div>
          <div :class="mainVideo == 2 ? 'active' : ''" v-if="currentDocument[2].length > 1">
            <video ref="videoPlayer2">
              <source :src="baseMediaUrl + currentDocument[2][1]" type="video/mp4" />
            </video>
          </div>
          <div :class="mainVideo == 3 ? 'active' : ''" v-if="currentDocument[2].length > 2">
            <video ref="videoPlayer3">
              <source :src="baseMediaUrl + currentDocument[2][2]" type="video/mp4" />
            </video>
          </div>
          <div :class="mainVideo == 4 ? 'active' : ''" v-if="currentDocument[2].length > 3">
            <video ref="videoPlayer4">
              <source :src="baseMediaUrl + currentDocument[2][3]" type="video/mp4" />
            </video>
          </div>
        </div>
      </div>

      <div class="container mt-4 mb-4">
        <div class="btn-group" role="group">
          <button type="button" class="btn btn-sm btn-primary" @click="playerFromStart">
            <FontAwesomeIcon :icon="['fas', 'backward-step']" />
          </button>
          <button type="button" class="btn btn-sm btn-primary">
            <FontAwesomeIcon :icon="['fas', 'backward']" />
          </button>
          <button type="button" class="btn btn-sm btn-primary active" @click="playerStop" v-if="playerIsPlaying">
            <FontAwesomeIcon :icon="['fas', 'pause']" />
          </button>
          <button type="button" class="btn btn-sm btn-primary" @click="playerPlay" v-else>
            <FontAwesomeIcon :icon="['fas', 'play']" />
          </button>
          <button type="button" class="btn btn-sm btn-primary">
            <FontAwesomeIcon :icon="['fas', 'forward']" />
          </button>
        </div>
        <div class="btn-group ms-1" role="group">
          <!-- <button
            type="button"
            class="btn btn-sm btn-primary"
            @click="playerVolumeDown"
          >
            <FontAwesomeIcon :icon="['fas', 'volume-down']" />
          </button>
          <button
            type="button"
            class="btn btn-sm btn-primary"
            @click="playerVolumeUp"
          >
            <FontAwesomeIcon :icon="['fas', 'volume-up']" />
          </button> -->
          <button type="button" class="btn btn-sm btn-primary" @click="playerVolumeMute">
            <div style="width: 11px; text-align: left">
              <FontAwesomeIcon v-if="volume == 0" :icon="['fas', 'volume-xmark']" />
              <FontAwesomeIcon v-else-if="volume > 0.9" :icon="['fas', 'volume-high']" />
              <FontAwesomeIcon v-else :icon="['fas', 'volume-low']" />
            </div>
          </button>

          <span class="btn btn-sm btn-primary pt-0 pb-0">
            <input type="range" class="form-range" v-model="volume" min="0" max="1" step="0.05" style="height: 2px" />
          </span>
          <span class="btn btn-sm btn-primary" style="width: 37px">
            <small>{{ parseInt(volume * 100, 10) }}</small>
          </span>
          <!-- <input
            type="range"
            class="form-range mt-1 ms-1"
            v-model="volume"
            min="0"
            max="1"
            step="0.001"
          />
          -->
        </div>
        <div class="btn-group ms-1" role="group">
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" @click="playerFrameDown(5)">
            -5
          </button>
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" @click="playerFrameDown(1)">
            -1
          </button>
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" @click="playerFrameUp(1)">
            +1
          </button>
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" @click="playerFrameUp(5)">
            +5
          </button>
          <!-- <button type="button" class="btn btn-sm btn-primary" @click="playerFrame100"><div class="icon-number">F100</div></button>
          <button type="button" class="btn btn-sm btn-primary" @click="playerSetTime"><div class="icon-number">Set time 10</div></button> -->
        </div>
        <div class="btn-group ms-1" role="group">
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" :class="playerSpeed == 0.5 ? 'active' : ''"
            @click="playerSetSpeed(0.5)">
            0.5x
          </button>
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" :class="playerSpeed == 1 ? 'active' : ''"
            @click="playerSetSpeed(1)">
            1x
          </button>
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" :class="playerSpeed == 1.5 ? 'active' : ''"
            @click="playerSetSpeed(1.5)">
            1.5x
          </button>
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" :class="playerSpeed == 2 ? 'active' : ''"
            @click="playerSetSpeed(2)">
            2x
          </button>
          <button type="button" class="btn btn-sm btn-primary btn-text-icon" :class="playerSpeed == 3 ? 'active' : ''"
            @click="playerSetSpeed(3)">
            3x
          </button>
        </div>
        <div class="btn-group ms-1" role="group">
          <button type="button" class="btn btn-sm btn-text-icon"
            :class="mainVideo == 1 ? 'active btn-primary' : 'btn-secondary'" @click="playerMainVideo(1)">
            V1
          </button>
          <button type="button" class="btn btn-sm btn-text-icon" v-if="currentDocument[2].length > 1"
            :class="mainVideo == 2 ? 'active btn-primary' : 'btn-secondary'" @click="playerMainVideo(2)">
            V2
          </button>
          <button type="button" class="btn btn-sm btn-text-icon" v-if="currentDocument[2].length > 2"
            :class="mainVideo == 3 ? 'active btn-primary' : 'btn-secondary'" @click="playerMainVideo(3)">
            V3
          </button>
          <button type="button" class="btn btn-sm btn-text-icon" v-if="currentDocument[2].length > 3"
            :class="mainVideo == 4 ? 'active btn-primary' : 'btn-secondary'" @click="playerMainVideo(4)">
            V4
          </button>
        </div>
        <div class="btn-group ms-1" role="group">
          <button type="button" class="btn btn-sm btn-text-icon"
            :class="mainAudio == 1 ? 'active btn-primary' : 'btn-light'" @click="playerMainAudio(1)">
            A1
          </button>
          <button type="button" class="btn btn-sm btn-text-icon" v-if="currentDocument[2].length > 1"
            :class="mainAudio == 2 ? 'active btn-primary' : 'btn-secondary'" @click="playerMainAudio(2)">
            A2
          </button>
          <button type="button" class="btn btn-sm btn-text-icon" v-if="currentDocument[2].length > 2"
            :class="mainAudio == 3 ? 'active btn-primary' : 'btn-secondary'" @click="playerMainAudio(3)">
            A3
          </button>
          <button type="button" class="btn btn-sm btn-text-icon" v-if="currentDocument[2].length > 3"
            :class="mainAudio == 4 ? 'active btn-primary' : 'btn-secondary'" @click="playerMainAudio(4)">
            A4
          </button>
        </div>
      </div>
      <div class="container mt-4">
        <div class="row mt-2 mb-4">
          <div class="col col-md-2">
            <label for="timePicker">{{ $t('common-go-to-time') }}:</label>
            <div v-if="currentMediaDuration > 0">
              <VueDatePicker v-model="selectedTime" time-picker enable-seconds format="HH:mm:ss" :min-time="minTime"
                :start-time="startTime" @update:model-value="handleDatePickerChange"></VueDatePicker>
            </div>
            <div v-else>
              <input type="text" disabled :placeholder="`${$t('common-loading-video-duration')}...`" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col" @click="timelineClick">
            <div class="progress" style="height: 10px; width: 100%" ref="timeline">
              <div class="progress-bar bg-danger" role="progressbar" :style="'width: ' + progress + '%'"
                aria-valuenow="25" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
          </div>
        </div>
        <!-- New: Time picker for seeking -->
        <div class="row mb-3 mt-2">
          <div class="col">
            <!-- Percentage: <span v-html="progress.toFixed(2)" />% -->
            {{ $t('common-frame') }}:
            <span v-html="parseInt(currentFrame, 10)" />&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {{ $t('common-time') }}: <span
              v-html="currentTime" />
          </div>
        </div>
      </div>
      <div id="timelinePopin" ref="timelinePopin" v-if="timelineEntry" :style="_getTimelinePopinXY()"
        @mouseleave="_annotationLeave">
        <div v-for="(entry, index) in timelineEntry" :key=index>
          <div class="header" v-html=entry[0]></div>
          <div v-html=entry[1]></div>
        </div>
      </div>
      <TimelineView v-if="Object.keys(currentDocumentData).length > 0 && loadingDocument == false"
        :data="currentDocumentData" :mediaDuration="currentMediaDuration" :playerIsPlaying="playerIsPlaying"
        :playerCurrentTime="playerCurrentTime" @updateTime="_playerSetTime" @annotationEnter="_annotationEnter"
        @annotationLeave="_annotationLeave" :key="documentIndexKey" />
      <div v-else-if="loadingDocument == true">
        {{ $t('common-loading-data') }}...
      </div>
      <hr />

      <div class="container mt-4">
        <div class="row">
          <div class="col-6">
            <div class="form-floating mb-3">
              <nav>
                <div class="nav nav-tabs" id="nav-tab" role="tablist">
                  <button class="nav-link active" id="nav-dqd-tab" data-bs-toggle="tab" data-bs-target="#nav-dqd"
                    type="button" role="tab" aria-controls="nav-dqd" aria-selected="true" @click="currentTab = 'dqd'">
                    DQD
                  </button>
                  <button class="nav-link" id="nav-json-tab" data-bs-toggle="tab" data-bs-target="#nav-json"
                    type="button" role="tab" aria-controls="nav-json" aria-selected="false"
                    @click="currentTab = 'json'">
                    JSON
                  </button>
                </div>
              </nav>
              <div class="tab-content" id="nav-tabContent">
                <div class="tab-pane fade show active pt-3" id="nav-dqd" role="tabpanel"
                  aria-labelledby="nav-results-tab">
                  <EditorView :query="queryDQD" :corpora="selectedCorpora" @update="updateQueryDQD"
                    @submit="submitQuery" :key="editorIndex" />
                  <p class="error-text text-danger mt-3" v-if="isQueryValidData && isQueryValidData.valid != true">
                    {{ isQueryValidData.error }}
                  </p>
                </div>
                <div class="tab-pane fade pt-3" id="nav-json" role="tabpanel" aria-labelledby="nav-stats-tab">
                  <textarea class="form-control query-field" placeholder="Query (e.g. test.*)" :class="isQueryValidData == null || isQueryValidData.valid == true
                    ? 'ok'
                    : 'error'
                    " v-model="query"></textarea>
                  <!-- <label for="floatingTextarea">Query</label> -->
                  <p class="error-text text-danger" v-if="isQueryValidData && isQueryValidData.valid != true">
                    {{ isQueryValidData.error }}
                  </p>
                </div>
              </div>
            </div>
            <div class="form-floating mb-3">
              <!-- <textarea
                class="form-control query-field"
                style="height: 200px"
                placeholder="Query (e.g. test.*)"
                v-model="query"
              ></textarea>
              <label for="floatingTextarea">Query</label> -->
            </div>
            <button type="button" @click="submitQuery" class="btn btn-primary me-1" :disabled="(selectedCorpora && selectedCorpora.length == 0) ||
              loading ||
              (isQueryValidData != null && isQueryValidData.valid == false) ||
              !query
              ">
              <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
              {{ $t('common-submit') }}
            </button>
            <button v-if="loading" type="button" @click="stop" :disabled="loading == false" class="btn btn-primary">
              {{ $t('common-stop') }}
            </button>
            <br />
            <br />
            {{ $t('load-example-query') }}:
            <button type="button" @click="setExample(1)" class="btn btn-sm btn-secondary ms-1">
              1
            </button>
            <button type="button" @click="setExample(2)" class="btn btn-sm btn-secondary ms-1">2</button>
            <button type="button" @click="setExample(3)" class="btn btn-sm btn-secondary ms-1">
              3
            </button>
            <!-- <button
              type="button"
              @click="setExample(4)"
              class="btn btn-sm btn-secondary ms-1"
            >
              4
            </button> -->
          </div>
          <div class="col-6" v-if="WSDataResults">
            <!-- Total progress
            <div class="progress mb-2">
              <div
                class="progress-bar"
                :class="
                  loading ? 'progress-bar-striped progress-bar-animated' : ''
                "
                role="progressbar"
                aria-label="Basic example"
                :style="`width: ${percentageTotalDone}%`"
                :aria-valuenow="percentageTotalDone"
                aria-valuemin="0"
                aria-valuemax="100"
              >
                {{ percentageTotalDone.toFixed(2) }}%
              </div>
            </div> -->
            <span v-if="WSDataResults">
              <ul class="list-no-bullets">
                <li v-for="(result, index) in currentPageResults" :key="index" class="cursor-pointer hover-opacity"
                  @click="resultClick(result, index)">
                  <div class="row">
                    <div class="col-2">
                      <span class="badge bg-secondary" v-html="frameNumberToTimeInResults(result, index)"></span>
                    </div>
                    <div class="col">
                      <span class="text-bold" v-html="contextWithHighlightedEntities(result, index)" />
                      <span v-html="otherEntityInfo(result, index)"></span>
                    </div>
                    <div class="col-1" :title="documentDict[docIdFromFrame(frameFromResult(result, index))]">
                      <span v-html="documentDict[docIdFromFrame(frameFromResult(result, index))]"></span>
                      <!-- <br>
                      <span v-html="result[4]"></span> -->
                    </div>
                  </div>
                </li>
              </ul>
              <PaginationComponent :resultCount="WSDataResults.result[1].length" :resultsPerPage="resultsPerPage"
                :currentPage="currentPage" @update="updatePage" :key="WSDataResults.result[1].length"
                :loading="loading" />
            </span>
            <!-- <span v-else-if="queryData == 1"></span> -->
            <span v-else>{{ $t('common-loading') }}...</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import { useWsStore } from "@/stores/wsStore";

import config from "@/config";
import Utils from "@/utils.js";
import EditorView from "@/components/EditorView.vue";
import TimelineView from "@/components/videoscope/TimelineView.vue";
import PaginationComponent from "@/components/PaginationComponent.vue";

import VueDatePicker from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css';

const urlRegex = /(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*))/g;

export default {
  data() {
    return {
      preselectedCorporaId: this.$route.params.id,
      selectedCorpora: null,
      currentDocument: null,
      currentDocumentData: null,
      currentMediaDuration: 0,
      documentIndexKey: 0,
      loadingDocument: false,
      loadingMedia: false,
      isQueryValidData: null,
      loading: false,
      failedStatus: false,
      WSDataResults: null,

      resultsPerPage: 20,
      currentPage: 1,

      percentageTotalDone: 0,
      progress: 0,
      chart: null,
      editorIndex: 0,
      currentFrame: 0,
      currentTime: "",
      subtitles: {},
      subtext: "",
      playerIsPlaying: false,
      playerCurrentTime: 0,
      playerSpeed: 1,
      updateTimer: null,
      mainVideo: 1,
      mainAudio: 1,
      volume: 0.5,
      frameRate: 25.0,

      timelineEntry: null,

      selectedTime: { hours: 0, minutes: 0, seconds: 0 }, // initialize to 00:00:00
      minTime: { hours: 0, minutes: 0, seconds: 0 },
      startTime: { hours: 0, minutes: 0, seconds: 0 },
      // maxTime: {hours: 0, minutes: 0, seconds: 0},

      setResultTimes: null,
      query: "",
      queryDQD: '',
      corpusData: [],
      documentDict: {},
    };
  },
  components: {
    EditorView,
    PaginationComponent,
    TimelineView,
    VueDatePicker,
  },
  computed: {
    ...mapState(useCorpusStore, ["queryData", "corpora"]),
    ...mapState(useUserStore, ["userData", "roomId"]),
    ...mapState(useWsStore, ["messages"]),
    corpusList() {
      return this.corpora
        ? this.corpora.map((corpus) => {
          return {
            name: corpus.meta.name,
            value: corpus.meta.id,
            corpus: corpus,
          };
        })
        : [];
    },
    currentPageResults() {
      let start = this.resultsPerPage * (this.currentPage - 1);
      let end = start + this.resultsPerPage;
      return this.WSDataResults.result[1]
        .filter((row, rowIndex) => {
          return rowIndex >= start && rowIndex < end;
        })
    },
    baseMediaUrl() {
      let retval = ""
      if (this.selectedCorpora) {
        retval = `${config.baseMediaUrl}${this.selectedCorpora.corpus.schema_path}/`
      }
      return retval
    },
    // Compute the maximum time based on the media's duration
    maxTime() {
      const duration = this.currentMediaDuration || 0;
      const hours = Math.floor(duration / 3600);
      const minutes = Math.floor((duration % 3600) / 60);
      const seconds = Math.floor(duration % 60);
      return { hours, minutes, seconds };
    },
    // Sets the available date-picker range from "00:00:00" to the media's duration.
    timePickerOptions() {
      const duration = this.currentMediaDuration > 0
        ? this.currentMediaDuration
        : 1;
      return {
        start: "00:00:00",
        end: this.formatSeconds(duration),
        step: "00:00:01"
      };
    }
  },
  methods: {
    setDocument(document) {
      this.currentDocument = document;
    },
    otherEntityInfo(result, index) {
      index = 0; // hard-coded for now
      // const ret = [];
      // const template = "{layer}: <b><span>{value}</span></b>";
      // const context = this.WSDataResults.result[0].result_sets[index].attributes.find(a=>a.name == "identifier");
      // const entities = this.WSDataResults.result[0].result_sets[index].attributes.find(a=>a.name == "entities");
      return ([] || result[index]).join("<br>");
    },
    contextWithHighlightedEntities(result, index) {
      index = 0; // hard-coded for now
      const n_entities = this.WSDataResults.result[0].result_sets[index].attributes.findIndex(a => a.name == "entities");
      const context = [];
      const offset = parseInt(this.WSDataResults.result[-1][result[0]][0]);
      const segment_layer_name = this.selectedCorpora.corpus.firstClass.segment;
      const column_names = this.selectedCorpora.corpus.mapping.layer[segment_layer_name].prepared.columnHeaders;
      const form_n = column_names.indexOf("form");
      const toks = this.WSDataResults.result[-1][result[0]][1].map(x => x[form_n]);
      for (let n in toks) {
        if (n_entities < 0 || !(result[n_entities] || []).includes(offset + parseInt(n))) context.push(toks[n]);
        else context.push("<span style='color:brown;'>" + toks[n] + "</span>");
      }
      return context.join(' ')
    },
    frameNumberToTime(frameNumber) {
      let seconds = Utils.frameNumberToSeconds(frameNumber);
      return Utils.msToTime(seconds);
    },
    frameNumberToTimeInResults(result, index) {
      let docId = this.docIdFromFrame(this.frameFromResult(result, index))
      return this.frameNumberToTime(
        parseInt(this.frameFromResult(result, index)[0])
        -
        parseInt(this.corpusData.find(c => c[0] == docId)[3][0])
      )
    },
    frameFromResult(result, index) {
      // if (index >= this.WSDataResults.result[0].result_sets.length)
      //   return [0,0];
      index = 0; // hard-coded for now
      const resAttrs = this.WSDataResults.result[0].result_sets[index].attributes;
      for (let n in resAttrs)
        if (resAttrs[n].name == "frame_ranges")
          return result[n];
      return [0, 0];
    },
    updatePage(currentPage) {
      this.currentPage = currentPage;
    },
    // docIdFromFrame(frame) {
    //   let [minFrame, maxFrame] = frame;
    //   return this.corpusData.find(c=>c[3][0] <= minFrame && maxFrame <= c[3][1])[0];
    // },
    docIdFromFrame(frame) {
      // Binary search
      let [minFrame, maxFrame] = frame;
      let left = 0, right = this.corpusData.length - 1;

      while (left <= right) {
        let mid = Math.floor((left + right) / 2);
        let [start, end] = this.corpusData[mid][3];

        if (start <= minFrame && maxFrame <= end) {
          return this.corpusData[mid][0];
        } else if (minFrame < start) {
          right = mid - 1;
        } else {
          left = mid + 1;
        }
      }
      return null;
    },
    resultClick(result, index) {
      // if (index >= this.WSDataResults.result[0].result_sets.length)
      //   return;
      index = 0; // hard-coded for now
      const frameFromResult = this.frameFromResult(result, index);
      const doc_result_id = this.docIdFromFrame(frameFromResult);
      const doc_result = this.corpusData.filter(corpus => corpus[0] == doc_result_id)[0];
      const adjustedFrames = frameFromResult.map(x => parseInt(x) - parseInt(doc_result[3][0]));
      let [start, end] = adjustedFrames.map(x => Utils.frameNumberToSeconds(x) / 1000);
      if (this.currentDocument == doc_result) {
        this._playerSetTime(start);
        window.scrollTo(0, 120);
        this.playerPlay(end);
      } else {
        //   // this.currentDocument = this.corpusData[result[2] - 1];
        // this.currentDocument = this.documentDict[result[2]];
        this.setResultTimes = [start, end];
        // TODO: should be fixed - corpusData changed
        this.currentDocument = doc_result;
      }
    },
    playerPlay(end = 0) {
      const n_players = [1, 2, 3, 4];
      for (let n of n_players) {
        const player = this.$refs['videoPlayer' + n];
        if (!player)
          continue
        if (end >= 0) {
          end = Math.min(end, player.duration);
          const handler = () => {
            if (player.currentTime < end) return;
            this.playerStop();
          };
          player.addEventListener("pause", () => player.removeEventListener("timeupdate", handler), { once: true });
          player.addEventListener("timeupdate", handler);
        }
        player.play();
      }
      this.playerIsPlaying = true;
      // this.$refs.timeline.player.playing = true;
    },
    playerStop() {
      if (this.$refs.videoPlayer1) {
        this.$refs.videoPlayer1.pause();
      }
      if (this.$refs.videoPlayer2) {
        this.$refs.videoPlayer2.pause();
      }
      if (this.$refs.videoPlayer3) {
        this.$refs.videoPlayer3.pause();
      }
      if (this.$refs.videoPlayer4) {
        this.$refs.videoPlayer4.pause();
      }
      this.playerIsPlaying = false;
      // this.$refs.timeline.player.playing = false;
    },
    playerFromStart() {
      this._playerSetToFrame(0);
    },
    playerVolumeUp() {
      this.volume = Math.max(0, this.volume + 0.05);
      this._setVolume();
    },
    playerVolumeDown() {
      this.volume = Math.max(0, this.volume - 0.05);
      this._setVolume();
    },
    playerVolumeMute() {
      this._setVolume(0);
    },
    playerFrameUp(value) {
      this.currentFrame =
        this.$refs.videoPlayer1.currentTime.toFixed(5) * this.frameRate;
      this._playerSetToFrame(this.currentFrame + value);
    },
    _playerSetToFrame(frameNumber) {
      let value = (frameNumber / this.frameRate).toFixed(5);
      this._playerSetTime(value);
    },
    // _playerSetTime(value) {
    //   const n_players = [1, 2, 3, 4];
    //   for (let n in n_players) {
    //     const player = this.$refs["videoPlayer" + n];
    //     if (!player) continue
    //     const time = Math.min(value, (isNaN(player.duration) ? 0.1 : player.duration) - 0.1);
    //     player.currentTime = time;
    //     this.playerCurrentTime = time;
    //   }
    // },
    _playerSetTime(value) {
      const players = [1, 2, 3, 4];
      for (let n of players) {
        const player = this.$refs[`videoPlayer${n}`];
        if (!player) continue;
        // Ensure the time does not exceed the player's duration
        const time = Math.min(
          value,
          player.duration ? player.duration - 0.1 : value
        );
        player.currentTime = time;
        this.playerCurrentTime = time;
      }
    },
    playerFrameDown(value) {
      this.currentFrame =
        this.$refs.videoPlayer1.currentTime.toFixed(5) * this.frameRate;
      this._playerSetToFrame(this.currentFrame - value);
    },
    playerSetSpeed(speed) {
      if (this.$refs.videoPlayer1) {
        this.$refs.videoPlayer1.playbackRate = speed;
      }
      if (this.$refs.videoPlayer2) {
        this.$refs.videoPlayer2.playbackRate = speed;
      }
      if (this.$refs.videoPlayer3) {
        this.$refs.videoPlayer3.playbackRate = speed;
      }
      if (this.$refs.videoPlayer4) {
        this.$refs.videoPlayer4.playbackRate = speed;
      }
      this.playerSpeed = speed;
    },
    // Helper to format seconds into HH:mm:ss
    formatSeconds(seconds) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      const s = Math.floor(seconds % 60);
      return [h, m, s]
        .map((n) => n.toString().padStart(2, "0"))
        .join(":");
    },
    handleDatePickerChange(newTime) {
      if (newTime === null) {
        return;
      }

      // Convert the selected time (HH:mm:ss) to seconds.
      let seconds =
        newTime.hours * 3600 +
        newTime.minutes * 60 +
        newTime.seconds;

      console.log(newTime, seconds);

      // Clamp to video duration if available
      if (this.$refs.videoPlayer1 && this.$refs.videoPlayer1.duration) {
        seconds = Math.min(seconds, this.$refs.videoPlayer1.duration - 0.1);
      }
      // Use your existing helper method to update the player's time
      this._playerSetTime(seconds);
    },
    timeupdate() {
      try {
        this.currentFrame =
          this.$refs.videoPlayer1.currentTime.toFixed(5) * this.frameRate;
        this.currentTime =
          new Date(this.$refs.videoPlayer1.currentTime * 1000)
            .toISOString()
            .substring(14, 19) +
          "/" +
          new Date(this.$refs.videoPlayer1.duration * 1000)
            .toISOString()
            .substring(14, 19);
        this.progress =
          (this.$refs.videoPlayer1.currentTime /
            this.$refs.videoPlayer1.duration) *
          100;
      } catch {
        this.currentFrame = 0;
        this.progress = 0;
      }

      let filtered = Object.keys(this.subtitles).filter(
        (x) => x >= this.currentFrame
      );
      if (filtered.length) {
        this.subtext = this.subtitles[filtered[0]];
      }
      // if (this.$refs.timeline && this.$refs.videoPlayer1) {
      //   this.playerCurrentTime = this.$refs.videoPlayer1.currentTime;
      //   this.$refs.timeline.player.time = this.$refs.videoPlayer1.currentTime;
      // }
    },
    videoPlayer1CanPlay() {
      this.loadingMedia = false;
      this.currentMediaDuration = this.$refs.videoPlayer1.duration;
      this.$refs.videoPlayer1.addEventListener("pause", () => this.playerIsPlaying = false);
      if (this.setResultTimes) {
        const [start, end] = this.setResultTimes;
        this.setResultTimes = null;
        this._playerSetTime(start);
        this.playerPlay(end);
        window.scrollTo(0, 120);
      }
    },
    playerMainVideo(number) {
      this.mainVideo = number;
    },
    playerMainAudio(number) {
      this.mainAudio = number;
      this._setVolume();
    },
    timelineClick(event) {
      let percent =
        parseFloat(
          event.clientX - this.$refs.timeline.getBoundingClientRect().left
        ) / this.$refs.timeline.getBoundingClientRect().width;
      let time = this.$refs.videoPlayer1.duration * percent;
      if (this.$refs.videoPlayer1) {
        this.$refs.videoPlayer1.currentTime = time;
      }
      if (this.$refs.videoPlayer2) {
        this.$refs.videoPlayer2.currentTime = time;
      }
      if (this.$refs.videoPlayer3) {
        this.$refs.videoPlayer3.currentTime = time;
      }
      if (this.$refs.videoPlayer4) {
        this.$refs.videoPlayer4.currentTime = time;
      }
    },
    // calcSize(number) {
    //   let retVal = [320, 240]
    //   if (number == this.mainVideo) {
    //     retVal = [480, 320]
    //   }
    //   return retVal
    // },
    _setVolume(volume = null) {
      let _volume = volume != null ? volume : this.volume;
      if (this.$refs.videoPlayer1) {
        this.$refs.videoPlayer1.volume = this.mainAudio == 1 ? _volume : 0;
      }
      if (this.$refs.videoPlayer2) {
        this.$refs.videoPlayer2.volume = this.mainAudio == 2 ? _volume : 0;
      }
      if (this.$refs.videoPlayer3) {
        this.$refs.videoPlayer3.volume = this.mainAudio == 3 ? _volume : 0;
      }
      if (this.$refs.videoPlayer4) {
        this.$refs.videoPlayer4.volume = this.mainAudio == 4 ? _volume : 0;
      }
      this.volume = _volume
    },
    _annotationEnter({ x, y, mouseX, mouseY, entry }) {
      this.timelinePopinY = Number(mouseY);
      this.timelinePopinX = Number(x);
      this.timelinePopinY = Number(y);
      this.timelinePopinX = Number(mouseX);
      this.timelineEntry = [
        ...Object.entries(entry).filter(kv => !(kv[0] in { frame_range: 1, char_range: 1, prepared: 1, meta: 1 })),
        ...Object.entries(entry.meta || {})
      ]
        .filter(kv => kv && kv[0] && kv[1])
        .map(([name, value]) => [name, value.replace(urlRegex, "<a href='$1' target='_blank'>$1</a>")]);
    },
    _annotationLeave() {
      this.timelineEntry = null;
    },
    _getTimelinePopinXY() {
      let { x, y } = document.querySelector("#timeline-svg").getBoundingClientRect();
      x += this.timelinePopinX + window.scrollX;
      y += this.timelinePopinY + window.scrollY;
      const bottom = window.scrollY + window.innerHeight, right = window.scrollX + window.innerWidth;
      const { width, height } = (
        this.$refs.timelinePopin
        || { getBoundingClientRect: () => Object({ width: 0, height: 0 }) }
      ).getBoundingClientRect();
      if (x + width > right)
        x = right - width;
      if (y + height > bottom)
        y = bottom - height;
      return { 'left': x + 'px', 'top': y + 'px' };
    },
    // loadData() {
    //   if (this.currentDocument) {
    //     this.mainVideo = 1;
    //     this.mainAudio = 1;
    //     this.subtitles = {};
    //     this.loading = true;
    //     this.playing = false;
    //     this._playerSetTime(0);
    //     useCorpusStore()
    //       .fetchDocument(this.currentDocument[0])
    //       .then((data) => {
    //         this.loadDataJobId = data.job;
    //       });
    //   }
    // },
    updateQueryDQD(query) {
      this.queryDQD = query
      this.validate()
    },
    updateQueryJSON(query) {
      console.log("Update JSON query", query)
      this.query = query
      // this.queryDQD = query;
      // this.validate();
    },
    async submitQuery() {
      this.WSDataResults = null;
      this.currentPage = 1;

      let data = {
        corpora: this.selectedCorpora.value,
        query: this.query,
        user: this.userId,
        room: this.roomId,
      }
      let retval = await useCorpusStore().fetchQuery(data);
      if (retval.status == "started") {
        this.loading = true;
        this.percentageDone = 0.001;
      }
    },
    onSocketMessage(data) {
      // let data = JSON.parse(event.data);
      // console.log("SOC", data)
      if (Object.prototype.hasOwnProperty.call(data, "action")) {
        if (data["action"] === "document") {
          this.documentData = data.document;
          let dataToShow = {};
          // TODO: replace what's hard-coded in this with reading 'tracks' from corpus_template
          let document_id = parseInt(this.currentDocument[0])
          if (!(this.selectedCorpora.value in { 115: 1 })) { // old tangram exception
            let tracks = this.selectedCorpora.corpus.tracks;
            dataToShow = {
              layers: Object.fromEntries(Object.entries(tracks.layers).map((e, n) => [n + 1, Object({ name: e[0] })])),
              tracks: {},
              document_id: document_id,
              groupBy: tracks.group_by
            };
            for (let gb of (tracks.group_by || [])) {
              if (!(gb in (data.document.global_attributes || {})))
                throw ReferenceError(`'${gb}' could not be found in global_attributes`);
              dataToShow[gb] = Object.fromEntries(data.document.global_attributes[gb].map(v => [v[gb + '_id'], v[gb]]))
            }
            for (let layer in data.document.layers) {
              tracks.layers[layer].split = tracks.layers[layer].split || [];
              const cols = data.document.structure[layer];
              const rows = data.document.layers[layer];
              for (let row of rows) {
                let trackName = layer;
                let content = {};
                for (let ncol in row) {
                  let name = cols[ncol];
                  let value = row[ncol];
                  if (tracks.layers[layer].split.find(s => name.toLowerCase().match(new RegExp(`^${s}(_id)?$`, 'i'))))
                    trackName = (isNaN(parseInt(value)) ? value : `${name.replace(/_id$/, '')} ${value}`) + ' ' + trackName;
                  else
                    content[name] = value;
                }
                let [ntrack, track] = Object.entries(dataToShow.tracks).find(nt => nt[1].name == trackName) || [null, null];
                if (ntrack === null) {
                  ntrack = Object.keys(dataToShow.tracks).length;
                  track = { name: trackName, layer: Object.keys(tracks.layers).indexOf(layer) + 1 };
                  track[layer] = [];
                }
                track[layer].push(content);
                dataToShow.tracks[ntrack] = track;
              }
            }
          }

          const segment_name = this.selectedCorpora.corpus.firstClass.segment;
          const column_names = this.selectedCorpora.corpus.mapping.layer[segment_name].prepared.columnHeaders;
          const form_n = column_names.indexOf("form");
          let timelineData = []

          // Sort by name
          let tracksNamesSorted = Object.values(dataToShow.tracks).sort((a, b) => {
            // TODO: hardcoded - use list from BR to order groups. Segements are hardcoded to be first
            let a_name = a.name.toLowerCase().replace(" segment", " aa_segment")
            let b_name = b.name.toLowerCase().replace(" segment", " aa_segment")
            if (a_name < b_name) {
              return -1;
            }
            if (a_name > b_name) {
              return 1;
            }
            return 0;
          });

          // Add group_by speaker
          if (this.selectedCorpora.corpus &&
            this.selectedCorpora.corpus.tracks &&
            this.selectedCorpora.corpus.tracks.group_by &&
            this.selectedCorpora.corpus.tracks.group_by[0] == "speaker"
          ) {
            let trackGroupCounter = {};
            let newTracksNamesSorted = [];
            tracksNamesSorted.forEach(track => {
              let groupName = track.name.split(" ").slice(0, 2).join(" ");
              if (!(groupName in trackGroupCounter)) {
                trackGroupCounter[groupName] = 0
                let speakerIndex = Object.keys(trackGroupCounter).length
                newTracksNamesSorted.push(new Proxy({
                  name: `Speaker ${speakerIndex}`,
                  layer: -1,
                  level: 0
                }, {}))
              }
              trackGroupCounter[groupName]++
              track.level = 1
              track.name = track.name.replace(groupName, "").trim()
              newTracksNamesSorted.push(track)
            })
            tracksNamesSorted = newTracksNamesSorted
          }

          // Generate timeline data
          tracksNamesSorted.forEach((track, key) => {
            let values = []
            if (track.layer != -1) {
              const keyName = dataToShow.layers[track.layer].name;
              const isSegment = keyName.toLowerCase() == segment_name.toLowerCase();

              for (const entry of track[keyName]) {
                const [startFrame, endFrame] = entry.frame_range
                let shift = this.currentDocument[3][0];
                let startTime = (parseFloat(startFrame - shift) / this.frameRate);
                let endTime = (parseFloat(endFrame - shift) / this.frameRate);
                const unitData = { x1: startTime, x2: endTime, l: key, entry: entry };
                if (isSegment)
                  unitData.n = entry.prepared.map(row => row[form_n]).join(" ");
                else {
                  let firstStringAttribute = Object.entries(
                    this.selectedCorpora.corpus.layer[keyName].attributes || {}
                  ).find(e => e[1].type in { text: 1, categorical: 1 });
                  if (firstStringAttribute)
                    unitData.n = entry[firstStringAttribute[0]];
                }
                values.push(unitData);
              }
            }

            timelineData.push({
              name: track.name,
              level: track.level || 0,
              heightLines: 1,
              values: values
            })
          })

          this.currentMediaDuration = this.$refs.videoPlayer1.duration;
          if (!this.currentMediaDuration && "doc" in this.documentData && "frame_range" in this.documentData.doc)
            this.currentMediaDuration = this.documentData.doc.frame_range.reduce((x, y) => y - x) / this.frameRate;
          this.currentDocumentData = timelineData;
          this.loadingDocument = false;
          this.documentIndexKey++;
          this._setVolume();
          return;
        }
        else if (data["action"] === "document_ids") {
          // console.log("DOC", data);
          // this.documentDict = data.document_ids
          this.documentDict = Object.fromEntries(Object.entries(data.document_ids).map(([id, props]) => [id, props.name]));
          this.corpusData = Object.entries(data.document_ids).map(([id, props]) => [id, props.name, Object.values(props.media), props.frame_range]);
          return;
        }
        else if (data["action"] === "validate") {
          // console.log("Query validation", data);
          if (data.kind == "dqd" && data.valid == true) {
            // console.log("Set query from server");
            this.query = JSON.stringify(data.json, null, 2);
          }
          this.isQueryValidData = data;
          return;
        }
        else if (data["action"] === "sentences") {
          this.failedStatus = false;
          if (this.WSDataResults && this.WSDataResults.first_job == data.first_job) {
            Object.keys(this.WSDataResults.result).forEach(key => {
              if (key > 0) {
                this.WSDataResults.result[key] = this.WSDataResults.result[key].concat(data.result[key])
              }
            })
            this.WSDataResults.result[-1] = {
              ...this.WSDataResults.result[-1],
              ...data.result[-1]
            }
          }
          else {
            this.WSDataResults = data;
          }
          return;
          // this.failedStatus = false;
          // this.WSDataResults = data;
          // return;
        } else if (data["action"] === "failed") {
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.value,
          });
        }
        else if (data["action"] === "timeout") {
          console.log("Query job expired", data);
          this.failedStatus = true;
          // this.submit(null, false, false);
          return;
        }
        else if (data["action"] === "query_error") {
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.info,
          });
        }
        if (["finished", "satisfied"].includes(data["status"]))
          this.loading = false;
      } else if (Object.prototype.hasOwnProperty.call(data, "status")) {
        if (data["status"] == "failed") {
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.value,
          });
        }
        if (data["status"] == "error") {
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.info,
          });
        }
      }
    },
    setExample(num) {
      console.log("setting example query", num);
      if (num == 1) {
        this.queryDQD = `Segment s

sequence@s
  Token t1
    upos = "DET"
  Token t2
    upos = "NOUN"

Gesture g1
  agent = s.agent
  type = "PG"
  start >= s.start - 3s
  end <= s.end + 3s

KWIC => plain
  context
    s
  entities
    t1
    t2
    g1

`
      }
      else if (num == 2) {
        this.queryDQD = `Segment s

sequence@s
  Token@s t1
    upos = "DET"
  Token@s t2
    upos = "NOUN"

Gesture g
  agent = s.agent
  type = /^(PG|OG|IG|UG)$/
  g.start >= s.start - 5s
  g.end <= s.end + 2s

KWIC => plain
  context
    s
  entities
    t1
    t2
    g

`
      }
      else if (num == 3) {
        this.queryDQD = `Segment s1
  agent.name = speaker_1

Token@s1 t1
  form = /[kK]opf/

Segment s2
  agent.name = "speaker_2"
  start >= s1.start
  end <= s1.end

Token@s2 t2
  form = "rechts"

KWIC => plain
  context
    s1
    s2
  entities
    t1
    t2

`
      }
      else if (num == 4) {
        this.queryDQD = `Document d

Gesture g1
  agent.name = "speaker_1"

NOT EXISTS
  Gesture g2
    agent.name = "speaker_2"
    start >= g1.start - 3s
    end <= g1.end + 3s

KWIC => plain
  context
    d
  entities
    g1

`
      }
      this.editorIndex++
      this.validate()
    },
    stop() {
      this.percentageDone = 0;
      this.percentageTotalDone = 0;
      this.failedStatus = false;
      this.$socket.sendObj({
        room: this.roomId,
        action: "stop",
        user: this.userId,
      });
      this.loading = false;
    },
    validate() {
      this.$socket.sendObj({
        room: this.roomId,
        action: "validate",
        user: this.userId,
        query: this.currentTab == "json" ? this.query : this.queryDQD + "\n",
      });
    },
    loadDocuments() {
      this.loadingDocument = true
      this.documentDict = {}
      this.currentDocumentData = {}
      this.currentMediaDuration = 0
      if (this.roomId && this.userId) {
        useCorpusStore().fetchDocuments({
          room: this.roomId,
          user: this.userId,
          corpora_id: this.selectedCorpora.value,
        })
      }
      else {
        setTimeout(() => this.loadDocuments(), 200)
      }
    },
    async loadDocument() {
      try {
        const checkVideoPlayer = r => {
          if (this.$refs.videoPlayer1) r();
          else window.requestAnimationFrame(() => checkVideoPlayer(r));
        }
        await new Promise(r => checkVideoPlayer(r));
        this.$refs.videoPlayer1.load();
        if (this.currentDocument[2].length > 1) {
          this.$refs.videoPlayer2.load();
        }
        if (this.currentDocument[2].length > 2) {
          this.$refs.videoPlayer3.load();
        }
        if (this.currentDocument[2].length > 3) {
          this.$refs.videoPlayer4.load();
        }
      } catch {
        console.log("Error player");
      }
      if (this.currentDocument) {
        this.currentDocumentData = {}
        this.loadingDocument = true
        this.loadingMedia = true
        this.timelineEntry = null
        // console.log("AA", this.currentDocument)
        useCorpusStore().fetchDocument({
          doc_id: this.currentDocument[0],
          corpora: [this.selectedCorpora.value],
          user: this.userId,
          room: this.roomId,
        });
      }
    },
  },
  mounted() {
    if (this.userData) {
      this.userId = this.userData.user.id;
      // this.connectToRoom();
      // this.stop();
      this.validate();
    }
    this._setVolume();
    window.addEventListener("keydown", (e) => {
      if (e.key == "ArrowLeft") {
        // key left
        this.playerFrameDown(25);
      } else if (e.key == "ArrowRight") {
        // key right
        this.playerFrameUp(25);
      }
    });
    this.setExample(1);
    if (this.selectedCorpora && this.selectedCorpora.corpus && this.selectedCorpora.corpus.sample_query)
      this.updateQueryDQD(this.selectedCorpora.corpus.sample_query);
  },
  unmounted() {
    if (this.updateTimer) {
      clearInterval(this.updateTimer);
    }
    // this.sendLeft();
  },
  watch: {
    playerIsPlaying: {
      handler() {
        if (this.updateTimer) {
          clearInterval(this.updateTimer);
        }
        if (this.playerIsPlaying) {
          this.updateTimer = setInterval(() => {
            this.playerCurrentTime = this.$refs.videoPlayer1.currentTime;
          }, 30);
        }
      },
      immediate: true,
    },
    corpora: {
      handler() {
        if (this.preselectedCorporaId) {
          let corpus = this.corpora.filter(corpus => corpus.meta.id == this.preselectedCorporaId)
          if (corpus.length) {
            this.selectedCorpora = {
              name: corpus[0].meta.name,
              value: corpus[0].meta.id,
              corpus: corpus[0],
            }
            if (corpus[0].sample_query)
              this.queryDQD = corpus[0].sample_query;
          }
          this.preselectedCorporaId = null
          this.loadDocuments()
        }
      },
      immediate: true,
      deep: true,
    },
    messages: {
      handler() {
        let _messages = this.messages;
        if (_messages.length > 0) {
          // console.log("WSM", _messages)
          _messages.forEach(message => this.onSocketMessage(message))
          useWsStore().clear();
        }
      },
      immediate: true,
      deep: true,
    },
    selectedCorpora() {
      this.loadDocuments()
      history.pushState(
        {},
        null,
        `/player/${this.selectedCorpora.value}/${this.selectedCorpora.corpus.shortname}`
      )
    },
    currentDocument() {
      this.loadDocument();
    },
    volume() {
      this._setVolume();
    },
    WSDataResults() {
      if (this.WSDataResults) {
        if (this.WSDataResults.percentage_done) {
          this.percentageDone = this.WSDataResults.percentage_done;
        }
        if (
          this.WSDataResults.total_results_so_far &&
          this.WSDataResults.projected_results
        ) {
          this.percentageTotalDone =
            (this.WSDataResults.total_results_so_far /
              this.WSDataResults.projected_results) *
            100;
        }
        if (["finished"].includes(this.WSDataResults.status)) {
          this.percentageDone = 100;
          this.percentageTotalDone = 100;
          this.loading = false;
        }
        if (["satisfied"].includes(this.WSDataResults.status)) {
          // this.percentageDone = this.WSDataResults.hit_limit/this.WSDataResults.projected_results*100.
          this.percentageDone = 100;
          this.loading = false;
        }
        // console.log("XXX", this.percentageTotalDone, this.percentageDone);
        if (this.WSDataResults.percentage_done >= 100) {
          this.loading = false;
        }
      }
    },
  },
};
</script>

<style scoped>
#nav-tab {
  height: 5em;
  display: flex;
  overflow: scroll;
}

video {
  margin-right: 3px;
  object-fit: fill;
  height: 140px;
}

.vertical-line {
  position: absolute;
  width: 1px;
  height: 56px;
  margin-top: -10px;
  background-color: rgb(114, 114, 114);
}

.progress-bar {
  border-radius: 4px;
}

.btn-text-icon {
  font-weight: bold;
  color: #fff;
  font-size: 12px;
  padding-top: 6px;
}

.video-text {
  position: absolute;
  bottom: 20px;
  width: 710px;
  left: 45px;
  color: #fff;
  font-weight: bold;
  user-select: none;
  font-size: 110%;
  text-align: center;
  background-color: #0000008c;
  padding: 2px;
}

.video-box {
  height: 450px;
  display: flex;
  flex-flow: column wrap;
  transition: 2s ease;
  position: relative;
  cursor: default;
}

.video-box>div {
  flex: 1 1 80px;
  margin: 1px;
}

.video-box>div.active {
  min-height: 100%;
  order: -1;
}

div.active video {
  height: 450px;
}

*>>>.drop {
  cursor: pointer;
}

.query-field {
  height: 328px;
}

.list-no-bullets {
  list-style-type: none;
}

.list-no-bullets li:hover {
  cursor: pointer;
  opacity: 0.8;
}

.list-no-bullets .col-1 {
  width: 20%;
  max-height: 2em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

#timelinePopin {
  position: absolute;
  width: 25em;
  min-height: 2em;
  max-height: 10em;
  overflow: scroll;
  left: 20vw;
  background-color: white;
  box-shadow: 2px 2px 20px 0px black;
  border-radius: 0.25em;
  z-index: 99;
}

#timelinePopin .header {
  font-weight: bold;
  background-color: lightgray;
}

@media screen and (max-width: 768px) and (orientation: landscape) {
  .video-box>div.active {
    max-width: calc(100vw - 78px) !important;
    order: -1;
  }
  
  video {
    max-width: 100vw !important;
    height: auto;
    display: block;
    width: 100%;
    height: auto;
    object-fit: contain;
    background: black; 
  }
}
</style>
