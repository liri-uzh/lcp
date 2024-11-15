<template>
  <div id="dep-rel-view">
  </div>
</template>

<style scoped>
  #dep-rel-view {
    padding-top: 20px;
    height: 60vh;
  }
  * >>> svg {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 12px;
    scale: 1.5;
    transform-origin: top left;
  }
  * >>> svg .dep-text,
  * >>> svg .link-text {
    font-size: 9px;
  }
  * >>> svg g.text-form text.label-root {
    text-decoration: underline;
  }
  * >>> svg g.text-pos {
    font-size: 80%;
    font-weight: bold;
    fill: #1e9989;
  }
  * >>> svg g.text-lemma {
    font-size: 80%;
  }

  /* Deafult line link color */
  * >>> svg line.link-line {
    stroke:#b0b0b0;
    stroke-width: 1px;
  }
  * >>> svg .link-pointer {
    fill: #b0b0b0;
  }
  * >>> svg text.link-text {
    fill:#b0b0b0;
  }

  /* Group 1 - Issue #199 */
  * >>> svg g.links g.link-type-nsubj line.link-line,
  * >>> svg g.links g.link-type-obj line.link-line,
  * >>> svg g.links g.link-type-iobj line.link-line,
  * >>> svg g.links g.link-type-csubj line.link-line,
  * >>> svg g.links g.link-type-ccomp line.link-line,
  * >>> svg g.links g.link-type-xcomp line.link-line {
    stroke: #5b77ae;
  }
  * >>> svg g.links g.link-type-nsubj text.link-text,
  * >>> svg g.links g.link-type-obj text.link-text,
  * >>> svg g.links g.link-type-iobj text.link-text,
  * >>> svg g.links g.link-type-csubj text.link-text,
  * >>> svg g.links g.link-type-ccomp text.link-text,
  * >>> svg g.links g.link-type-xcomp text.link-text {
    fill: #003ebb;
  }

  /* Group 2 - Issue #199 */
  * >>> svg g.links g.link-type-obl line.link-line,
  * >>> svg g.links g.link-type-vocative line.link-line,
  * >>> svg g.links g.link-type-expl line.link-line,
  * >>> svg g.links g.link-type-dislocated line.link-line,
  * >>> svg g.links g.link-type-advcl line.link-line,
  * >>> svg g.links g.link-type-advmod line.link-line,
  * >>> svg g.links g.link-type-discourse line.link-line,
  * >>> svg g.links g.link-type-aux line.link-line,
  * >>> svg g.links g.link-type-cop line.link-line,
  * >>> svg g.links g.link-type-mark line.link-line {
    stroke: #9d0000;
  }
  * >>> svg g.links g.link-type-obl text.link-text,
  * >>> svg g.links g.link-type-vocative text.link-text,
  * >>> svg g.links g.link-type-expl text.link-text,
  * >>> svg g.links g.link-type-dislocated text.link-text,
  * >>> svg g.links g.link-type-advcl text.link-text,
  * >>> svg g.links g.link-type-advmod text.link-text,
  * >>> svg g.links g.link-type-discourse text.link-text,
  * >>> svg g.links g.link-type-aux text.link-text,
  * >>> svg g.links g.link-type-cop text.link-text,
  * >>> svg g.links g.link-type-mark text.link-text {
    fill: #9d0000;
  }

  /* Group 3 - Issue #199 */
  * >>> svg g.links g.link-type-nmod line.link-line,
  * >>> svg g.links g.link-type-appos line.link-line,
  * >>> svg g.links g.link-type-nummod line.link-line,
  * >>> svg g.links g.link-type-acl line.link-line,
  * >>> svg g.links g.link-type-amod line.link-line,
  * >>> svg g.links g.link-type-det line.link-line,
  * >>> svg g.links g.link-type-clf line.link-line,
  * >>> svg g.links g.link-type-case line.link-line {
    stroke: #7bcc85;
  }
  * >>> svg g.links g.link-type-nmod text.link-text,
  * >>> svg g.links g.link-type-appos text.link-text,
  * >>> svg g.links g.link-type-nummod text.link-text,
  * >>> svg g.links g.link-type-acl text.link-text,
  * >>> svg g.links g.link-type-amod text.link-text,
  * >>> svg g.links g.link-type-det text.link-text,
  * >>> svg g.links g.link-type-clf text.link-text,
  * >>> svg g.links g.link-type-case text.link-text {
    fill: #548c5b;
  }
