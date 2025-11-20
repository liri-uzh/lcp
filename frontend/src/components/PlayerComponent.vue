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
        <div v-if="currentDocumentInfo" class="doc-info">
          <div v-html="dictToStr(currentDocumentInfo, {addTitles: true})"></div>
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
          <div class="btn-group w-auto" role="group">
            <input type="number" ref="pickerHours" min="0" placeholder="HH" style="width: 60px;" @keyup="(e)=>e.target.value.length >= 2 && $refs.pickerMinutes.focus()"/>
            <span>:</span>
            <input type="number" ref="pickerMinutes" min="0" max="59" placeholder="MM" style="width: 60px;" @keyup="(e)=>e.target.value.length >= 2 && $refs.pickerSeconds.focus()" />
            <span>:</span>
            <input type="number" ref="pickerSeconds" min="0" max="59" placeholder="SS" style="width: 60px;" />
            <button @click="handleDatePickerChange">{{ $t('common-go-to-time') }}</button>
          </div>
        </div>
      </div>
      <div class="container-fluid mt-4">
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
      <button
        v-if="Object.keys(dataToShow).length > 0 && loadingDocument == false"
        type="button"
        class="btn btn-sm btn-light"
        data-bs-toggle="modal"
        data-bs-target="#timelineSettings"
        title="Timeline visualization settings"
        style="position: absolute;"
      >
        <FontAwesomeIcon :icon="['fas', 'gear']" />
      </button>
      <TimelineView
        v-if="Object.keys(dataToShow).length > 0 && loadingDocument == false"
        :data="dataToShow"
        :mediaDuration="currentMediaDuration"
        :playerIsPlaying="playerIsPlaying"
        :playerCurrentTime="playerCurrentTime"
        :hoveredResult="hoveredResult"
        :corpusId="selectedCorpora.value"
        :docId="currentDocument[0]"
        @updateTime="_playerSetTime"
        @annotationEnter="_annotationEnter"
        @annotationLeave="_annotationLeave"
        @annotationClick="_annotationClick"
        @mouseleave="_annotationLeave"
        :key="documentIndexKey"
        ref="timelineview"
      />
      <div v-else-if="loadingDocument == true">
        {{ $t('common-loading-data') }}...
      </div>
    </div>
  </div>

  <div class="modal fade" id="timelineSettings" tabindex="-1" aria-labelledby="timelineSettingsLabel"
    aria-hidden="true" ref="vuemodaldetails">
    <div class="modal-dialog modal-xl">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="timelineSettingsLabel">
            Timeline
          </h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div v-if="selectedCorpora.corpus.globalAttributes">
          <strong>Group by:</strong>
          <div class="timeline-split">
            <span v-for="(ga_name, index) in Object.keys(selectedCorpora.corpus.globalAttributes)" :key=index>
              <input type="checkbox" :id="`timeline_global_attribute_${ga_name}`" :value="ga_name" v-model="this.tracks_conf.group_by" @input="updateConf"/>
              <label :for="`timeline_global_attribute_${ga_name}`"><em>{{ ga_name }}</em></label>
            </span>
          </div>
        </div>
        <div v-for="(lprops, lname) in timedLayers" :key=lname>
          <input type="checkbox" :id="`timeline_${lname}`" :checked="lname in tracks_conf.layers" @input="switchConfLayer"/>
          <label :for="`timeline_${lname}`">Show <strong>{{ lname }}</strong></label>
          <div v-if="lname in tracks_conf.layers" class="timeline-split">
            <span v-for="(aname, index) in getEnumAttributes(lname, lprops.attributes)" :key=index>
              <input type="checkbox" :id="`timeline_${lname}_${aname}`" :value="aname" v-model="this.tracks_conf.layers[lname].split" @input="updateConf" />
              <label :for="`timeline_${lname}_${aname}`">Split by <em>{{ aname }}</em></label>
            </span>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
            {{ $t('common-close') }}
          </button>
        </div>
      </div>
    </div>
  </div>

</template>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useUserStore } from "@/stores/userStore";
import { useWsStore } from "@/stores/wsStore";

import config from "@/config";
import Utils from "@/utils.js";
import TimelineView from "@/components/videoscope/TimelineView.vue";

class Track {
  constructor(name, splits, groups) {
    this._name = name;
    this._values = [];
    this._splits = splits || {};
    this._groups = groups || {};
  }
  push(v, info, layer_attrs) {
    const [startFrame, endFrame] = info.frame_range; //JSON.parse(info.frame_range.replace(")","]"));
    const shift = v.currentDocument[3][0];
    let startTime = (parseFloat(startFrame - shift) / v.frameRate);
    let endTime = (parseFloat(endFrame - shift) / v.frameRate);
    const content = Object.entries(info)
      .filter(kv=>!(kv[0] in this._splits) && kv[0] in layer_attrs && layer_attrs[kv[0]].type in {text:1,categorical:1,number:1})
      .sort(kv=>kv[0] == "form" ? -1 : 1) // priority to the form
      .map(kv=>kv[1])
      .join(" ");
    this._values.push({ x1: startTime, x2: endTime, l: 0, entry: info, n: content });
  }
  toObj(level) {
    let name = this._name;
    if (this._splits.length)
      name += Object.values(this._splits).join(" ");
    return {name: name, heightLines: 1, values: this._values, level: level || 0};
  }
}

