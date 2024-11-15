<template>
  <div>
    <div class="button-container">
      <button class="btn btn-primary btn-sm me-1" :disabled="zoomValue <= 1" @click="zoomOut">
        <FontAwesomeIcon :icon="['fas', 'magnifying-glass-minus']" class="me-1" />
        Zoom Out
      </button>
      <input type="range" min="1" :max="MAX_ZOOM_LEVEL" class="zoom-slider" v-model="zoomValue" step="1" />
      <button class="btn btn-primary btn-sm me-1" :disabled="zoomValue >= MAX_ZOOM_LEVEL" @click="zoomIn">
        <FontAwesomeIcon :icon="['fas', 'magnifying-glass-plus']" class="me-1" />
        Zoom In
      </button>
    </div>
    <!--
    <div class="slider-container">
      <input type="range" id="horizontal-slider" min="0" max="156" value="0" step="0.1" />
    </div> -->
    <svg id="timeline-svg"></svg>
  </div>
</template>

<style scoped>
  /* #timeline-svg {
    margin: 0 10px;
  } */
  .button-container {
    margin-left: 178px;
  }
  /* .zoom-slider {
    margin-top: 5px;
  } */
  /*
  .zoom-button {
    margin-right: 5px;
  } */

  /* .slider-container {
    margin-top: 10px;
  } */

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
</style>

<script>
import * as d3 from 'd3'

import Utils from "@/utils.js";

let svg = null;
let zoom;
let linearScale = null;
let currentTime = 0;
let playerState = false;
let hoveringAnnotation = null;
const padding = 180;
const width = document.body.clientWidth - 20;
const paddingBeforeTimeline = 40;
const MAX_ZOOM_LEVEL = 100

// Function to update the vertical timeline
function updateVerticalLine(xPosition) {
  const verticalLine = svg.selectAll(".vertical-line");
  verticalLine.attr("x1", xPosition).attr("x2", xPosition);

  const rightBoundary = width - paddingBeforeTimeline;

  // Hide vertical line
  // console.log("PLB", playButton.checked)
  if (xPosition > rightBoundary) {
    if (playerState) {
      moveRight()
    }
    else {
      verticalLine.attr("opacity", 0);
    }
  }
  else if (xPosition < padding) {
    verticalLine.attr("opacity", 0);
  }
  else {
    verticalLine.attr("opacity", 1);
  }
}

function moveRight() {
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
}

export default {
  name: "TimelineView",
  props: ["data", "playerIsPlaying", "playerCurrentTime", "mediaDuration"],
  data() {
    return {
      defaultCurrentTime: this.playerCurrentTime,
      currentTime: 0,
      zoomValue: 1,
      MAX_ZOOM_LEVEL: MAX_ZOOM_LEVEL,
    }
  },
  watch: {
    playerIsPlaying(){
      playerState = this.playerIsPlaying;
      // console.log("playerState", playerState);
    },
    playerCurrentTime(){
      this.updateCurrentPosition(this.playerCurrentTime)
    },
    zoomValue(){
      const verticalLine = svg.selectAll(".vertical-line");
      const xPosition = verticalLine.attr("x1");
      const scale = this.zoomValue;
      svg.transition().call(zoom.scaleTo, parseFloat(scale), [xPosition, 0]);
    }
  },
  methods: {
    zoomIn() {
      this.zoomValue = Math.min(parseFloat(this.zoomValue) + 1, MAX_ZOOM_LEVEL);
    },
    zoomOut() {
      this.zoomValue = Math.max(parseFloat(this.zoomValue) - 1, 1);
    },
    updateCurrentPosition(time) {
      this.currentTime = time;
      const newXScale = d3.zoomTransform(svg.node()).rescaleX(linearScale);
      updateVerticalLine(newXScale(this.currentTime));
    },
  },
  mounted() {

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
      "#1fa187ff", "#46327eff", "#4ac16dff", "#277f8eff", "#440154ff", "#fde725ff", "#365c8dff", "#a0da39ff"
    ];

    // Set up the SVG container
    // const root = selection.selectAll('#timeline').data(selection.data());
    // root.exit().remove();
    svg = d3.select("#timeline-svg");

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
      .attr("height", totalHeight+40)

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

    // Create zoom behavior
    zoom = d3
      .zoom()
      .scaleExtent([1, 75])
      .translateExtent([
        [padding, -Infinity],
        [width - padding, Infinity],
      ])
      .extent([
        [padding, 0],
        [width - padding, height],
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

    // Zoom event handler
    function zoomed(event) {
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
      const verticalLineX = newXScale(currentTime);
      updateVerticalLine(verticalLineX);
    }

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
        const originalValue = linearScale.invert(clickX);
        const newXScale = d3.zoomTransform(svg.node()).rescaleX(linearScale);
        this.$emit("updateTime", originalValue);
        // this.verticalSlider.value = originalValue
        updateVerticalLine(newXScale(originalValue));
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

        const hovering = barAndTextGroups
          .filter( function () {
            const rect = this.querySelector("rect");
            const {x, y, width, height} = Object.fromEntries([...rect.attributes].map(v=>[v.name,v.value]));
            return x<=mouseOverX && Number(x)+Number(width)>=mouseOverX && y<=mouseOverY && Number(y)+Number(height)>=mouseOverY;
          } );
        if ([...hovering].length && [...hovering][0] != hoveringAnnotation) {
          hoveringAnnotation = [...hovering][0];
          const rect = hoveringAnnotation.querySelector("rect");
          const {x, y, height} = Object.fromEntries([...rect.attributes].map(v=>[v.name,v.value]));
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

        const transform = d3.zoomTransform(svg.node());
        const clickX = transform.invertX(d3.pointer(event)[0]);
        const originalValue = linearScale.invert(clickX);

        d3
          .select(".mouse-text")
          .attr("x", mouseOverX + 5)
          .style('opacity', '1')
          .text(Utils.secondsToTime(originalValue, true));
      });

      this.zoomValue = 20;

      this.updateCurrentPosition(this.defaultCurrentTime);
  },
};
</script>
