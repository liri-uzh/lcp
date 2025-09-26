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
      :style="`transform: translate(${offsetX}px, ${offsetY}px) scale(${zoom}) rotate(${rotate}deg);`"
    >
      <img
        id="displayedImage"
        ref="displayedImage"
        :src="src"
        draggable="false"
        @wheel="onWheel"
        @pointerdown="onPointerDown"
        @load="onImageLoad"
      />
      <div
        v-for="([x1,y1,x2,y2,color,layer,id]) in highlights"
        class="highlight-box"
        :key="`div-highlight-${layer}-${id}`"
        :style="[
          ['left',x1-1],
          ['top',y1-1],
          ['width',(x2-x1)+2],
          ['height',(y2-y1)+2],
          ['border-color',color],
          ['display',isVisible(layer,id) ? 'block' : 'none']
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
          <div class="annotation-layer-name" @click="switchVisible(layer)">
            <FontAwesomeIcon :icon="['fas', this.isVisible(layer) ? 'eye' : 'eye-slash']" />
            {{ layer }}
          </div>
          <div class="annotation-list">
            <div
              class="annotation"
              v-for="(annotation, n) in annotations"
              :key="`annotation-layer-${layer}-annotation-${n}`"
              :style="`opacity: ${isVisible(layer, annotation._id) ? 1 : 0.5};`"
            >
              <div class="annotation-box" @click="switchVisible(layer, annotation._id)">
                <div class="annotation-idx">{{ layer }} {{ n+1 }}</div>
                <div
                  class="annotation-attribute"
                  v-for="(value,attribute) in filterAttributes(layer, annotation)"
                  :key="`annotation-layer-${layer}-annotation-${n}-attribute-${attribute}`"
                >
                  {{ attribute }} : {{ value }}
                </div>
              </div>
              <div class="annotation-idx">{{ getAnnotationName(layer, n, annotation) }}</div>
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
      imageWidth: 0,
      imageHeight: 0,
      layerId: this.image.layerId,
      name: this.image.name,
      dragStart: null,
      currentToken: null,
      currentDocumentSelected: null,
      documentOptions: [],
      annotationVisibility: {}
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
    getAnnotationName(layer, n, attributes) {
      if (attributes.form) return attributes.form;
      else return layer + " " + String(n + 1);
    },
    onImageLoad() {
      this.adjustImage();
    },
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
    async adjustImage() {
      if (this.imageWidth == 0 || this.imageHeight == 0) {
        const img = new Image();
        img.src = this.src;
        img.style.visibility = "hidden";
        document.body.append(img);
        while (img.getBoundingClientRect().width == 0)
          await new Promise(r=>setTimeout(r, 1));
        const {width, height} = img.getBoundingClientRect();
        this.imageWidth = width;
        this.imageHeight = height;
        img.remove();
      }
      const viewerContainer = this.$refs.viewerContainer;
      const img = this.$refs.displayedImage;
      const filename = this.filename;
      if (!filename || !viewerContainer || !img)
        return window.requestAnimationFrame(()=>this.adjustImage());
      const vbcr = viewerContainer.getBoundingClientRect();
      if (vbcr.width == 0 || vbcr.height == 0)
        return window.requestAnimationFrame(()=>this.adjustImage());
      this.zoom = (vbcr.width * 0.45) / this.imageWidth;
      const [newWidth, newHeight] = [this.imageWidth * this.zoom, this.imageHeight * this.zoom];
      this.offsetX = {0: 0, 90: newHeight, 180: newWidth, 270: 0}[this.rotate];
      this.offsetY = {0: 0, 90: 0, 180: newHeight, 270: newWidth}[this.rotate];
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
    },
    isVisible(layer, annotationId) {
      if (!(layer in this.annotationVisibility)) return true;
      if (!this.annotationVisibility[layer].show) return false;
      if (annotationId === undefined) return true;
      if (!(annotationId in this.annotationVisibility[layer].annotations))
        return true;
      return this.annotationVisibility[layer].annotations[annotationId];
    },
    switchVisible(layer, annotationId) {
      this.annotationVisibility[layer] = this.annotationVisibility[layer] || {show: true, annotations: {}};
      const av = this.annotationVisibility[layer];
      if (annotationId === undefined)
        av.show = !av.show;
      else {
        if (!(annotationId in av.annotations))
          av.annotations[annotationId] = true;
        av.annotations[annotationId] = !av.annotations[annotationId];
      }
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
        if (overlaps.length == 0) continue;
        ret[layer] = [...(ret[layer] || []), ...overlaps];
      }
      return ret;
    },
    allPrepared() {
      const img = this.currentImage;
      if (!img) return [];

      const prepared = [];
      const segments = this.meta.layer[this.corpus.segment].byStream.searchValue(img.char_range);
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
      const sortedXs = [x1 > x2 ? x2 : x1, x1 > x2 ? x1 : x2];
      const sortedYs = [y1 > y2 ? y2 : y1, y1 > y2 ? y1 : y2];
      const image_offset = [sortedXs[0], sortedYs[0], sortedXs[1], sortedYs[1]];

      for (let [layer, bys] of Object.entries(this.meta.layer)) { // eslint-disable-line no-unused-vars
        const overlaps = this.overlaps(bys.byLocation, img.xy_box);
        for (let o of overlaps) {
          if (!o || !o.xy_box) continue;
          [x1,x2,y1,y2] = [
            ...[o.xy_box[0], o.xy_box[2]].sort((a,b)=>parseInt(a) - parseInt(b)),
            ...[o.xy_box[1], o.xy_box[3]].sort((a,b)=>parseInt(a) - parseInt(b))
          ];
          highlights.push([
            x1-image_offset[0],
            y1-image_offset[1],
            x2-image_offset[0],
            y2-image_offset[1],
            colors[highlights.length % colors.length],
            layer,
            o._id
          ]);
        }
      }

      highlights = highlights.map(([left,top,width,height,color,layer,id])=>{
        const [newLeft, newTop] = [Math.max(-1 * MARGIN, left), Math.max(-1 * MARGIN, top)];
        const [newWidth, newHeight] = [
          Math.min(width, image_offset[2]-image_offset[0] + MARGIN - newLeft),
          Math.min(height, image_offset[3]-image_offset[1] + MARGIN - newTop)
        ];
        return [newLeft, newTop, newWidth, newHeight, color, layer, id];
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
    },
    layerId() {
      // automatically resize and reposition image here
      const img = this.currentImage;
      if (!img) return;
      const filename = this.filename;
      if (!filename) return;
      this.name = filename.replace(/\.[^.]+$/,"");
    },
    currentImage() {
      this.imageWidth = 0;
      this.imageHeight = 0;
      if (!this.currentImage) return;
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
    },
    nonSegments() {
      for (let [layer, annotations] of Object.entries(this.nonSegments || {})) {
        if (!(layer in this.annotationVisibility))
          this.annotationVisibility[layer] = {show: true, annotations: {}};
        for (let annotation of annotations)
          this.annotationVisibility[layer].annotations[annotation._id] = true;
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
.non-segment {
  max-height: 20vh;
  overflow-y: scroll;
  margin-bottom: 1em;
}
.annotation-layer-name {
  font-weight: bold;
  margin-bottom: 0.25em 0em;
}
.annotation-list {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
}
.annotation-list .annotation {
  background-color: beige;
  padding: 0.25em;
  border-radius: 0.5em;
}
.annotation-list .annotation .annotation-box {
  display: none;
  background-color: beige;
  padding: 0.25em;
  border-radius: 0.5em;
  margin: -5px 0px 0px -5px;
  box-shadow: black 0px 0px 5px;
}
.annotation-list .annotation:hover .annotation-box {
  position: absolute;
  display: block;
  z-index: 99;
}
.non-segment .annotation {
  margin: 0.25em;
}
.rotate-nav {
  display: flex;
  justify-content: space-between;
  margin: 0em 2em;
}
#viewer-container {
  width: 100%;
  height: 50vh;
  position: relative;
  overflow: hidden;
  resize: vertical;
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
  width: calc(50% - 2em);
  margin: 2em;
  height: 50vh;
  overflow-y: scroll;
  display: flex;
  flex-direction: column;
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