const urlRegex = /(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*))/g;

export default {
  props: ["meta", "selectedCorpora", "documentIds", "selectedMediaForPlay", "hoveredResult", "dataType"],
  emits: ["switchToQueryTab"],
  data() {
    return {
      currentDocumentSelected: null,
      currentDocument: null,
      currentDocumentData: null,
      currentDocumentInfo: null,
      dataToShow: [],
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
      tracks_conf: {layers: {}, group_by: []},

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
    TimelineView,
  },
  computed: {
    ...mapState(useCorpusStore, ["queryData", "corpora"]),
    ...mapState(useUserStore, ["userData", "roomId"]),
    ...mapState(useWsStore, ["messagesPlayer"]),
    timedLayers() {
      if (!this.selectedCorpora || !this.selectedCorpora.corpus) return {};
      const layers = this.selectedCorpora.corpus.layer || {};
      const ret = {};
      for (let [lname, lprops] of Object.entries(layers)) {
        if (lname == this.selectedCorpora.corpus.token || !Utils.isAnchored(lname, layers, "time")) continue;
        ret[lname] = lprops;
      }
      return ret;
    },
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
        }).sort((x,y)=>(x.name || "").toLowerCase() > (y.name || "").toLowerCase()) :
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
    dictToStr(...args) {
      return Utils.dictToStr(...args);
    },
    updateConf() {
      if (this._updateConfTimeout) clearTimeout(this._updateConfTimeout);
      this._updateConfTimeout = setTimeout(()=>this.toTimeline(), 500);
    },
    switchConfLayer(e) {
      const layer = e.target.id.replace(/^timeline_/,"");
      if (e.target.checked)
        this.tracks_conf.layers[layer] = this.tracks_conf.layers[layer] || {};
      else if (layer in this.tracks_conf.layers)
        delete this.tracks_conf.layers[layer];
      this.updateConf();
    },
    getEnumAttributes(layer, attributes) {
      this.tracks_conf.layers[layer].split = this.tracks_conf.layers[layer].split || [];
      const ret = [];
      for (let [aname, aprops] of Object.entries(attributes||{})) {
        if (!(aprops.type in {text:1, number:1, categorical: 1} || aprops.ref)) continue;
        ret.push(aname);
      }
      return ret;
    },
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
        const tv = this.$refs.timelineview;
        if (tv) {
          let [tvstart,tvend] = [tv.selectionStart,tv.selectionEnd]
          if (tvstart > tvend) [tvstart,tvend] = [tvend, tvstart];
          if (tvend - tvstart > 0.1 && tvend > 0) {
            this.currentTime = tvstart;
            player.currentTime = tvstart;
            end = tvend;
          }
        }
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
    handleDatePickerChange() {
      if (!this.currentMediaDuration) return;
      const newTime = {
        hours: Math.min(this.currentMediaDuration/3600, Math.max(parseInt(this.$refs.pickerHours.value) || 0, 0)),
        minutes: Math.min(59, Math.max(parseInt(this.$refs.pickerMinutes.value) || 0, 0)),
        seconds: Math.min(59, Math.max(parseInt(this.$refs.pickerSeconds.value) || 0, 0))
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
        .map(([name, value]) => [name, typeof(value)=="string" ? value.replace(urlRegex, "<a href='$1' target='_blank'>$1</a>") : value]);
    },
    _annotationClick(stick) {
      if (!this.timelineEntry) return;
      this.timelineEntry._stick = stick;
    },
    _annotationLeave() {
      if (this.timelineEntry && this.timelineEntry._stick) return;
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
    toTimeline() {
      const conf = this.tracks_conf;
      const data = this.currentDocumentData;
      const group_conf = conf.group_by || [];
      const seg = this.selectedCorpora.corpus.segment;
      const column_names = this.selectedCorpora.corpus.mapping.layer[seg].prepared.columnHeaders;
      const form_n = column_names.indexOf("form");
      const segs_to_fill = {};
      const tracks = [];
      const getTrack = (name, splits, groups) => {
        let track = tracks.find(
          t=>t._name == name && 
          Object.entries(t._splits).every(([k,v])=>splits[k] == v) &&
          Object.entries(t._groups).every(([k,v])=>groups[k] == v)
        );
        if (!track) {
          track = new Track(name, splits, groups);
          tracks.push(track);
        }
        return track;
      }
      let all_groups = {};
      for (let [[layer, lid, info]] of data) {
        if (layer == "_prepared" && lid in segs_to_fill) {
          // the _prepared rows come last, after the segments have been processed
          const content = info.map(t=>t[form_n]).join(" ");
          segs_to_fill[lid].n = content;
        }
        if (!(layer in conf.layers)) continue;
        let track_name = layer;
        const groups = {};
        for (let aname of group_conf) {
          if (!(aname in info)) continue;
          groups[aname] = info[aname];
          all_groups[aname] = all_groups[aname] || {};
          all_groups[aname][info[aname]] = 1;
        }
        const split_conf = conf.layers[layer].split || [];
        const splits = {};
        for (let aname of split_conf) {
          if (aname in groups || !(aname in info)) continue;
          splits[aname] = info[aname];
          track_name += " " + info[aname];
        }
        const track = getTrack(track_name, splits, groups);
        const layer_attrs = this.selectedCorpora.corpus.layer[layer].attributes;
        track.push(this, info, layer_attrs);
        if (layer == this.selectedCorpora.corpus.segment)
          segs_to_fill[lid] = track._values.at(-1);
      }

      const no_groups = {x: 1};
      if (Object.keys(all_groups).length == 0)
        all_groups = {x: no_groups}
      const tracks_to_show = [];
      for (let [group_name,group_values] of Object.entries(all_groups)) {
        const groups = Object.keys(group_values);
        for (let gn=0; gn < groups.length; gn++) {
          if (group_values != no_groups)
            tracks_to_show.push(new Track(`${group_name} ${gn+1}`, {}, {}).toObj(0));
          const group_value = groups[gn];
          for (let t of tracks) {
            const track_is_grouped = Object.keys(t._groups).length > 0;
            if (!track_is_grouped && gn>0)
              continue;
            if (track_is_grouped && group_name in t._groups && t._groups[group_name] != group_value)
              continue;
            const track_obj = t.toObj(track_is_grouped ? 1 : 0);
            if (track_is_grouped)
              tracks_to_show.push(track_obj);
            else
              tracks_to_show.unshift(track_obj);
          }
        }
      }
      let mediaDuration = 0;
      for (let n=0; n < tracks_to_show.length; n++) {
        const track = tracks_to_show[n];
        for (let v of track.values) {
          v.l = n;
          if (v.x2 > mediaDuration)
            mediaDuration = v.x2;
        }
      }
      this.dataToShow = tracks_to_show;
      return mediaDuration;
    },
    onSocketMessage(data) {
      // console.log("SOC2", data)
      if (Object.prototype.hasOwnProperty.call(data, "action")) {
        if (data["action"] === "document") {
          this.currentDocumentData = data.document;
          const default_tracks = {"layers": Object.fromEntries([[this.selectedCorpora.corpus.segment,{}]]), group_by: []};
          if (Object.keys(this.tracks_conf.layers).length == 0)
            this.tracks_conf = this.selectedCorpora.corpus.tracks || default_tracks;
          this.currentMediaDuration = this.toTimeline();
          this.loadingDocument = false;
          this.documentIndexKey++;
          this._setVolume();
          const doc_layer = this.selectedCorpora.corpus.document;
          this.currentDocumentInfo = ((((this.meta||{}).layer||{})[doc_layer]||{}).byId||{})[this.currentDocumentSelected.value];
          return;
        }
        else if (data["action"] === "document_ids") {
          this.documentDict = Object.fromEntries(Object.entries(data.document_ids).map(([id, props]) => [id, props.name]));
          this.corpusData = Object.entries(data.document_ids).map(
            ([id, props]) => {
              let fr = [0,0];
              try {
                fr = JSON.parse(props.frame_range.replace(")","]"));
              } catch { /* */ }
              return [id, props.name, Object.values(props.media), fr]
            }
          );

          // Preselect first document
          if (!this.currentDocumentSelected) {
            let document = this.corpusData[0];
            if (document) {
              this.currentDocumentSelected = {
                name: document[1],
                value: document[0],
                document: document
              };
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
        this.$refs.timelineview.select(start, end);
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
      this.currentDocumentInfo = null;
      this.loadDocument();
    },
    volume() {
      this._setVolume();
    }
  }
};
</script>

<style scoped>
#nav-tab {
  height: 5em;
  display: flex;
  overflow: scroll;
}

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

.timeline-split {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: space-between;
  margin-left: 2em;
}
.timeline-split span {
  margin-right: 2em;
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

#timelineSettings .modal-content {
  margin-left: 1em;
}
#timelineSettings .modal-content div:nth-child(n+2) {
  margin: 0.2em 1.5em;
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
