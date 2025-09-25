<template>
  <div class="container-fuild">
    <div class="row" v-if="corpus">
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

  <LoadingView class="image-loading" override="1" v-if="!currentImage"/>
  <div
    id="viewer-container"
    ref="viewerContainer"
    @pointermove="onPointerMove"
    @pointerup="onPointerStop"
    @pointercancel="onPointerStop"
    v-if="corpus && imageLayer && layerId"
  >
    <div id="prev-image" @click="updateImageId(layerId - 1)"> &lt; </div>
    <div id="next-image" @click="updateImageId(layerId + 1)"> &gt; </div>
    <div class="rotate-nav">
      <div id="rotate-image-left" @click="rotateBy(-1)"><FontAwesomeIcon :icon="['fas', 'rotate-left']" /></div>
      <div id="rotate-image-right" @click="rotateBy(1)"><FontAwesomeIcon :icon="['fas', 'rotate-right']" /></div>
    </div>
    <span>{{ imageLayer }} #{{ layerId }} ({{ filename.replace(/\.[^.]+$/,"") }})</span>
    <div
      ref="imageContainer"
      class="image-container"
      :style="`transform: scale(${zoom}) translate(${offsetX}px, ${offsetY}px) rotate(${rotate}deg);`"
    >
      <img
        id="displayedImage"
        ref="displayedImage"
        :src="src"
        draggable="false"
        @wheel="onWheel"
        @pointerdown="onPointerDown"
      />
      <div
        v-for="(xyc, n) in highlights"
        class="highlight-box"
        :key="`div-highlight-${n}`"
        :style="[
          ['left',xyc[0]-1],
          ['top',xyc[1]-1],
          ['width',(xyc[2]-xyc[0])+2],
          ['height',(xyc[3]-xyc[1])+2],
          ['border-color',xyc[4]]
        ].map(([p,v],n)=>p+': '+v+(n<4?'px':'')).join('; ')"
      >
      </div>
    </div>
    <div id="annotations">
      <div class="non-segments">
        <div
          class="non-segment"
          v-for="(annotations,layer) in nonSegments"
          :key="`annotation-layer-${layer}`"
        >
          {{ layer }}
          <div
            class="annotation"
            v-for="(annotation, n) in annotations"
            :key="`annotation-layer-${layer}-annotation-${n}`"
          >
            <div
              class="annotation-attribute"
              v-for="(value,attribute) in filterAttributes(layer, annotation)"
              :key="`annotation-layer-${layer}-annotation-${n}-attribute-${attribute}`"
            >
              {{ attribute }} : {{ value }}
            </div>
          </div>
        </div>
      </div>
      <div class="segments" v-if="allPrepared instanceof Array && allPrepared.length > 0">
        <div
          class="segment"
          v-for="(prep, n) in allPrepared"
          :key="`image-prepared-${n}`"
          :class="prep._highlight > 0 ? 'highlight' : ''"
        >
          <PlainTokens
            :item="prep"
            :columnHeaders="columnHeaders"
            :currentToken="currentToken"
            :resultIndex="0"
            @showPopover="()=>null"
            @closePopover="()=>null"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useUserStore } from "@/stores/userStore";

import LoadingView from "@/components/LoadingView.vue";
import PlainTokens from "@/components/results/PlainToken.vue";

import Utils from "@/utils";
import config from "@/config";

const TokenToDisplay = Utils.TokenToDisplay;

const MARGIN = 10;

