<template>
  <div :style="`width: ${width}px; height: ${height}px; overflow: hidden;`">
    <svg id="corpusDiagram"></svg>
    <div id="zoomControls">
      <div id="zoomPlus" @click="zoom = Math.min(2.0, zoom - 0.1)">+</div>
      <div id="zoomReset" @click="placeInit()">reset</div>
      <div id="zoomMinus" @click="zoom = Math.max(0.2, zoom + 0.1)">-</div>
    </div>
  </div>
</template>

<script>
import * as d3 from 'd3'
import Utils from '@/utils.js'
import { setTooltips, removeTooltips } from "@/tooltips";

const NATTR_FOLD = 4;
const WIDTH = 650, HEIGHT = 500;

function attrColor(props) {
  if (props.ref)
    return "#6264FF";
  if ("entity" in props)
    return "#1BE5C3";
  if (props.type in {number: 1, integer: 1})
    return "#ABF513";
  if (["dict", "jsonb"].includes(props.type))
    return "#6BD5F3";
  if (props.type in {labels:1, array: 1})
    return "#3BF5B3";
  if (props.type == "image")
    return "#F3906F";
  if (props.type == "_unfolder")
    return "#CCC"
  return "#FBD573"
}
function displayTextWidth(text) {
  const canvas = displayTextWidth.canvas || (displayTextWidth.canvas = document.createElement("canvas"));
  let context = canvas.getContext("2d");
  context.font = "16px / 24px trebuchet ms, verdana, arial, sans-serif";
  let metrics = context.measureText(text);
  return 6 + metrics.width;
}
function forceXCollision(nodes, getWidth) {
  let nodesRef = nodes;
  function force() {
    for (let i = 0; i < nodesRef.length; i++) {
      const d1 = nodesRef[i];
      for (let j = i + 1; j < nodesRef.length; j++) {
        const d2 = nodesRef[j];
        if (d1.y != d2.y) continue;
        const width1 = getWidth(d1);
        const width2 = getWidth(d2);
        const startOverlap = Math.max(d1.x,d2.x);
        const endOverlap = Math.min(d1.x + width1, d2.x + width2);
        if (startOverlap > endOverlap) continue;
        const resolveX = 30 + (endOverlap-startOverlap) * 0.5;
        d1.x -= resolveX;
        d2.x += resolveX;
      }
    }
  }
  force.initialize = function(_) {
    nodesRef = _;
  };
  return force;
}

