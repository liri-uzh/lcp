<template>
  <div id="selectedReplicator"></div>
  <div ref="image" class="image-container" :style="`transform: scale(${zoom});`">
    <img id="displayedImage" :src="src" @wheel="onWheel"/>
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
</template>

<script>
const MARGIN = 10;

export default {
  name: "ImageViewer",
  data() {
    return {
      zoom: 1
    }
  },
  props: ["src", "boxes", "offset"],
  methods: {
    onWheel(e) {
      e.preventDefault();
      e.stopPropagation();
      this.zoom = Math.max(0.2, Math.min(2.0, this.zoom - e.deltaY/500));
    }
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
    const selectedRow = document.querySelector(".selected .results");
    const selectedReplicator = document.querySelector("#selectedReplicator");
    console.log("selectedRow", selectedRow);
    console.log("selectedReplicator", selectedReplicator);
    if (!selectedReplicator || !selectedRow) return;
    selectedReplicator.innerHTML = "";
    selectedReplicator.appendChild(selectedRow.cloneNode(true));
  },
  beforeUnmount() {
    // pass
  }
};
</script>

<style>
#selectedReplicator {
  margin-bottom: 1em;
}
.image-container {
  position: relative;
  transform-origin: top left;
}
.highlight-box {
  z-index: 99;
  position: absolute;
  border: solid 6px black;
  pointer-events: none;
}
</style>
