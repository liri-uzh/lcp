<template>
  <div class="player">
    <div class="container-fuild">
      <div class="row" v-if="selectedCorpora">
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
        <div class="col-12 col-md-4">
          <div class="mb-3 mt-3 text-center text-md-start">
            <button type="button" class="btn btn-primary" @click="$emit('switchToQueryTab')">{{ $t('common-query-corpus') }}</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="currentDocument">
      <div class="container-fluid mt-4 mb-4">
        <div
          :class="appType == 'video' ? 'video-box' : 'audio-box'"
          @click="playerTogglePlay"
          :data-is-playing="playerIsPlaying"
        >
          <div class="video-text" v-html="subtext" v-if="appType == 'video'"></div>
          <div class="video-play-button" v-if="appType == 'video'">
            <div class="button" :class="playerIsPlaying ? '' : 'play'">
              <span class="s1"></span>
            </div>
          </div>
          <!-- v-if="appType == 'video'" -->
          <div :class="mainVideo == 1 ? 'active' : ''">
            <video ref="videoPlayer1" @timeupdate="timeupdate" @canplay="videoPlayer1CanPlay"
              v-if="appType == 'video'">
              <source :src="baseMediaUrl + currentDocument[2][0]" type="video/mp4" />
            </video>
            <audio ref="videoPlayer1" @timeupdate="timeupdate" @canplay="videoPlayer1CanPlay"
              v-if="appType == 'audio'">
              <source :src="baseMediaUrl + currentDocument[2][0]" type="audio/mpeg" />
            </audio>
          </div>
          <div :class="mainVideo == 2 ? 'active' : ''" v-if="appType == 'video' && currentDocument[2].length > 1">
            <video ref="videoPlayer2">
              <source :src="baseMediaUrl + currentDocument[2][1]" type="video/mp4" />
            </video>
          </div>
          <div :class="mainVideo == 3 ? 'active' : ''" v-if="appType == 'video' && currentDocument[2].length > 2">
            <video ref="videoPlayer3">
              <source :src="baseMediaUrl + currentDocument[2][2]" type="video/mp4" />
            </video>
          </div>
          <div :class="mainVideo == 4 ? 'active' : ''" v-if="appType == 'video' && currentDocument[2].length > 3">
            <video ref="videoPlayer4">
              <source :src="baseMediaUrl + currentDocument[2][3]" type="video/mp4" />
            </video>
          </div>
        </div>
      </div>

      <div class="container-fluid mt-4 mb-4">
        <div class="d-flex flex-column flex-md-row gap-2">
          <div class="btn-group w-auto" role="group">
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
          <div class="btn-group w-auto" role="group">
            <button type="button" class="btn btn-sm btn-primary" @click="playerVolumeMute">
              <div style="width: 11px; text-align: left">
                <FontAwesomeIcon v-if="volume == 0" :icon="['fas', 'volume-xmark']" />
                <FontAwesomeIcon v-else-if="volume > 0.9" :icon="['fas', 'volume-high']" />
                <FontAwesomeIcon v-else :icon="['fas', 'volume-low']" />
              </div>
            </button>

            <span class="btn btn-sm btn-primary pt-0 pb-0">
              <input
                type="range"
                class="form-range"
                v-model="volume"
                min="0"
                max="1"
                step="0.05"
                style="height: 2px"
              />
            </span>
            <span class="btn btn-sm btn-primary" style="width: 37px">
              <small>{{ parseInt(volume * 100, 10) }}</small>
            </span>
          </div>
          <div class="btn-group w-auto" role="group">
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
          </div>
          <div class="btn-group w-auto" role="group">
            <button
              type="button"
              class="btn btn-sm btn-primary btn-text-icon"
              :class="playerSpeed == 0.5 ? 'active' : ''"
              @click="playerSetSpeed(0.5)"
            >
              0.5x
            </button>
            <button
              type="button"
              class="btn btn-sm btn-primary btn-text-icon"
              :class="playerSpeed == 1 ? 'active' : ''"
              @click="playerSetSpeed(1)"
            >
              1x
            </button>
            <button
              type="button"
              class="btn btn-sm btn-primary btn-text-icon"
              :class="playerSpeed == 1.5 ? 'active' : ''"
              @click="playerSetSpeed(1.5)"
            >
              1.5x
            </button>
            <button
              type="button"
              class="btn btn-sm btn-primary btn-text-icon"
              :class="playerSpeed == 2 ? 'active' : ''"
              @click="playerSetSpeed(2)"
            >
              2x
            </button>
            <button
              type="button"
              class="btn btn-sm btn-primary btn-text-icon"
              :class="playerSpeed == 3 ? 'active' : ''"
              @click="playerSetSpeed(3)"
            >
              3x
            </button>
          </div>
          <div class="btn-group w-auto" role="group" v-if="appType == 'video'">
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
          <div class="btn-group w-auto" role="group" v-if="appType == 'video'">
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
      </div>
      <div class="container-fluid mt-4">
        <div class="row mt-2 mb-4">
          <div class="col col-md-3">
            <label for="timePicker">{{ $t('common-go-to-time') }}:</label>
            <div v-if="currentMediaDuration > 0">
              <VueDatePicker id="timePicker" v-model="selectedTime" time-picker enable-seconds format="HH:mm:ss" :min-time="minTime"
                :start-time="startTime" @update:model-value="handleDatePickerChange"></VueDatePicker>
            </div>
            <div v-else>
              <input id="timePicker" type="text" disabled :placeholder="`${$t('common-loading-video-duration')}...`" />
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
        <div class="row mb-3 mt-2">
          <div class="col">
            <!-- Percentage: <span v-html="progress.toFixed(2)" />% -->
            {{ $t('common-frame') }}:
            <span v-html="parseInt(currentFrame, 10)" />&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {{ $t('common-time') }}: <span
              v-html="currentTime" />
          </div>
        </div>
      </div>
      <div id="timelinePopin" ref="timelinePopin" v-if="timelineEntry" :style="_getTimelinePopinXY()">
        <div v-for="(entry, index) in timelineEntry" :key=index>
          <div class="header" v-html=entry[0]></div>
          <div v-html=entry[1]></div>
        </div>
      </div>
      <TimelineView
        v-if="Object.keys(currentDocumentData).length > 0 && loadingDocument == false"
        :data="currentDocumentData"
        :mediaDuration="currentMediaDuration"
        :playerIsPlaying="playerIsPlaying"
        :playerCurrentTime="playerCurrentTime"
        :hoveredResult="hoveredResult"
        @updateTime="_playerSetTime"
        @annotationEnter="_annotationEnter"
        @annotationLeave="_annotationLeave"
        @mouseleave="_annotationLeave"
        :key="documentIndexKey"
      />
      <div v-else-if="loadingDocument == true">
        {{ $t('common-loading-data') }}...
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
// import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import { useWsStore } from "@/stores/wsStore";

