<template>
  <div :style="`width: ${this.width}px; height: ${this.height}px; overflow: hidden;`">
    <svg id="corpusDiagram"></svg>
  </div>
</template>

<script>
import * as d3 from 'd3'

const WIDTH = 650, HEIGHT = 500;

function attrColor(props) {
  if (props.ref)
    return "#6264FF";
  if (props.type == "number")
    return "#ABF513";
  if (["dict", "jsonb"].includes(props.type))
    return "#6BD5F3";
  if (props.type == "labels")
    return "#3BF5B3";
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
        layerProps.contains = [layerProps.contains];
      if (!layerProps.partOf) return;
      if (!layers[layerProps.partOf].contains)
        layers[layerProps.partOf].contains = [];
      if (typeof(layers[layerProps.partOf].contains) == "string")
        layers[layerProps.partOf].contains = [layers[layerProps.partOf].contains];
      layers[layerProps.partOf].contains.push(layerName);
    });
    const entities = [];
    for (let [layerName, layerProps] of Object.entries(layers)) {
      const layerEntity = {id: layerName, label: layerName, width: displayTextWidth(layerName), anchors: []};
      const attributes = layerProps.attributes || {};
      if ("meta" in attributes && typeof(attributes.meta)=="object" && Object.keys(attributes.meta).length>=1) {
        for (let [metaAttrName, metaAttrProps] of Object.entries(attributes.meta))
          attributes[metaAttrName] = metaAttrProps;
        delete attributes.meta;
      }
      let folded = Object.keys(attributes).length > 4;
      for (let [attName, attProps] of Object.entries(attributes))
        entities.push({
          id: `${layerName}_${attName}`,
          parentId: layerName,
          label: attName,
          attribute: true,
          props: attProps,
          width: displayTextWidth(attName),
          folded: folded
        });
      if (folded)
        entities.push({
          id: `${layerName}__unfolder`,
          parentId: layerName,
          label: "...4+",
          attribute: true,
          props: {type: "_unfolder"},
          width: displayTextWidth("...4+"),
          folded: false
        })
      entities.push(layerEntity);
    }
    const additionalParents = {};
    for (let [layerName, layerProps] of Object.entries(this.corpus.layer)) {
      if (!layerProps.contains) continue;
      const children = entities.filter((e)=>layerProps.contains.includes(e.id));
      if (children.length==0) continue;
      children.forEach(child=>{
        if (!child.parentId) {
          child.parentId = layerName;
          return;
        }
        additionalParents[child] = additionalParents[child] || [];
        additionalParents[child].push(layerName);
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
    drawTree() {
      const nodeWidth = 50, nodeHeight = 50;
      const horizontalSep = 20, verticalSep = 50;

      const unfoldedentities = this.entities.filter((s)=>!s.folded);

      let hierarchy = d3.stratify()(unfoldedentities);
      const treeLayout = d3.tree()
        // .size([WIDTH,HEIGHT])
        .nodeSize([nodeWidth+horizontalSep,nodeHeight+verticalSep]);
      hierarchy = treeLayout(hierarchy);

      const links = hierarchy.links();
      const nodes = hierarchy.descendants();

      const additionalLinks = Object.entries(this.additionalParents).map(([parentId,childrenIds])=>{
        const parent = nodes.find((n)=>n.id==parentId);
        if (!parent) return null;
        return childrenIds.map((cid)=>{
          const child = nodes.find((n)=>n.id==cid);
          return Object({source: {x: parent.x, y: parent.y}, target: {x: child.x, y: child.y}});
        });
      }).flat().filter(x=>x != null);

      this.skillTree.selectAll("*").remove();

      const svgLines = this.skillTree
        .selectAll("line")
        .data([...links, ...additionalLinks])
        .join('line')
        .style('stroke', 'black');

      const svgRects = this.skillTree
        .selectAll("rect")
        .data(nodes)
        .join("rect")
        .attr("width", (d) => d.data.width)
        .attr("height", () => nodeHeight)
        .attr("rx", (d) => d.data.attribute ? 5 : 0 )
        .attr("ry", (d) => d.data.attribute ? 5 : 0 )
        .attr("style", (d) => Object.entries({
          fill: d.data.attribute ? attrColor(d.data.props) : "#EEE",
          stroke: d.data.attribute ? "#333" : "#999",
          "stroke-width": d.data.attribute ? "2px" : "1px"
        }).map(([p,v])=>`${p}:${v};`).join(' '))
        .on("click", (e,node)=>{
          if (!node.parent) return e;
          let id = node.id;
          if (node.data.attribute && node.data.props.type == "_unfolder")
            id = node.data.parentId;
          this.entities.forEach((s)=>s.parentId != id || !s.attribute || (s.folded = !s.folded));
          this.drawTree();
        });

      const svgTexts = this.skillTree
        .selectAll("text")
        .data(nodes)
        .join("text")
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
          this.svg.attr("viewBox", `${x} ${y} ${WIDTH} ${HEIGHT}`);
      }
    },
  },
  computed: {
  },
  mounted() {
    this.svg = d3
      .select("svg#corpusDiagram")
      .attr("width", WIDTH)
      .attr("height", HEIGHT)
      .attr("cursor", "grab")
      .attr("position", "relative");
    this.skillTree = this.svg.append("g");
    this.drawTree();

    this.svg.on("pointerdown", this.onPointerDown);
    this.svg.on("pointerup", this.onPointerUp);
    this.svg.on("pointerleave", this.onPointerUp);
    this.svg.on("pointermove", this.onPointerMove);

    document.querySelector("svg#corpusDiagram").parentElement.addEventListener("wheel", (e)=>{
      this.zoom = Math.max(0.2, Math.min(4.0, this.zoom + e.deltaY/250));
      document.querySelector("svg#corpusDiagram > g").style.zoom = this.zoom;
    });
  },
  beforeUnmount() {
  }
};
</script>

<style>
#corpusDiagram text {
  font-family: trebuchet ms, verdana, arial, sans-serif;
  pointer-events: none;
  user-select: none;
}
</style>