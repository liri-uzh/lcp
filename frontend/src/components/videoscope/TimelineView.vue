<template>
  <div>
    <div class="button-container" :style="mobileOrientationStyle">
      <button class="btn btn-primary btn-sm me-1" @click="center">
        Center
      </button>
      <button
        class="btn btn-primary btn-sm me-1"
        :disabled="zoomValue <= 1"
        @click="zoomOut"
      >
        <FontAwesomeIcon
          :icon="['fas', 'magnifying-glass-minus']"
          class="me-1"
        />
        {{ $t("common-zoom-out") }}
      </button>
      <input
        type="range"
        min="1"
        :max="MAX_ZOOM_LEVEL"
        class="zoom-slider me-1"
        v-model="zoomValue"
        step="1"
      />
      <button
        class="btn btn-primary btn-sm me-1"
        :disabled="zoomValue >= MAX_ZOOM_LEVEL"
        @click="zoomIn"
      >
        <FontAwesomeIcon
          :icon="['fas', 'magnifying-glass-plus']"
          class="me-1"
        />
        {{ $t("common-zoom-in") }}
      </button>
      <button class="btn btn-primary btn-sm me-1" @click="resetZoom">
        <FontAwesomeIcon :icon="['fas', 'rotate-left']" class="me-1" />
        {{ $t("common-zoom-reset-default") }}
      </button>
      <button class="btn btn-primary btn-sm me-1" @click="fitZoom">
        <FontAwesomeIcon
          :icon="['fas', 'arrows-left-right-to-line']"
          class="me-1"
        />
        {{ $t("common-zoom-fit-content") }}
      </button>
    </div>
    <!--
    <div class="slider-container">
      <input type="range" id="horizontal-slider" min="0" max="156" value="0" step="0.1" />
    </div> -->
    <div v-if="!isLandscape && isMobile" class="rotation-instructions">
      <FontAwesomeIcon
        :icon="['fas', 'mobile-screen-button']"
        class="rotation-icon"
      />
      <p class="p-0 m-0">{{ $t("common-rotate-device") }}</p>
    </div>
    <svg id="timeline-svg" :style="mobileOrientationStyle"></svg>
  </div>
</template>

<style scoped>
.button-container {
  margin-left: 178px;
}

.button-container > button, .button-container > input {
  margin-top: 5px;
}

* >>> .tooltip-rect {
  fill: #fffffff0;
  stroke: #e6e6e6;
  stroke-width: 1px;
}

svg#timeline-svg {
  cursor: pointer;
  color: #2c3e50;
  font-size: 12px;
}

.mouse-text {
  background-color: #2c3e50;
}

.rotation-icon {
  font-size: 2rem;
  margin-bottom: 10px;
  animation: rotate 2s infinite;
}

.rotation-instructions{
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
  margin-top: 30px;
  margin-bottom: 30px;
}

@keyframes rotate {
  0% {
    transform: rotate(0deg);
  }

  25% {
    transform: rotate(-90deg);
  }

  75% {
    transform: rotate(-90deg);
  }

  100% {
    transform: rotate(0deg);
  }
}