export default {
  name: "ImageViewer",
  components: {
    PlainTokens,
    LoadingView
  },
  data() {
    return {
      zoom: 1,
      rotate: 0,
      offsetX: 0,
      offsetY: 0,
      layerId: this.image.layerId,
      name: this.image.name,
      dragStart: null,
      currentToken: null,
      currentDocumentSelected: null,
      documentOptions: [],
    }
  },
  props: [
    "image",
    "corpus",
    "meta",
    "sentences",
    "documentIds"
  ],
  emits: ["getImageAnnotations", "switchToQueryTab"],
  methods: {
    overlaps(itv, xy_box) {
      const [x1,y1,x2,y2] = xy_box;
      const overlapXs = itv.searchValue([x1,x2]);
      const overlaps = overlapXs.map(o=>o.searchValue([y1,y2])).flat();
      return overlaps;
    },
    filterAttributes(layer, attributes) {
      const ret = {};
      const validAttributes = this.corpus.layer[layer].attributes;
      for (let [attribute,value] of Object.entries(attributes)) {
        if (!(attribute in validAttributes)) continue;
        ret[attribute] = value;
      }
      return ret;
    },
    adjustImage() {
      const viewerContainer = this.$refs.viewerContainer;
      const img = this.$refs.displayedImage;
      const filename = this.filename;
      if (!filename || !viewerContainer || !img)
        return window.requestAnimationFrame(()=>this.adjustImage());
      const vbcr = viewerContainer.getBoundingClientRect();
      const ibcr = img.getBoundingClientRect();
      if ([vbcr.width,vbcr.height,ibcr.width,ibcr.height].includes(0))
        return window.requestAnimationFrame(()=>this.adjustImage());
      const dim = this.rotate % 180 ? 'height' : 'width';
      const original = ibcr[dim] / this.zoom;
      this.offsetX = [0,270].includes(this.rotate) ? 0 : (this.rotate == 90 ? ibcr.height : ibcr.width) / this.zoom;
      this.offsetY = this.rotate < 180 ? 0 : (this.rotate == 180 ? ibcr.height : ibcr.width) / this.zoom;
      this.zoom = (vbcr[dim] * 0.45) / original;
    },
    rotateBy(by) {
      this.rotate = (360 + this.rotate + by * 90) % 360;
      this.adjustImage();
    },
    onPointerDown(e) {
      const {clientX, clientY} = e;
      this.dragStart = {
        offsets: [this.offsetX, this.offsetY],
        pointer: [clientX, clientY]
      };
    },
    onPointerMove(e) {
      if (!this.dragStart) return;
      const [offsetX, offsetY] = this.dragStart.offsets;
      const [x,y] = this.dragStart.pointer;
      const {clientX, clientY} = e;
      this.offsetX = offsetX + clientX - x;
      this.offsetY = offsetY + clientY - y;
    },
    onPointerStop() {
      this.dragStart = null;
    },
    onWheel(e) {
      e.preventDefault();
      e.stopPropagation();
      this.zoom = Math.max(0.2, Math.min(2.0, this.zoom - e.deltaY/500));
    },
    updateImageId(id) {
      if (id < 1) return;
      this.layerId = id;
      this.$emit("getImageAnnotations", this.imageLayer, id);
    },
    loadDocuments() {
      useCorpusStore().fetchDocuments({
        room: this.roomId,
        user: this.userData.user.id,
        corpora_id: this.corpus.meta.id,
        kind: "image"
      });
    },
    shouldFetchForDocument() {
      // returns true if one needs to fetch annotations
      if (!this.currentDocumentSelected) return;
      const box = this.currentDocumentSelected.value.xy_box;
      let foundImages = [];
      if (this.meta.layer && this.meta.layer[this.imageLayer])
        foundImages = this.overlaps(this.meta.layer[this.imageLayer].byLocation, box)
      if (foundImages.length>0) {
        if (this.currentImage && foundImages.find(i=>i._id == this.layerId)) return;
        this.layerId = foundImages[0]._id;
        return;
      }
      return true;
    }
  },
  computed: {
    ...mapState(useUserStore, ["userData", "roomId"]),
    currentImage() {
      if (!this.layerId) return;
      if (!this.imageLayer) return;
      if (!this.meta.layer) return;
      const images = this.meta.layer[this.imageLayer];
      if (!images) return;
      const img = (images.byId || {})[this.layerId];
      if (!img) return;
      return img;
    },
    imageAttr() {
      if (!this.imageLayer) return "";
      if (!this.corpus || !this.corpus.layer || !this.corpus.layer[this.imageLayer]) return "";
      const attrs = this.corpus.layer[this.imageLayer].attributes || {};
      return (Object.entries(attrs).find(kv=>kv[1].type == "image") || [""])[0];
    },
    filename() {
      const img = this.currentImage;
      if (!img) return "";
      return img[this.imageAttr] || "";
    },
    src() {
      // Update current document
      const filename = this.filename;
      if (!filename) return "";
      this.adjustImage();
      return this.baseMediaUrl + filename;
    },
    imageLayer() {
      return (Object.entries(this.corpus.layer).find((l)=>Object.values(l[1].attributes||{}).find(a=>a.type == "image")) || [null])[0];
    },
    columnHeaders() {
      if (!this.corpus) return [];
      const seg = this.corpus.segment;
      return this.corpus.mapping.layer[seg].prepared.columnHeaders;
    },
    nonSegments() {
      const img = this.currentImage;
      if (!img) return {};
      const ret = {};
      for (let [layer, bys] of Object.entries(this.meta.layer)) {
        const overlaps = this.overlaps(bys.byLocation, img.xy_box);
        ret[layer] = [...(ret[layer] || []), ...overlaps];
      }
      return ret;
    },
    allPrepared() {
      const img = this.currentImage;
      if (!img) return [];

      const prepared = [];
      const char_range = [...img.char_range].sort(n=>parseInt(n));
      const segments = this.meta.layer[this.corpus.segment].byStream.searchValue(char_range);
      for (let segment of segments.sort((a,b)=>a.char_range[0] - b.char_range[0])) {
        if (!(segment._id in this.sentences)) continue;
        const [segOffset, preTokens] = this.sentences[segment._id];
        if (!preTokens) continue
        let groups = [];
        if (this.image.resultSegment == segment._id)
          groups = this.image.groups;
        const tokens = preTokens.map((t,i)=>new TokenToDisplay(t, (segOffset||1)+i, groups, this.columnHeaders, {}));
        tokens._highlight = groups.length;
        prepared.push(tokens);
      }
      return prepared;
    },
    highlights() {

      const colors = ["green","blue","orange","pink","brown"];

      let highlights = [];
      if (!this.layerId || this.layerId < 0) return highlights;

      const img = this.currentImage;
      if (!img) return highlights;

      let [x1,y1,x2,y2] = img.xy_box;
      let sortedXs = [x1,x2].sort(n=>parseInt(n)), sortedYs = [y1,y2].sort(n=>parseInt(n));
      const image_offset = [sortedXs[0], sortedYs[0], sortedXs[1], sortedYs[1]];

      for (let [layer, bys] of Object.entries(this.meta.layer)) { // eslint-disable-line no-unused-vars
        const overlaps = this.overlaps(bys.byLocation, img.xy_box);
        for (let o of overlaps) {
          if (!o || !o.xy_box) continue;
          [x1,x2,y1,y2] = [
            ...[o.xy_box[0], o.xy_box[2]].sort(n=>parseInt(n)),
            ...[o.xy_box[1], o.xy_box[3]].sort(n=>parseInt(n))
          ];
          highlights.push([
            x1-image_offset[0],
            y1-image_offset[1],
            x2-image_offset[0],
            y2-image_offset[1],
            colors[highlights.length % colors.length]
          ]);
        }
      }

      highlights = highlights.map(([left,top,width,height,color])=>{
        const [newLeft, newTop] = [Math.max(-1 * MARGIN, left), Math.max(-1 * MARGIN, top)];
        const [newWidth, newHeight] = [
          Math.min(width, image_offset[2]-image_offset[0] + MARGIN - newLeft),
          Math.min(height, image_offset[3]-image_offset[1] + MARGIN - newTop)
        ];
        return [newLeft, newTop, newWidth, newHeight, color];
      });

      return highlights;
    },
    baseMediaUrl() {
      let retval = ""
      if (this.corpus) {
        retval = `${config.baseMediaUrl}/${this.corpus.schema_path}/`
      }
      return retval
    }
  },
  watch: {
    image() {
      this.layerId = this.image.layerId;
      this.adjustImage();
    },
    layerId() {
      // automatically resize and reposition image here
      this.adjustImage();
      const img = this.currentImage;
      if (!img) return;
      const filename = this.filename;
      if (!filename) return;
      this.name = filename.replace(/\.[^.]+$/,"");
    },
    currentImage() {
      if (!this.currentImage) return;
      setTimeout(()=>this.adjustImage(), 50);
      if (!this.meta || !this.meta.layer || !this.meta.layer[this.corpus.document]) return;
      const docs = this.overlaps(this.meta.layer[this.corpus.document].byLocation, this.currentImage.xy_box);
      if (docs.length==0) return;
      const doc = docs[0];
      if (this.currentDocumentSelected && doc._id == this.currentDocumentSelected.value.id) return;
      this.currentDocumentSelected = {
        name: this.corpus.document + " " + doc._id,
        value: {
          id: doc._id,
          xy_box: doc.xy_box
        }
      };
    },
    documentIds() {
      this.documentOptions = Object.entries(this.documentIds)
        .map(([id,info])=>Object({
          name: this.corpus.document + " " + id,
          value: {id: id, xy_box: JSON.parse("["+info.xy_box.replace(/[()]+/g,"")+"]")}
        }));
      if (!this.currentDocumentSelected)
        this.currentDocumentSelected = this.documentOptions[0];
    },
    meta() {
      if (this.currentImage) return;
      if (!this.meta.layer) return;
      if (this.shouldFetchForDocument()) return;
    },
    currentDocumentSelected() {
      if (!this.currentDocumentSelected) return;
      if (this.shouldFetchForDocument()) {
        this.layerId = null;
        this.$emit("getImageAnnotations", this.imageLayer, this.currentDocumentSelected.value.xy_box);
      }
    }
  },
  mounted() {
    this._keydownhandler = e=>{
      if (!this.$refs.viewerContainer) return;
      if (this.$refs.viewerContainer.getBoundingClientRect().width == 0) return;
      if (e.key == "ArrowLeft") this.updateImageId(this.layerId - 1);
      else if (e.key == "ArrowRight") this.updateImageId(this.layerId + 1);
      else return;
      e.stopPropagation();
      e.preventDefault();
    };
    document.addEventListener("keydown", this._keydownhandler);
    this.loadDocuments();
  },
  beforeUnmount() {
    document.removeEventListener("keydown", this._keydownhandler);
  }
};
</script>

