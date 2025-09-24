<template
>
  <div
    id="viewer-container"
    ref="viewerContainer"
    @pointermove="onPointerMove"
    @pointerup="onPointerStop"
    @pointercancel="onPointerStop"
  >
    <div id="prev-image" @click="updateImageId(layerId - 1)"> &lt; </div>
    <div id="next-image" @click="updateImageId(layerId + 1)"> &gt; </div>
    <div class="rotate-nav">
      <div id="rotate-image-left" @click="rotateBy(-1)"><FontAwesomeIcon :icon="['fas', 'rotate-left']" /></div>
      <div id="rotate-image-right" @click="rotateBy(1)"><FontAwesomeIcon :icon="['fas', 'rotate-right']" /></div>
    </div>
    <span>{{ image.layer }} #{{ layerId }}</span>
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
import PlainTokens from "@/components/results/PlainToken.vue";

import Utils from "@/utils";
import config from "@/config";

const TokenToDisplay = Utils.TokenToDisplay;

const MARGIN = 10;

export default {
  name: "ImageViewer",
  components: {
    PlainTokens
  },
  data() {
    return {
      zoom: 1,
      rotate: 0,
      offsetX: 0,
      offsetY: 0,
      layerId: this.image.layerId,
      name: this.image.name,
      src: this.image.src,
      dragStart: null,
      currentToken: null,
    }
  },
  props: [
    "image",
    "columnHeaders",
    "corpus",
    "meta",
    "sentences",
  ],
  emits: ["getImageAnnotations"],
  methods: {
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
      const vbcr = viewerContainer.getBoundingClientRect();
      const ibcr = img.getBoundingClientRect();
      if ([vbcr.width,vbcr.height,ibcr.width,ibcr.height].includes(0))
        return setTimeout(()=>this.adjustImage());
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
    updateImageContent() {
      const id = this.layerId;
      const img = this.meta.layer[this.image.layer].byId[id];
      // automatically resize and reposition image here
      setTimeout(()=>this.adjustImage(), 50);
      if (!img) return;
      const attrs = this.corpus.layer[this.image.layer].attributes;
      const image_col = Object.entries(attrs).find(kv=>kv[1].type == "image")[0];
      const filename = img[image_col];
      this.name = filename.replace(/\.[^.]+$/,"");
      this.src = this.baseMediaUrl + filename;
    },
    updateImageId(id) {
      if (id < 1) return;
      if (!this.image) return;
      this.layerId = id;
      this.$emit("getImageAnnotations", this.image.layer, id);
      this.updateImageContent();
    }
  },
  computed: {
    nonSegments() {
      const img = this.meta.layer[this.image.layer].byId[this.layerId];
      if (!img) return {};
      const [x1,y1,x2,y2] = img.xy_box;
      const xs = [x1,x2], ys = [y1,y2];
      const ret = {};
      for (let [layer, bys] of Object.entries(this.meta.layer)) {
        const overlapXs = bys.byLocation.searchValue(xs);
        const overlaps = overlapXs.map(o=>o.searchValue(ys)).filter(x=>x.length>0).flat();
        if (overlaps.length==0) continue;
        ret[layer] = [...(ret[layer] || []), ...overlaps];
      }
      return ret;
    },
    allPrepared() {
      const img = this.meta.layer[this.image.layer].byId[this.layerId];
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

      const id = this.layerId;
      const img = this.meta.layer[this.image.layer].byId[id];
      if (!img) return highlights;

      let [x1,y1,x2,y2] = img.xy_box;
      let sortedXs = [x1,x2].sort(n=>parseInt(n)), sortedYs = [y1,y2].sort(n=>parseInt(n));
      const image_offset = [sortedXs[0], sortedYs[0], sortedXs[1], sortedYs[1]];

      for (let [layer, bys] of Object.entries(this.meta.layer)) { // eslint-disable-line no-unused-vars
        const overlapXs = bys.byLocation.searchValue(sortedXs);
        for (let overlaps of overlapXs) {
          for (let o of overlaps.searchValue(sortedYs)) {
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
      this.src = this.image.src;
      this.layerId = this.image.layerId;
      setTimeout(()=>this.adjustImage(), 20);
    }
  },
  mounted() {
    this._keydownhandler = e=>{
      if (e.key == "ArrowLeft") this.updateImageId(this.layerId - 1);
      else if (e.key == "ArrowRight") this.updateImageId(this.layerId + 1);
      else return;
      e.stopPropagation();
      e.preventDefault();
    };
    document.addEventListener("keydown", this._keydownhandler);
    this.adjustImage();
  },
  beforeUnmount() {
    document.removeEventListener("keydown", this._keydownhandler);
  }
};
</script>

<style>
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
  height: 100%;
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
  height: calc(100% - 5em);
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