export default {
  name: "CorpusGraphView",
  data() {
    const layers = this.corpus.layer;
    Object.entries(layers).forEach(([layerName,layerProps])=>{
      if (layerProps.contains && typeof(layerProps.contains)=="string")
        // typeof(layerProps.contains) == 'string' ? layerProps.contains = [layerProps.contains] : layerProps.contains.push
        layerProps.contains = [layerProps.contains];
      if (!layerProps.partOf) return;
      if (!layers[layerProps.partOf].contains)
        layers[layerProps.partOf].contains = [];
      if (typeof(layers[layerProps.partOf].contains) == "string")
        layers[layerProps.partOf].contains = [layers[layerProps.partOf].contains];
      layers[layerProps.partOf].contains.push(layerName);
    });
    const globalAttributesDones = {};
    const additionalParents = {};
    const entities = [];
    for (let [layerName, layerProps] of Object.entries(layers)) {
      const attributes = layerProps.attributes || {};
      if ("meta" in attributes && typeof(attributes.meta)=="object" && Object.keys(attributes.meta).length>=1) {
        for (let [metaAttrName, metaAttrProps] of Object.entries(attributes.meta))
          attributes[metaAttrName] = metaAttrProps;
        delete attributes.meta;
      }
      const nAttrs = Object.keys(attributes).length;
      const folded = nAttrs > NATTR_FOLD;
      for (let [attName, attProps] of Object.entries(attributes)) {
        const attId = `${layerName}_${attName}`;
        if ("entity" in attProps && "name" in attProps) {
          attName = attProps.name;
          additionalParents[attId] = [attProps.entity];
        }
        entities.push({
          id: attId,
          parentId: layerName,
          label: attName,
          attribute: true,
          props: attProps,
          width: displayTextWidth(attName),
          folded: folded
        });
        let subAttributes = null;
        if (attProps.ref && attProps.ref in this.corpus.globalAttributes && !(attProps.ref in globalAttributesDones)) {
          globalAttributesDones[attProps.ref] = true;
          subAttributes = Object.entries(this.corpus.globalAttributes[attProps.ref].keys || {});
        }
        else if (attProps.type == "dict")
          subAttributes = Object.entries(attProps.keys || {});
        if (subAttributes === null)
          continue;
        if (subAttributes.length == 0) {
          entities.at(-1).note = "Sub-attributes missing from config";
          continue;
        }
        entities.at(-1).nAttrs = subAttributes.length;
        const subFolded = subAttributes.length > NATTR_FOLD;
        for (let [subAttName, subAttProps] of subAttributes)
          entities.push({
            id: `${layerName}_${attName}_${subAttName}`,
            parentId: `${layerName}_${attName}`,
            label: subAttName,
            attribute: true,
            props: subAttProps,
            width: displayTextWidth(subAttName),
            folded: subFolded
          });
        entities.push({
          id: `${layerName}_${attName}__unfolder`,
          parentId: `${layerName}_${attName}`,
          label: `show ${subAttributes.length}`,
          attribute: true,
          props: {type: "_unfolder", description: `Click to view all ${subAttributes.length} sub-attributes`},
          width: displayTextWidth(`show ${subAttributes.length}`),
          folded: !subFolded
        });
      }
      entities.push({
        id: `${layerName}__unfolder`,
        parentId: layerName,
        label: `show ${nAttrs}`,
        attribute: true,
        props: {type: "_unfolder", description: `Click to view all ${nAttrs} attributes`},
        width: displayTextWidth(`show ${nAttrs}`),
        folded: !folded
      });
      const layerEntity = {
        id: layerName,
        label: layerName,
        width: displayTextWidth(layerName),
        nAttrs: nAttrs,
        anchors: ["stream","time","location"].filter(a=>Utils.isAnchored(layerName,this.corpus.layer,a))
      };
      entities.push(layerEntity);
    }
    for (let [layerName, layerProps] of Object.entries(this.corpus.layer)) {
      if (!layerProps.contains) continue;
      const children = entities.filter((e)=>layerProps.contains.includes(e.id));
      if (children.length==0) continue;
      children.forEach(child=>{
        if (!child.parentId) {
          child.parentId = layerName;
          return;
        }
        additionalParents[child.id] = additionalParents[child.id] || [];
        additionalParents[child.id].push(layerName);
      })
    }
    for (let entity of entities)
      entity.parentId = entity.parentId || "_root";
    const rootLabel = this.corpus.shortname || this.corpus.meta.shortname;
    entities.unshift({id:"_root", label: rootLabel, width: displayTextWidth(rootLabel)});
    entities.forEach((e)=>e.folded = e.folded || false);
    return {
      entities: entities,
      additionalParents: additionalParents,
      viewBoxOffset: {x: 0, y: 0},
      zoom: 1,
      width: WIDTH,
      height: HEIGHT
    };
  },
  props: ["corpus"],
  methods: {
    placeInit() {
      const svgInDOM = document.querySelector("#corpusDiagram");
      this.viewBoxOffset = {x: -1 * Math.round(WIDTH/2), y: 0};
      svgInDOM.setAttribute("viewBox", `${this.viewBoxOffset.x} ${this.viewBoxOffset.y} ${WIDTH} ${HEIGHT}`);
    },
    title(node) {
      const props = node.data.props;
      let title = (props||node.data).description || node.data.label;
      if (props && props.type && props.type != "_unfolder")
        title += ` [${node.data.props.type}]`;
      if (node.data.anchors && node.data.anchors.length > 0)
        title += "; " +
                (node.data.anchors||[]).map(a=>Object({stream:"character-",time:"time-",location:"location-"})[a]).join(" and ") +
                "aligned";
      if (props && props.values instanceof Array)
        title += "; Possible values: " + node.data.props.values.join(" ");
      if ("entity" in (props||{}))
        title += `; points to ${props.entity}`
      return title;
    },
    drawTree() {
      const nodeWidth = 50, nodeHeight = 50;
      const horizontalSep = 20, verticalSep = 50;

      const unfoldedentities = this.entities.filter((s)=>!s.folded && (!s.parentId || !this.entities.find(e=>e.id == s.parentId).folded));

      let hierarchy = d3.stratify()(unfoldedentities);
      const treeLayout = d3.tree()
        // .size([WIDTH,HEIGHT])
        .nodeSize([nodeWidth+horizontalSep,nodeHeight+verticalSep]);
      hierarchy = treeLayout(hierarchy);

      const links = hierarchy.links();
      const nodes = hierarchy.descendants();

      const additionalLinks = Object.entries(this.additionalParents).map(([parentId,childrenIds])=>{
        const parentNode = nodes.find((n)=>n.id==parentId);
        if (!parentNode) return null;
        return childrenIds.map((cid)=>{
          const child = nodes.find((n)=>n.id==cid);
          const [childWidth, parentWidth] = [child,parentNode].map(n=>displayTextWidth(n.label));
          return Object({
            source: {
              data: {width: childWidth},
              id: child.id,
              x: child.x,
              y: child.y
            },
            target: {
              data: {width: parentWidth},
              id: parentNode.id,
              x: parentNode.x,
              y: parentNode.y
            }
          });
        });
      }).flat().filter(x=>x != null);

      this.corpusTree.selectAll("*").remove();

      const svgLines = this.corpusTree
        .selectAll("line")
        .data([...links, ...additionalLinks])
        .join('line')
        .style('stroke', (d) => d.target.data.attribute ? 'brown' : 'darkgrey');

      const svgBoxes = this.corpusTree.selectAll("g")
        .data(nodes)
        .enter()
        .append("g");

      const svgRects = svgBoxes
        .append("rect")
        .attr("width", (d) => d.data.width)
        .attr("height", () => nodeHeight)
        .attr("rx", (d) => d.data.attribute ? 5 : 0 )
        .attr("ry", (d) => d.data.attribute ? 5 : 0 )
        .attr("style",
          (d) => Object.entries({
            fill: d.data.attribute ? attrColor(d.data.props) : "#EEE",
            stroke: d.data.attribute ? "#333" : "#999",
            "stroke-width": d.data.attribute ? "2px" : "1px"
          }).map(([p,v])=>`${p}:${v};`).join(' ')
        )
        .attr("class", "tooltips")
        .attr("title", (d) => this.title(d) )
        .on("pointerdown", (e,node)=>{
          if (!node.parent) return e;
          let id = node.id;
          if (node.data.attribute && node.data.props.type == "_unfolder")
            id = node.data.parentId;
          const entity = this.entities.find(e=>e.id == id);
          if (!entity) return;
          if (!entity.nAttrs || entity.nAttrs == 1) return;
          this.entities.forEach(e=>e.parentId != id || !e.attribute || (e.folded = !e.folded));
          this.drawTree();
          setTooltips();
        });

      const svgAnchors = svgBoxes
        .append("text")
        .attr("font-size", "smaller")
        .text( (d) => (d.data.anchors||[]).map(a=>Object({stream:"c",time:"t",location:"l"})[a]).join(".") )
        .attr("text-anchor", "end");

      const svgTexts = svgBoxes
        .append("text")
        .attr("fill", "black")
        .attr("dominant-baseline", "middle")
        .attr("text-anchor", "middle")
        .text( (d) => d.data.label );

      const simulation = d3.forceSimulation(nodes)
        .force("collision", forceXCollision(nodes, d=>d.data.width));

      simulation.alpha(1).restart();
      for (let i = 0; i < 100; i++)
        simulation.tick();
      simulation.stop();

      svgRects
        .attr("x", d => d.x )
        .attr("y", d => d.y );
      svgAnchors
        .attr("x", d => d.x + d.data.width - 2 )
        .attr("y", d => d.y + 10);
      svgTexts
        .attr("x", d => d.x + d.data.width/2 )
        .attr("y", d => d.y + nodeHeight/2 );
      svgLines
        .attr("x1", d => d.source.x + d.source.data.width/2 )
        .attr("x2", d => d.target.x + d.target.data.width/2 )
        .attr("y1", d => d.source.y + nodeHeight/2 )
        .attr("y2", d => d.target.y + nodeHeight/2 );
    },
    onPointerDown: function (event) {
      this.isClicked = true;
      const x = event.pageX;
      const y = event.pageY;
      this.viewBoxPointer = {
        x: x + this.viewBoxOffset.x,
        y: y + this.viewBoxOffset.y,
      };
    },
    onPointerUp: function () {
      this.isClicked = false;
    },
    onPointerMove: function (event) {
      if (this.isClicked) {
          const x = this.viewBoxPointer.x - event.pageX;
          const y = this.viewBoxPointer.y - event.pageY;
          this.viewBoxOffset = {x: x, y: y};
          const [w, h] = (this.svg.attr("viewBox") || `_ _ ${WIDTH} ${HEIGHT}`)
            .split(" ").map(x=>parseInt(x)).slice(2,4);
          this.svg.attr("viewBox", `${x} ${y} ${w} ${h}`);
      }
    },
  },
  computed: {
  },
  watch: {
    zoom: {
      handler() {
        const svgInDOM = document.querySelector("svg#corpusDiagram");
        const [x,y] = svgInDOM.getAttribute("viewBox").split(" ").map(x=>parseInt(x)).slice(0,2);
        svgInDOM.setAttribute(
          "viewBox",
          [x, y, Math.round(WIDTH * this.zoom), Math.round(HEIGHT * this.zoom)].join(" ")
        );
      }
    }
  },
  mounted() {
    this.placeInit();
    this.svg = d3
      .select("svg#corpusDiagram")
      .attr("width", WIDTH)
      .attr("height", HEIGHT)
      .attr("cursor", "grab")
      .attr("position", "relative");
    this.corpusTree = this.svg.append("g");
    this.drawTree();

    this.svg.on("pointerdown", this.onPointerDown);
    this.svg.on("pointerup", this.onPointerUp);
    this.svg.on("pointerleave", this.onPointerUp);
    this.svg.on("pointermove", this.onPointerMove);

    const svgInDOM = document.querySelector("svg#corpusDiagram");
    svgInDOM.parentElement.addEventListener("wheel", (e)=>{
      e.preventDefault();
      e.stopPropagation();
      this.zoom = Math.max(0.2, Math.min(2.0, this.zoom + e.deltaY/250));
    });
    setTooltips();
  },
  updated() {
    setTooltips();
  },
  beforeUnmount() {
    removeTooltips();
  }
};
</script>

<style>
#corpusDiagram text {
  font-family: trebuchet ms, verdana, arial, sans-serif;
  pointer-events: none;
  user-select: none;
}
#zoomControls {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: absolute;
  width: 100px;
  height: 100px;
  right: 1em;
  bottom: 1em;
}
#zoomControls div {
  text-align: center;
  font-size: 1.5em;
  line-height: 1em;
  height: 1em;
  width: 1em;
  font-variant: small-caps;
  font-weight: bold;
  color: white;
  background-color: gray;
  border-radius: 0.1em;
  margin: 0.15em 0em;
}
#zoomControls div:hover {
  cursor: pointer;
  background-color: lightgray;
  color: black;
}
#zoomControls #zoomReset {
  width: unset;
  font-size: 1.25em;
  padding: 0em 0.2em;
}
</style>
