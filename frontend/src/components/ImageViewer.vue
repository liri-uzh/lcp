<template>
  <div v-if="onItemPage">
    <strong>Hit:</strong>&nbsp;
    <PlainTokens
      :item="item"
      :columnHeaders="columnHeaders"
      :currentToken="currentToken"
      :resultIndex="0"
      @showPopover="()=>null"
      @closePopover="()=>null"
    />
  </div>
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
    <div class="segment" v-for="(prep, n) in allPrepared" :key="`image-prepared-${n}`">
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

const MARGIN = 10;

export default {
  name: "ImageViewer",
  components: {
    PlainTokens
  },
  data() {
    console.log("layer", this.layer, "layerId", this.layerId, "corpus", this.corpus);
    return {
      zoom: 1,
      offsetX: 0,
      offsetY: 0,
      dragStart: null,
      currentToken: null,
      onItemPage: this.item ? true : false,
    }
  },
  props: ["src", "name", "boxes", "offset", "item", "resultIndex", "columnHeaders", "corpus", "layer", "layerId", "allPrepared"],
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
  },
  computed: {
    highlights() {
      let highlights = [];
      if (this.boxes && this.boxes instanceof Array)
        highlights = [...this.boxes];
      if (this.offset instanceof Array && this.offset.length > 0)
        highlights = highlights.map(([left,top,width,height])=>{
          const [newLeft, newTop] = [Math.max(-1 * MARGIN, left), Math.max(-1 * MARGIN, top)];
          const [newWidth, newHeight] = [
            Math.min(width, this.offset[2]-this.offset[0] + MARGIN - newLeft),
            Math.min(height, this.offset[3]-this.offset[1] + MARGIN - newTop)
          ];
          return [newLeft, newTop, newWidth, newHeight];
        });
      return highlights;
    },
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