<style>
.image-loading {
  position: absolute;
  top: 0;
  left: 0;
  width: 5em;
  height: 5em;
}
.non-segments {
  margin-bottom: 2em;
}
.non-segment {
  font-weight: bold;
  margin-bottom: 1em;
}
.non-segment .annotation {
  font-weight: normal;
  margin-left: 1em;
  height: 4em;
  overflow-y: scroll;
  resize: vertical;
}
.rotate-nav {
  display: flex;
  justify-content: space-between;
  margin: 0em 2em;
}
#viewer-container {
  width: 100%;
  max-height: 50vh;
  /* height: 100%; */
  position: relative;
}
.segment.highlight {
  border: solid 2px green;
}
#prev-image, #next-image {
  position: absolute;
  height: 100%;
  z-index: 100;
  width: 2em;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}
#prev-image {
  margin-left: -1em;
}
#next-image {
  right: 0;
}
#prev-image:hover, #next-image:hover {
  background-color: #9993;
  cursor: pointer;
}
#annotations {
  position: absolute;
  right: 0;
  top: 0;
  max-width: calc(50% - 2em);
  margin: 2em;
  /* height: calc(100% - 5em); */
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.image-container {
  position: relative;
  transform-origin: top left;
  margin-left: 2em;
}
.image-container img {
  user-select: none;
}
.highlight-box {
  z-index: 99;
  position: absolute;
  border: solid 6px black;
  pointer-events: none;
}
</style>