@media screen and (max-width: 768px) and (orientation: portrait) {
  .button-container {
    margin-left: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
}
</style>

<script>
import * as d3 from 'd3'

import Utils from "@/utils.js";

// Global variables
let svg = null;
let zoom;
let linearScale = null;
// eslint-disable-next-line
let playerState = false;
let hoveringAnnotation = null;
const padding = 180;
let width = document.body.clientWidth - 20;
const paddingBeforeTimeline = 40;
const MAX_ZOOM_LEVEL = 200;
const DEFAULT_ZOOM_LEVEL = 20;

export default {
  name: "TimelineView",
  props: ["data", "playerIsPlaying", "playerCurrentTime", "mediaDuration", "hoveredResult"],
  data() {
    return {
      defaultCurrentTime: this.playerCurrentTime,
      currentTime: 0,
      zoomValue: 1,
      MAX_ZOOM_LEVEL: MAX_ZOOM_LEVEL,
      isMobile: false,
      isLandscape: false,
      resizeHandler: null,
    }
  },
  watch: {
    hoveredResult() {
      // console.log("hoveredResult", this.hoveredResult);
      // if (this.hoveredResult && this.hoveredResult instanceof Array && this.hoveredResult.length > 2)
      //   console.log("frame range of hovered line", [...this.hoveredResult[2]]);
    },
    playerIsPlaying() {
      playerState = this.playerIsPlaying;
      this.center();
      // console.log("playerState", playerState);
    },
    playerCurrentTime() {
      this.updateCurrentPosition(this.playerCurrentTime)
    },
    zoomValue() {
      const transform = d3.zoomTransform(svg.node());
      const currentScale = transform.k;
      const scaleRatio = this.zoomValue / currentScale;
      let xPosition = 0;

      // if (!this.playerIsPlaying) {
      //   // Zoom relative to the position of the vertical line
      //   const verticalLine = svg.selectAll(".vertical-line");
      //   xPosition = verticalLine.attr("x1");
      // } else {
      //   // Zoom relative to the center of the timeline
      //   const svgBounds = svg.node().getBoundingClientRect();
      //   xPosition = (svgBounds.width / 2 - transform.x) / currentScale;
      // }

      // Zoom relative to the position of the vertical line
      const verticalLine = svg.selectAll(".vertical-line");
      xPosition = verticalLine.attr("x1");

      // Apply the zoom while keeping the center in place
      svg.transition().call(zoom.scaleBy, scaleRatio, [xPosition, 0]);
    },
  },
  computed: {
    mobileOrientationStyle() {
      // only override on mobile
      if (!this.isMobile) {
        return {}
      }
      // on mobile, choose between landscape vs. portrait
      return {
        visibility:  this.isLandscape ? 'visible' : 'hidden',
        height:      this.isLandscape ? 'auto'    : '0'
      }
    }
  },
  methods: {
    resetZoom() {
      this.zoomValue = DEFAULT_ZOOM_LEVEL;
    },
    fitZoom() {
      this.zoomValue = 1;
    },
    zoomIn() {
      this.zoomValue = Math.min(parseFloat(this.zoomValue) + 1, MAX_ZOOM_LEVEL);
    },
    zoomOut() {
      this.zoomValue = Math.max(parseFloat(this.zoomValue) - 1, 1);
    },
    updateCurrentPosition(time) {
      this.currentTime = time;
      const newXScale = d3.zoomTransform(svg.node()).rescaleX(linearScale);
      this.updateVerticalLine(newXScale(this.currentTime));
      if (!this.playerIsPlaying) {
        this.center();
      }
    },
    // Function to update the vertical timeline
    updateVerticalLine(xPosition) {
      const verticalLine = svg.selectAll(".vertical-line");

      // Get the current transform and the domain [domainStart, domainEnd] after zoom
      const transform = d3.zoomTransform(svg.node());
      const newXScale = transform.rescaleX(linearScale);
      let [domainStart, domainEnd] = newXScale.domain();
      domainStart = Math.max(0, domainStart.toFixed(3));

      // console.log('Position data:', domainStart, this.currentTime, domainEnd, xPosition);
      // console.log(`Position data / start: ${domainStart}, current: ${this.currentTime}, end: ${domainEnd}, new position: ${xPosition}`);

      // If the global currentTime is in the visible domain, show the line; otherwise hide it
      const inDomain = (this.currentTime >= domainStart && this.currentTime <= domainEnd);

      // console.log('IN DOMAIN? ', inDomain)
      verticalLine
        .attr("x1", xPosition)
        .attr("x2", xPosition)
        .attr("opacity", inDomain ? 1 : 0);

      if (this.currentTime > domainEnd) {
        if (playerState) {
          this.moveRight();
        }
      }
    },
    center() {
      // Get the current transform and the current SVG dimensions.
      const currentTransform = d3.zoomTransform(svg.node());
      const svgBounds = svg.node().getBoundingClientRect();
      const svgWidth = svgBounds.width; // use the current rendered width

      // Create a scale based on the current transform.
      const newXScale = currentTransform.rescaleX(linearScale);

      // Compute the pixel position (under the current transform) for the current time.
      const currentX = newXScale(this.currentTime);

      // Compute the visible area in pixels.
      // (Assuming your clip area starts at "padding" and extends to (svgWidth - paddingBeforeTimeline))
      const visibleWidth = svgWidth - padding - paddingBeforeTimeline;
      const centerPixel = padding + visibleWidth / 2;

      // Compute how much (in pixels) we want to shift the timeline so that currentX becomes centered.
      let dx = centerPixel - currentX;
      let desiredX = currentTransform.x + dx;

      // --- Left Boundary Clamp ---
      // Under your base linearScale, data value 0 maps to "padding".
      // With a transform, the left edge appears at: currentTransform.x + currentTransform.k * padding.
      // We want to keep that ≤ padding.
      // Rearranging gives:
      //    currentTransform.x ≤ padding - currentTransform.k * padding = padding * (1 - currentTransform.k)
      const minAllowedX = padding * (1 - currentTransform.k);
      desiredX = Math.min(desiredX, minAllowedX);

      // --- Right Boundary Clamp ---
      // The right edge of your content (data value = this.mediaDuration) maps to:
      //   linearScale(this.mediaDuration)
      // With the transform it’s at: currentTransform.x + currentTransform.k * linearScale(this.mediaDuration)
      // We want that to be exactly at the right visible boundary:
      //   svgWidth - paddingBeforeTimeline
      // Solving for the x translation gives:
      //   desiredX = (svgWidth - paddingBeforeTimeline) - currentTransform.k * linearScale(this.mediaDuration)
      const maxAllowedX = (svgWidth - paddingBeforeTimeline) - currentTransform.k * linearScale(this.mediaDuration);
      desiredX = Math.max(desiredX, maxAllowedX);

      // Build the new transform with the clamped translation.
      const newTransform = d3.zoomIdentity
        .translate(desiredX, currentTransform.y)
        .scale(currentTransform.k);

      // Apply the new transform with a smooth transition.
      svg.transition().call(zoom.transform, newTransform);
    },
    moveLeft() {

      const currentTransform = d3.zoomTransform(svg.node());
      const newXScale = currentTransform.rescaleX(linearScale);

      // Get the width of the visible range
      const visibleWidth = newXScale.range()[1] - newXScale.range()[0];

      // Get the width of the entire data range
      const totalWidth = newXScale.domain()[1] - newXScale.domain()[0];

      // Calculate the amount to move the graph to the right (one width)
      const moveAmount = totalWidth - visibleWidth;

      // Calculate the new translation along the x-axis
      const newTx = currentTransform.x - moveAmount;

      // Update the zoom transform with the new translation
      svg.call(zoom.transform, d3.zoomIdentity.translate(newTx, currentTransform.y).scale(currentTransform.k));
    },
    moveRight() {
      console.log('MOVING RIGHT');
      const currentTransform = d3.zoomTransform(svg.node());
      const newXScale = currentTransform.rescaleX(linearScale);

      // Get the width of the visible range
      const visibleWidth = newXScale.range()[1] - newXScale.range()[0];

      // Get the width of the entire data range
      const totalWidth = newXScale.domain()[1] - newXScale.domain()[0];

      // Calculate the amount to move the graph to the right (one width)
      const moveAmount = totalWidth - visibleWidth;

      // Calculate the new translation along the x-axis
      const newTx = currentTransform.x + moveAmount;

      // Update the zoom transform with the new translation
      svg.call(zoom.transform, d3.zoomIdentity.translate(newTx, currentTransform.y).scale(currentTransform.k));
      this.center();
    },
    setResizeOrientationListeners() {
      // kick off initial check and update on resize/orientationchange
      window.addEventListener('resize', this.resizeHandler);
      window.addEventListener('orientationchange', this.resizeHandler);
    },
    checkMobile(e) {
      if(e.type !== "resize" && e.type !== "orientationchange") return;

      this.isMobile = window.innerWidth  < 768;
      this.isLandscape = window.innerWidth  >  window.innerHeight;

      // Set the new screen width
      width = document.body.clientWidth - 20;

      this.initializeTimeline();
      this.updateCurrentPosition(this.currentTime);
    },
    initializeTimeline() {
      this.setResizeOrientationListeners();
    // Example
    // const data = [
    //   {
    //     name: "Row 1",
    //     heightLines: 1,
    //     values: [
    //       { x1: 9.85, x2: 15, n: "Text 1", l: 0 },
    //       { x1: 25, x2: 28, n: "Text 2", l: 0 },
    //       { x1: 40, x2: 47, n: "Text 3", l: 0 },
    //     ],
    //   },
    //   {
    //     name: "Row 2",
    //     heightLines: 1,
    //     values: [
    //       { x1: 20, x2: 22, n: "Text 4", l: 1 },
    //       { x1: 35, x2: 40, n: "Text 5", l: 1 },
    //       { x1: 41, x2: 45, n: "Text 6", l: 1 },
    //       { x1: 55, x2: 156, n: "Text 7", l: 1 },
    //     ],
    //   },
    //   {
    //     name: "Row 3",
    //     heightLines: 1,
    //     values: [
    //       { x1: 20, x2: 22, n: "Text 4", l: 2 },
    //       { x1: 35, x2: 40, n: "Text 5", l: 2 },
    //       { x1: 41, x2: 45, n: "Text 6", l: 2 },
    //       { x1: 55, x2: 156, n: "Text 7", l: 2 },
    //     ],
    //   },
    //   {
    //     name: "Row 4",
    //     heightLines: 1,
    //     values: [
    //       { x1: 20, x2: 22, n: "Text 4", l: 3 },
    //       { x1: 35, x2: 40, n: "Text 5", l: 3 },
    //       { x1: 41, x2: 45, n: "Text 6", l: 3 },
    //       { x1: 55, x2: 156, n: "Text 7", l: 3 },
    //     ],
    //   },
    // ];

    // Utils.frameNumberToSeconds

    // const searchResults = [
    //   { x: 20, n: "Text 4", l: 2 },
    //   { x: 45, n: "Text 4", l: 1 },
    // ]

    // https://waldyrious.net/viridis-palette-generator/
    const barColors = [
      // "#fde725", "#a0da39", "#4ac16d", "#1fa187", "#277f8e", "#365c8d", "#46327e", "#440154"
      "#1fa187ff", "#46327eff", "#4ac16dff", "#277f8eff", "#440154ff", "#fdaa25ff", "#365c8dff", "#a0da39ff"
    ];

    // Set up the SVG container
    // const root = selection.selectAll('#timeline').data(selection.data());
    // root.exit().remove();
    svg = d3.select("#timeline-svg");
    svg.selectAll("*").remove();

    // Create the scaleLinear
    linearScale = d3.scaleLinear().domain([0, this.mediaDuration]).range([padding, width - 1]);

    let data = [...this.data];

    // Add names to the chart
    let heightStart = {}
    let totalHeight = 50; // Height before the first row
    svg
      .selectAll(".name")
      .data(data)
      .enter()
      .append("text")
      .attr("class", "name")
      .attr("x", d => 10 + 20 * (d.level ? d.level : 0))
      .attr("y", (d, i) => {
        let height = totalHeight + 10
        totalHeight += d.heightLines * 15 + 10
        heightStart[i] = height
        return height + 13
      })
      .text((d) => d.name);

    let height = totalHeight + 20
    // svg.attr("height", height).attr("width", "calc(100% - 40px)");
    svg.attr("height", height).attr("width", "100%");

    svg
      .append("clipPath")
      .attr("id", "myClip")
      .append("rect")
      .attr("x", "180")
      .attr("y", "40")
      .attr("width", width - padding)
      .attr("height", totalHeight + 40);

    // Create a single group for all bars
    const barsGroup = svg.append("g").attr("clip-path", "url(#myClip)");

    // Create individual groups for each bar and its text label
    const barAndTextGroups = barsGroup.selectAll("g")
      .data(data.flatMap(d => d.values))
      .enter()
      .append("g")
      .attr("clip-path", (d, i) => `url(#barClip${i})`); // Unique clip-path for each group

    // Define a clip path for each group
    barAndTextGroups.append("clipPath")
      .attr("id", (d, i) => `barClip${i}`)
      .append("rect")
      .attr("x", (d) => linearScale(d.x1))
      .attr("y", (d) => heightStart[d.l])
      .attr("width", (d) => linearScale(d.x2) - linearScale(d.x1))
      .attr("height", 20);

    // Create bars within each bar and text group
    barAndTextGroups
      .append("rect")
      .attr("rx", "2")
      .attr("x", (d) => linearScale(d.x1))
      .attr("y", (d) => heightStart[d.l])
      .attr("width", (d) => linearScale(d.x2) - linearScale(d.x1))
      .attr("height", 20) // Height of the bars
      // .attr("fill", (d) => (d.l % 2 === 0 ? "#622A7F" : "#005aa3"));
      .attr("fill", (d) => (barColors[d.l % barColors.length]));

    // Add text labels to the bar and text groups
    barAndTextGroups
      .append("text")
      .attr("x", (d) => linearScale(d.x1) + 3)
      .attr("y", (d) => heightStart[d.l] + 14)
      .text((d) => d.n)
      .attr("fill", "white");

    // END OF THE BARS

    // Add x-axis group
    const xAxisGroup = svg
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0, ${paddingBeforeTimeline})`);

    // Add initial x-axis
    let tickPadding = 6;
    const xAxis = d3
      .axisTop(linearScale)
      .tickFormat(d => {
        return Utils.secondsToTime(d)
      })
      .tickPadding(tickPadding);
    xAxisGroup.call(xAxis);


    // Zoom event handler
    const zoomed = (event) => {
      // if (event.sourceEvent && event.sourceEvent.type === "wheel") {
      //   return true;
      // }
      const { transform } = event;
      const newXScale = transform.rescaleX(linearScale);
      xAxis.scale(newXScale);
      xAxisGroup.call(xAxis);

      // Update the bars
      barsGroup
        .selectAll("rect")
        .attr("x", (d) => newXScale(d.x1))
        .attr("width", (d) => newXScale(d.x2) - newXScale(d.x1));

      // Update the text
      barsGroup.selectAll("text").attr("x", (d) => newXScale(d.x1) + 5);

      // Update the vertical line
      // const sliderValue = parseFloat(d3.select("#vertical-slider").node().value);
      const verticalLineX = newXScale(this.currentTime);

      // console.log("zoomed -> currentTime:", this.currentTime, " new domain:", newXScale.domain());

      this.updateVerticalLine(verticalLineX);
    }

    // Create zoom behavior
    zoom = d3
      .zoom()
      .scaleExtent([1, 200])
      .translateExtent([
        [padding, -Infinity],
        [width, Infinity],
      ])
      .extent([
        [padding, 0],
        [width, height],
      ])
      .on("zoom", zoomed);

    // Apply zoom behavior to SVG
    svg.call(zoom).on("wheel.zoom", null)
    // .on("wheel.zoom", event => {
    //   if (event.ctrlKey == true) {
    //     zoomed(d3.event)
    //     event.preventDefault();
    //   }
    //   return null
    // });

    // Zoom control event handlers
    // const zoomInButton = document.getElementById("zoom-in");
    // const zoomOutButton = document.getElementById("zoom-out");

    // zoomInButton.addEventListener("click", () => {
    //   // const scale = d3.zoomTransform(svg.node()).k;
    //   svg.transition().call(zoom.scaleBy, 1.2);
    // });

    // zoomOutButton.addEventListener("click", () => {
    //   // const scale = d3.zoomTransform(svg.node()).k;
    //   svg.transition().call(zoom.scaleBy, 0.8);
    // });

    // Zoom slider event handler
    // const zoomSlider = document.getElementById("zoom-slider");
    // zoomSlider.addEventListener("input", () => {
    //   svg.transition().call(zoom.scaleTo, parseFloat(zoomSlider.value));
    // });

    // // Get the horizontal slider element
    // const horizontalSlider = document.getElementById("horizontal-slider");

    // let lastHorizonatlValue = 0
    // // Add event listener for slider input
    // horizontalSlider.addEventListener("input", () => {
    //   const xOffset = horizontalSlider.value - lastHorizonatlValue;
    //   const currentTransform = d3.zoomTransform(svg.node());
    //   const newTx = currentTransform.x - xOffset;
    //   // const newXScale = currentTransform.rescaleX(linearScale);
    //   svg.call(zoom.transform, d3.zoomIdentity.translate(newTx, 0).scale(currentTransform.k));
    //   lastHorizonatlValue = horizontalSlider.value
    // });

    // Initial position of the vertical line
    const initialXPosition = linearScale(0);

    // const verticalLine =
    svg
      .append("line")
      .attr("class", "vertical-line")
      .attr("x1", initialXPosition)
      .attr("y1", 32) // Padding of the current time line
      .attr("x2", initialXPosition)
      .attr("y2", height)
      .attr("stroke", "red")
      .attr("stroke-width", 1);

    // const mouseLine =
    svg
      .append("line")
      .attr("class", "mouse-line")
      .attr("x1", initialXPosition)
      .attr("y1", 0)
      .attr("x2", initialXPosition)
      .attr("y2", height)
      .attr("stroke", "#0050bf")
      .attr("stroke-width", 1)
      .attr("opacity", 0);

    // const mouseText =
    svg
      .append("text")
      .attr("class", "mouse-text")
      .attr("x", initialXPosition)
      .attr("y", 10)
      .attr("fill", "#0050bf")
      .attr("font-size", "11px")
      .attr("opacity", 0);

    const mouseG = svg
      .append('g')
      .attr('class', 'mouse-over-effects')

    // mouseG
    //   .append('path') // this is the black vertical line to follow mouse
    //   .attr('class', 'mouse-line')
    //   .style('stroke', '#4d4d4d')
    //   .style('stroke-width', '1px')
    //   .style('opacity', '1')

    mouseG
      .append('svg:rect') // append a rect to catch mouse movements on canvas
      .attr('width', width - padding) // can't catch mouse events on a g element
      .attr('height', height)
      .attr('x', padding + 1)
      .attr('fill', 'none')
      .attr('pointer-events', 'all')
      .on('click', () => {
        const transform = d3.zoomTransform(svg.node());
        const clickX = transform.invertX(d3.pointer(event)[0]);
        let originalValue = linearScale.invert(clickX);
        originalValue = Math.max(0, Math.min(originalValue, this.mediaDuration)); // Don't accept values outside the media duration
        const newXScale = d3.zoomTransform(svg.node()).rescaleX(linearScale);
        this.$emit("updateTime", originalValue);
        // this.verticalSlider.value = originalValue
        this.updateVerticalLine(newXScale(originalValue));
        if (hoveringAnnotation) {
          hoveringAnnotation._stick = !hoveringAnnotation._stick;
          const rect = hoveringAnnotation.querySelector("rect:nth-child(2)");
          rect.style.strokeWidth = hoveringAnnotation._stick ? "3" : "0";
          rect.style.stroke = "red";
          this.$emit("annotationClick", hoveringAnnotation._stick);
        }
      })
      .on('mouseout', function () {
        // on mouse out hide line, circles and text
        d3.select('.mouse-line').style('opacity', '0');
        d3.select('.mouse-text').style('opacity', '0');
      })
      .on('mouseover', function () {
        // on mouse in show line, circles and text
        d3.select('.mouse-line').style('opacity', '0.5');
        d3.select('.mouse-text').style('opacity', '0.5');
      })
      .on('mousemove', () => {
        const [mouseOverX, mouseOverY] = d3.pointer(event).slice(0, 2);
        // const mouseOverX = d3.pointer(event)[0]
        d3
          .select(".mouse-line")
          .attr("x1", mouseOverX)
          .attr("x2", mouseOverX)
          .style('opacity', '1');

        const transform = d3.zoomTransform(svg.node());
        const clickX = transform.invertX(d3.pointer(event)[0]);
        const originalValue = linearScale.invert(clickX);

        d3
          .select(".mouse-text")
          .attr("x", mouseOverX + 5)
          .style('opacity', '1')
          .text(Utils.secondsToTime(originalValue, true));

        if (hoveringAnnotation && hoveringAnnotation._stick) return;

        const hovering = barAndTextGroups
          .filter(function () {
            const rect = this.querySelector("rect");
            const { x, y, width, height } = Object.fromEntries([...rect.attributes].map(v => [v.name, v.value]));
            return x <= mouseOverX && Number(x) + Number(width) >= mouseOverX && y <= mouseOverY && Number(y) + Number(height) >= mouseOverY;
          });
        if ([...hovering].length && [...hovering][0] != hoveringAnnotation) {
          hoveringAnnotation = [...hovering][0];
          const rect = hoveringAnnotation.querySelector("rect");
          const { x, y, height } = Object.fromEntries([...rect.attributes].map(v => [v.name, v.value]));
          const event = {
            x: Number(x),
            y: Number(y) + Number(height),
            mouseX: mouseOverX,
            mouseY: mouseOverY,
            entry: hovering.data()[0].entry
          }
          this.$emit("annotationEnter", event);
        }
        else if ([...hovering].length == 0 && hoveringAnnotation) {
          hoveringAnnotation = null;
          this.$emit("annotationLeave");
        }
      });

    this.zoomValue = DEFAULT_ZOOM_LEVEL;

    this.updateCurrentPosition(this.currentTime > 0 ? this.currentTime : this.defaultCurrentTime);
    }
  },
  mounted() {
    // Create a debounced resize handler and save a reference
    this.resizeHandler = (e) => {
      clearTimeout(this._resizeTimeout)
      this._resizeTimeout = setTimeout(() => this.checkMobile(e), 200)
    }
    // Initialize the timeline
    this.initializeTimeline();
  },
  beforeUnmount(){
    window.removeEventListener('resize', this.resizeHandler)
    window.removeEventListener('orientationchange', this.resizeHandler)
  }
};
</script>