import config from "@/config";
import Utils from "@/utils.js";
import TimelineView from "@/components/videoscope/TimelineView.vue";

import VueDatePicker from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css';

const urlRegex = /(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*))/g;

export default {
  props: ["selectedCorpora", "documentIds", "selectedMediaForPlay", "hoveredResult", "dataType"],
  data() {
    return {
      currentDocumentSelected: null,
      currentDocument: null,
      currentDocumentData: null,
      currentMediaDuration: 0,
      documentIndexKey: 0,
      loadingDocument: false,
      loadingMedia: false,
      isQueryValidData: null,
      loading: false,
      failedStatus: false,

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

      setResultTimes: null,
      query: "",
      queryDQD: '',
      corpusData: [],
      documentDict: {},

      appType: this.dataType,
    };
  },
  components: {
    // EditorView,
    // PaginationComponent,
    TimelineView,
    VueDatePicker
  },
  computed: {
    ...mapState(useCorpusStore, ["queryData", "corpora"]),
    ...mapState(useUserStore, ["userData", "roomId"]),
    ...mapState(useWsStore, ["messagesPlayer"]),
    documentOptions() {
      return this.selectedCorpora ?
        this.corpusData.filter(
          corpus => Object.values(this.documentDict).includes(corpus[1])
        ).map(document => {
          return {
            name: document[1],
            value: document[0],
            document: document
          }
        }) :
        []
    },
    baseMediaUrl() {
      let retval = ""
      if (this.selectedCorpora) {
        retval = `${config.baseMediaUrl}/${this.selectedCorpora.corpus.schema_path}/`
      }
      return retval
    },
  },
  methods: {
    frameNumberToTime(frameNumber) {
      let seconds = Utils.frameNumberToSeconds(frameNumber);
      return Utils.msToTime(seconds);
    },
    updatePage(currentPage) {
      this.currentPage = currentPage;
    },
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
    playerTogglePlay() {
      if (this.playerIsPlaying) {
        this.playerStop()
      }
      else {
        setTimeout(() => this.playerPlay(), 100)
      }
    },
    playerPlay(end = 0) {
      const n_players = [1, 2, 3, 4];
      for (let n of n_players) {
        const player = this.$refs['videoPlayer' + n];
        if (!player)
          continue
        if (end && end >= 0) {
          end = Math.min(end, player.duration);
          const handler = () => {
            if (player.currentTime < end) return;
            this.playerStop();
          };
          player.addEventListener("pause", () => player.removeEventListener("timeupdate", handler), { once: true });
          player.addEventListener("timeupdate", handler);
        }
        try {
          player.play();
        } catch {
          // pass
        }
      }
      this.playerIsPlaying = true;
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
    _playerSetTime(value) {
      const n_players = [1, 2, 3, 4];
      for (let n in n_players) {
        const player = this.$refs["videoPlayer" + n];
        if (!player) continue
        const time = Math.min(value, (isNaN(player.duration) ? 0.1 : player.duration) - 0.1);
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
    handleDatePickerChange(newTime) {
      if(newTime === null) {
        return;
      }

      // Convert the selected time (HH:mm:ss) to seconds.
      let seconds =
        newTime.hours * 3600 +
        newTime.minutes * 60 +
        newTime.seconds;

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
        this.playerCurrentTime = time;
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
    _annotationEnter({ mouseX, mouseY, entry }) {
      // Set coordinates once, using the mouse coordinates
      this.timelinePopinX = mouseX;
      this.timelinePopinY = mouseY;
      
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
      if(!document.querySelector("#timeline-svg")) return;
      
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
      return { 'left': x + 'px', 'top': y - 250 + 'px' };
    },
    onSocketMessage(data) {
      // console.log("SOC2", data)
      if (Object.prototype.hasOwnProperty.call(data, "action")) {
        if (data["action"] === "document") {
          this.documentData = data.document;
          let dataToShow = {};
          // TODO: replace what's hard-coded in this with reading 'tracks' from corpus_template
          let document_id = parseInt(this.currentDocument[0])
          if (!(this.selectedCorpora.value in { 115: 1 })) { // old tangram exception
            const segment_name = this.selectedCorpora.corpus.firstClass.segment;
            let tracks = this.selectedCorpora.corpus.tracks || {"layers": {}};
            if (Object.keys(tracks.layers).length == 0)
              tracks.layers[segment_name] = {split: []};
            // console.log("CRP", this.selectedCorpora, data.document.layers)
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
          this.documentDict = Object.fromEntries(Object.entries(data.document_ids).map(([id, props]) => [id, props.name]));
          this.corpusData = Object.entries(data.document_ids).map(([id, props]) => [id, props.name, Object.values(props.media), props.frame_range]);

          // Preselect first document
          if (!this.currentDocumentSelected) {
            let document = this.corpusData[0];
            if (document) {
              this.currentDocumentSelected = {
                name: document[1],
                value: document[0],
                document: document
              }
            }
          }
          return;
        }
      }
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
    if (!this.document_ids) {
      this.loadDocuments()
    }
    if (this.userData) {
      this.userId = this.userData.user.id;
      // this.connectToRoom();
      // this.stop();
      // this.validate();
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

    // this.setExample(1);
    // if (this.selectedCorpora && this.selectedCorpora.corpus && this.selectedCorpora.corpus.sample_query)
    //   this.updateQueryDQD(this.selectedCorpora.corpus.sample_query);
  },
  // updated() {
  //   if (this.documentIds) {
  //     this.documentDict = Object.fromEntries(Object.entries(this.documentIds).map(([id,props]) => [id,props.name]));
  //     this.corpusData = Object.entries(this.documentIds).map(([id,props]) => [id,props.name,Object.values(props.media),props.frame_range]);
  //   }
  // },
  unmounted() {
    if (this.updateTimer) {
      clearInterval(this.updateTimer);
    }
    // this.sendLeft();
  },
  watch: {
    selectedMediaForPlay() {
      let document = this.corpusData.find(
        corpus => parseInt(corpus[0], 10) == parseInt(this.selectedMediaForPlay.documentId, 10)
      )
      if (document) {
        let [start, end] = [
          this.selectedMediaForPlay.startTime,
          this.selectedMediaForPlay.endTime
        ]
        this.setResultTimes = [start, end];

        this.currentDocumentSelected = {
          name: document[1],
          value: document[0],
          document: document
        }
      }
    },
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
    messagesPlayer: {
      handler() {
        let _messages = this.messagesPlayer;
        if (_messages.length > 0) {
          // console.log("WSM", _messages)
          _messages.forEach(message => this.onSocketMessage(message))
          useWsStore().clearPlayer();
        }
      },
      immediate: true,
      deep: true,
    },
    currentDocumentSelected() {
      // Only reset this if different
      if (this.currentDocument == this.currentDocumentSelected.document)
        return this.videoPlayer1CanPlay();
      this.currentDocument = this.currentDocumentSelected.document;
      this.loadDocument();
    },
    volume() {
      this._setVolume();
    },
  }
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

.video-box[data-is-playing="true"] .video-play-button {
  opacity: 0;
}

.video-box[data-is-playing="true"]:hover .video-play-button {
  opacity: 0.3;
}

.video-box[data-is-playing="false"] .video-play-button {
  opacity: 0.5;
}

.video-play-button {
  position: absolute;
  width: 100px;
  height: 100px;
  border-radius: 50px;
  background-color: #e8e8e854;
  top: calc(50% - 50px);
  left: 100px;
  cursor: pointer;
  transition: all 0.3s;
  z-index: 1000;
}

.video-play-button:hover {
  opacity: 1;
}

.video-play-button>.button {
  margin-top: 39px;
  margin-left: 54px;
  transform: scale(2.0);
}

.video-play-button>.button.play {
  margin-left: 58px;
}

.video-play-button>.button>.s1 {
  display: block;
  background: #FFFFFF;
  width: 20px;
  height: 20px;
  transition: all 0.3s ease;

  -webkit-clip-path: polygon(100% 0, 100% 100%, 66% 100%, 66% 0, 35% 0, 35% 100%, 0 100%, 0 0);
  clip-path: polygon(100% 0, 100% 100%, 66% 100%, 66% 0, 35% 0, 35% 100%, 0 100%, 0 0);
}

.video-play-button>.button.play>.s1 {
  -webkit-clip-path: polygon(100% 49%, 100% 49%, 46% 77%, 46% 26%, 46% 25%, 46% 77%, 0 100%, 0 0);
  clip-path: polygon(100% 49%, 100% 49%, 46% 77%, 46% 26%, 46% 25%, 46% 77%, 0 100%, 0 0);
}

.audio-box {
  height: 0px;
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

div.active>video {
  height: 450px;
}

/* Mobile Responsive Styles */
@media screen and (max-width: 415px) {
  div.active{
    display: flex;
    justify-content: center;
    align-items: center;
  }
}

@media screen and (max-width: 768px) {
  .video-box {
    height: auto;
    min-height: 200px;
    max-height: 300px;
  }

  .video-box > div {
    flex: 1 1 auto;
    /* width: 100%; */
  }

  .video-box > div.active {
    max-width: calc(100vw - 78px);
    min-height: auto;
  }

  div.active > video {
    height: auto;
    max-height: 300px;
    max-width: 100vw;
    width: 100%;
    object-fit: contain;
  }

  .video-text {
    width: 90%;
    left: 5%;
    font-size: 90%;
  }

  .video-play-button {
    width: 60px;
    height: 60px;
    border-radius: 30px;
    top: calc(50% - 30px);
    left: calc(50% - 30px);
  }

  .video-play-button > .button {
    margin-top: 20px;
    margin-left: 25px;
    transform: scale(1.5);
  }

  .video-play-button > .button.play {
    margin-left: 27px;
  }

  .btn-group {
    width: fit-content !important;
    margin: 0;
    align-self: flex-start;
  }
}

@media screen and (orientation: landscape) {
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

/* @media screen and (max-width: 756px) {
  video {
    aspect-ratio: 16 / 9;
  }
} */
</style>