</style>

<script>
import * as d3 from 'd3'

const browserText = (function () {
  const canvas = document.createElement('canvas'),
      context = canvas.getContext('2d');

  function getWidth(text, fontSize, fontFace) {
      context.font = fontSize + 'px ' + fontFace;
      return context.measureText(text).width;
  }

  return {
      getWidth: getWidth
  };
})()

export default {
  name: "DepRelView",
  props: ["data", "sentences", "columnHeaders"],
  data(){
    const { tokens, links } = this.buildGraphData(this.data, this.sentences)
    return {
      tokens: tokens,
      links: links,
      tokenSpace: 25,
    }
  },
  methods: {
    buildGraphData(data, sentences) {
      // let startId = this.data[1]
      let startId = sentences[0]
      let tokens = []
      let links = []
      let sumX = 0
      let matrix = []
      let linksDict = {}
      let groups = {}

      data[1].forEach( (tokenIdOrArray,groupId) => tokenIdOrArray instanceof Array
        ? tokenIdOrArray.forEach( (tokenId) => groups[tokenId] = tokenId in groups ? groups[tokenId] : groupId )
        : groups[tokenIdOrArray] = tokenIdOrArray in groups ? groups[tokenIdOrArray] : groupId
      )

      let form_id = this.columnHeaders.indexOf("form");
      let lemma_id = this.columnHeaders.indexOf("lemma");
      let pos_id = this.columnHeaders.findIndex(v=>v.endsWith("pos"));
      let head_id = this.columnHeaders.indexOf("head");
      let label_id = this.columnHeaders.indexOf("label");
      if (label_id < 0)
        label_id = this.columnHeaders.indexOf("udep"); // replace this with looking up the first categorical attribute
      let large_index_counter = 5000;

      // Compile tokens and link matrix
      sentences[1].forEach((token, index) => {
        let textWidth = browserText.getWidth(token[form_id], 12, "Arial")
        let typeWidth = browserText.getWidth(token[pos_id], 12, "Arial")
        let currentTokenId = startId + index
        tokens.push({
          id: currentTokenId,
          // name: startId + index
          form: token[form_id],
          lemma: token[lemma_id],
          pos: token[pos_id],
          width: textWidth,
          sumX: sumX,
          group: currentTokenId in groups ? `color-group-${groups[currentTokenId]}` : ''
        })
        sumX += Math.max(textWidth, typeWidth)

        // Matrix
        if (head_id) {
          let currentTokenIndex = index
          let targetTokenIndex = token[head_id] - startId
          let targetTokenId = token[head_id]
          let indexLevel = Math.abs(targetTokenIndex - currentTokenIndex)

          if (!(indexLevel in linksDict)) {
            linksDict[indexLevel] = []
          }

          linksDict[indexLevel].push({
            source: currentTokenId,
            target: targetTokenId,
            label: token[label_id],
            originalLevel: indexLevel > 5000 ? large_index_counter++ : indexLevel,
          })
        }
      })

      while (large_index_counter-- > 0) {
        matrix.push([])
      }

      // Compile links
      Object.keys(linksDict).sort((a, b) => a - b).forEach(levelIndex => {
        linksDict[levelIndex].forEach(link => {
          let level = link.originalLevel
          let sourceIndex = link.source - startId
          let targetIndex = link.target - startId

          if (targetIndex < sourceIndex) {
            [sourceIndex, targetIndex] = [targetIndex, sourceIndex];
          }

          // Check level
          while (
            level > 1 &&
            (
              matrix.length < level ||
              matrix[level - 1].slice(sourceIndex, targetIndex).reduce((a, b) => a + b, 0) == 0
            )
          ) {
            level -= 1
          }
          if (matrix[level].length < targetIndex) {
            let extendArray = new Array(targetIndex - matrix[level].length + 1).fill(0)
            matrix[level].push.apply(matrix[level], extendArray)
          }
          matrix[level].fill(1, sourceIndex, targetIndex + 1)

          links.push({
            ...link,
            level: level,
          })
        })
      })
      return { tokens, links }
    },
    // calcArc(link) {
    //   let startId = this.data[2]
    //   let sourceIndex = link.source - startId
    //   let targetIndex = link.target - startId
    //   let startX = this.tokens[sourceIndex].sumX + this.tokens[sourceIndex].width/2 + sourceIndex*this.tokenSpace
    //   let endX = this.tokens[targetIndex ].sumX + this.tokens[targetIndex].width/2 + targetIndex*this.tokenSpace
    //   if (startX > endX) {
    //     let tmp = startX
    //     startX = endX
    //     endX = tmp
    //   }

    //   const r = Math.hypot(endX - startX, 0)*1.2;
    //   return `
    //     M${startX},60
    //     A${r},${r} 0 0,1 ${endX},60
    //   `;
    // },
    calcLine(link) {
      let diff = Math.abs(link.target - link.source)
      let startId = this.sentences[0]
      let sourceIndex = link.source - startId
      let targetIndex = link.target - startId
      let startX = this.tokens[sourceIndex].sumX + this.tokens[sourceIndex].width/2 + sourceIndex*this.tokenSpace
      if (!(targetIndex in this.tokens))
        return [startX,startX+4,0,'start'];
      let endX = this.tokens[targetIndex].sumX + this.tokens[targetIndex].width/2 + targetIndex*this.tokenSpace
      let arrowPlacment = 'end';
      if (startX > endX) {
        let tmp = startX
        startX = endX
        endX = tmp
        arrowPlacment = 'start'
      }
      return [startX + 2, endX - 2, 70 - diff*10, arrowPlacment]
    },
  },
  mounted() {
    const countTokens = this.tokens.length
    const totalWidth = this.tokens[countTokens - 1].sumX + this.tokens[countTokens - 1].width + countTokens*this.tokenSpace + 100

    let maxLevel = Math.max(...Object.values(this.links).map(link => link.level))
    var margin = { top: 40, right: 30, bottom: 20, left: 50 },
      width = totalWidth - margin.left - margin.right,
      height = 110 + maxLevel*15 - margin.top - margin.bottom;

    d3.select("div#dep-rel-view").html('')
    const svg = d3.select("div#dep-rel-view").append("svg")
      .attr("width", width + margin.right + margin.left)
      .attr("height", height + margin.top + margin.bottom)
      .attr("viewBox", [0, 0, width, height])
      // .style("font", "10px sans-serif");

    svg.append("defs")
      .append("marker")
        .attr("id", "link-pointer")
        .attr("markerWidth", 10)
        .attr("markerHeight", 7)
        .attr("orient", "auto")
        .attr("refX", 4)
        .attr("refY", 3)
        .append("polygon")
          .attr("class", "link-pointer")
          .attr("points", "0 0, 5 3, 0 6")

    // eslint-disable-next-line no-case-declarations
    let filters = ['head','dep'].map( (id)=> svg.select("defs")
      .append("filter")
        .attr("id", id)
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", 1)
        .attr("height", 1)
    )
    filters.forEach( (f) => {
      f.append("feFlood").attr("flood-color", f.attr('id')=='head' ? "#1e999967" : "#2a7f62")
      f.append("feComposite").attr("in", "SourceGraphic")
    })

    let label_id = this.columnHeaders.indexOf("label");
    if (label_id < 0)
      label_id = this.columnHeaders.indexOf("udep"); // replace this with looking up first categorical column
    svg.append("g")
    .attr("class", "text-form")
      .selectAll("text")
      .data(this.tokens)
      .join("text")
      // .attr("class", d => (d.id >= this.data[1] && d.id <= this.data.at(-1)) ? "text-bold text-danger" : "")
      .attr("class", (d,i) => d.group + ' ' + (this.sentences && this.sentences[1] ? `label-${this.sentences[1][i][label_id]}` : '') )
      .text(d => d.form)
      .attr("x", (d, index) => (this.tokenSpace * index + d.sumX))
      .attr("y", 10 + maxLevel*15)
      .attr("filter", d => `url(#${d.id})` )
      .on("mouseenter", d => {
        let tid = d.target.getAttribute("filter").replace(/\D/g,'')
        filters[1].attr("id", tid)
        filters[0].attr("id", (this.links.find( (l)=>l.source==tid ) || {target:null}).target )
      })
      .on("mouseleave", () => filters.map( (f,i) => f.attr("id", i==0?'head':'dep') ) )

    svg.append("g")
    .attr("class", "text-lemma")
      .selectAll("text")
      .data(this.tokens)
      .join("text")
      .text(d => d.lemma)
      .attr("x", (d, index) => (this.tokenSpace * index + d.sumX))
      .attr("y", 35 + maxLevel*15);

    svg.append("g")
      .attr("class", "text-pos")
      .selectAll("text")
      .data(this.tokens)
      .join("text")
      .text(d => d.pos)
      .attr("x", (d, index) => (this.tokenSpace * index + d.sumX))
      .attr("y", 52 + maxLevel*15);

    // svg.append("g")
    //   .selectAll("path")
    //   .data(this.links)
    //   .join("path")
    //   .attr("d", d => this.calcArc(d))
    //   .attr("stroke", "#1e9989")
    //   .attr("id", (d, index) => `link-${index}`)
    //   .attr("fill", "transparent")
    //   .exit()

    // svg.append("g")
    //   .attr("class", "dep-text")
    //   .selectAll("text")
    //   .data(this.links)
    //   .join("text")
    //   .attr("x", d => `${d.offset}px`)
    //   .attr("baseline-shift", "-7px")
    //   .append("textPath")
    //     .attr("fill", "#1e9989")
    //     .attr("xlink:href", (d, index) => `#link-${index}`)
    //     // .attr("startOffset", "-50%")
    //     .text(d => d.label)

    let links = svg.append("g")
      .attr("class", "links")
      .selectAll(".deprel-link")
      .data(this.links.filter( l => (l.label||l.udep) != "root" ))
      .enter()
      .append("g")
      .attr("class", d => `link-type-${d.label||d.udep}`)

    links.append("line")
          .attr("x1", d => this.calcLine(d)[0] + 4)
          .attr("x2", d => this.calcLine(d)[1] - 4)
          .attr("y1", d => (maxLevel*15 - d.level*15))
          .attr("y2", d => (maxLevel*15 - d.level*15))
          .attr("class", "link-line")
    links.append("line")
          .attr("x1", d => this.calcLine(d)[0] + 4)
          .attr("x2", d => this.calcLine(d)[0])
          .attr("y1", d => (maxLevel*15 - d.level*15))
          .attr("y2", d => (maxLevel*15 - d.level*15) + 7)
          .attr("class", "link-line")
          .attr("marker-end", d => this.calcLine(d)[3] == "end" ? "url(#link-pointer)" : "")
    links.append("line")
          .attr("x1", d => this.calcLine(d)[1] - 4)
          .attr("x2", d => this.calcLine(d)[1])
          .attr("y1", d => (maxLevel*15 - d.level*15))
          .attr("y2", d => (maxLevel*15 - d.level*15) + 7)
          .attr("class", "link-line")
          .attr("marker-end", d => this.calcLine(d)[3] == "start" ? "url(#link-pointer)" : "")
    links.append("text")
          .attr("x", d => (this.calcLine(d)[0] + this.calcLine(d)[1])/2)
          .attr("y", d => (maxLevel*15 - 5 - d.level*15))
          .attr("class", "link-text")
          .attr("text-anchor", "middle")
          .attr("dominant-baseline", "middle")
          .text(d => d.label || d.udep);

    // adapt CSS highlighting to SVG
    [...svg.node().querySelectorAll("text[class^=color-group-]")].forEach( (node) => {
      let style = window.getComputedStyle(node)
      node.style.fill = style.color
      node.style.fontWeight = "bold"
      let backgroundId = "rgb" + style.backgroundColor.replace(/[^\d,]/g,'').replace(/,/g,'-')
      let select = svg.select(`defs filter#${backgroundId}`).node()
      if (select==null) {
        select = svg.select("defs")
                    .append("filter")
                      .attr("id", backgroundId)
                      .attr("x", 0)
                      .attr("y", 0)
                      .attr("width", 1)
                      .attr("height", 1)
        select.append("feFlood")
                .attr("flood-color", style.backgroundColor)
        select.append("feComposite")
                .attr("in", "SourceGraphic")
      }
      node.setAttribute("filter", `url(#${backgroundId})`);
    });
  },
}
</script>
