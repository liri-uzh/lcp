<template>
  <div id="prev-image" @click="updateImageId(layerId - 1)"> &lt; </div>
  <div id="next-image" @click="updateImageId(layerId + 1)"> &gt; </div>
  <span>{{ image.layer }} #{{ layerId }}</span>
  <div
    ref="image"
    class="image-container"
    @pointermove="onPointerMove"
    @pointerup="onPointerStop"
    @pointercancel="onPointerStop"
    :style="`transform: scale(${zoom}) translate(${offsetX}px, ${offsetY}px);`"
  >
    <img
      id="displayedImage"
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
  <div id="imageAllPrepared" v-if="allPrepared instanceof Array && allPrepared.length > 0">
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
    updageImageContent() {
      const id = this.layerId;
      const img = this.meta.layer[this.image.layer].byId[id];
      if (!img) return;
      const attrs = this.corpus.layer[this.image.layer].attributes;
      const image_col = Object.entries(attrs).find(kv=>kv[1].type == "image")[0];
      const filename = img[image_col];
      this.name = filename.replace(/\.[^.]+$/,"");
      this.src = this.baseMediaUrl + filename;
    },
    updateImageId(id) {
      if (id < 0) return;
      if (!this.image) return;
      this.layerId = id;
      this.$emit("getImageAnnotations", this.image.layer, id);
      this.updageImageContent();
    }
  },
  computed: {
    allPrepared() {
      const img = this.meta.layer[this.image.layer].byId[this.layerId];
      if (!img) return [];

      const prepared = [];
      const segments = this.meta.layer[this.corpus.segment].byStream.searchValue([...img.char_range].sort());
      for (let segment of segments) {
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
      let sortedXs = [x1,x2].sort(), sortedYs = [y1,y2].sort();
      const image_offset = [sortedXs[0], sortedYs[0], sortedXs[1], sortedYs[1]];

      for (let [layer, bys] of Object.entries(this.meta.layer)) { // eslint-disable-line no-unused-vars
        const overlapXs = bys.byLocation.searchValue(sortedXs);
        for (let overlaps of overlapXs) {
          for (let o of overlaps.searchValue(sortedYs)) {
            if (!o || !o.xy_box) continue;
            [x1,x2,y1,y2] = [...[o.xy_box[0], o.xy_box[2]].sort(), ...[o.xy_box[1], o.xy_box[3]].sort()];
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
  mounted() {
    // pass
  },
  beforeUnmount() {
    // pass
  }
};
</script>

<style>
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
#imageAllPrepared {
  position: absolute;
  right: 0;
  top: 0;
  max-width: 50%;
  margin-right: 1em;
  height: 100%;
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
