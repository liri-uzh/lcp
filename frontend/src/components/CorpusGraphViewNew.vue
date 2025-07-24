<template>
  <div>
    <svg id="corpusDiagram"></svg>
  </div>
</template>

<script>
import * as d3 from 'd3'

const WIDTH = 600, HEIGHT = 500;

export default {
  name: "CorpusGraphView",
  data() {
    const entities = [];
    for (let [layerName, layerProps] of Object.entries(this.corpus.layer)) {
      entities.push({id: layerName, label: layerName});
      const attributes = layerProps.attributes || {};
      console.log("layerName", layerName, "attributes", attributes, "meta?", attributes.meta);
      if ("meta" in attributes && typeof(attributes.meta)=="object" && Object.keys(attributes.meta).length>=1) {
        for (let [metaAttrName, metaAttrProps] of Object.entries(attributes.meta))
          attributes[metaAttrName] = metaAttrProps;
        delete attributes.meta;
      }
      for (let [attName, attProps] of Object.entries(attributes))
        entities.push({id: `${layerName}_${attName}`, parentId: layerName, label: attName, attribute: true, props: attProps});
    }
    const additionalParents = {};
    for (let [layerName, layerProps] of Object.entries(this.corpus.layer)) {
      if (!layerProps.contains) continue;
      const child = entities.find((e)=>e.id == layerProps.contains);
      if (!child) continue;
      if (!child.parentId) {
        child.parentId = layerName;
        continue;
      }
      additionalParents[child] = additionalParents[child] || [];
      additionalParents[child].push(layerName);
    }
    for (let entity of entities)
      entity.parentId = entity.parentId || "_root";
    entities.unshift({id:"_root", label: this.corpus.shortname || this.corpus.meta.shortname});
    entities.forEach((e)=>e.folded = false);
    return {
      entities: entities,
      additionalParents: additionalParents,
      viewBoxOffset: {x: 0, y: 0}
    };
  },
  props: ["corpus"],
  methods: {
    drawTree() {
      const nodeWidth = 200, nodeHeight = 50;
      const horizontalSep = 20, verticalSep = 50;

      const unfoldedentities = this.entities.filter((s)=>!s.folded);

      let hierarchy = d3.stratify()(unfoldedentities);
      const treeLayout = d3.tree()
        /*.size([WIDTH,HEIGHT])*/
        .nodeSize([nodeWidth+horizontalSep,nodeHeight+verticalSep]);
      hierarchy = treeLayout(hierarchy);

      const links = hierarchy.links();
      const nodes = hierarchy.descendants();


      const additionalLinks = Object.entries(this.additionalParents).map(([parentId,childrenIds])=>{
        const parent = nodes.find((n)=>n.id==parentId);
        return childrenIds.map((cid)=>{
          const child = nodes.find((n)=>n.id==cid);
          return Object({source: {x: parent.x, y: parent.y}, target: {x: child.x, y: child.y}});
        });
      }).flat();

      this.skillTree
        .selectAll("line")
        .data([...links, ...additionalLinks])
        .join('line')
        .attr('x1', d => d.source.x + nodeWidth/2)
        .attr('x2', d => d.target.x + nodeWidth/2)
        .attr('y1', d => d.source.y)
        .attr('y2', d => d.target.y)
        .style('stroke', 'black');

      this.skillTree
        .selectAll("rect")
        .data(nodes)
        .join("rect")
        .attr("width", () => nodeWidth)
        .attr("height", () => nodeHeight)
        .attr("x", (d) => d.x)
        .attr("y", (d) => d.y - nodeHeight/2)
        .on("click", (d,node)=>{
          if (!node.parent) return d;
          this.entities.forEach((s)=>s.parentId != node.id || !s.attribute || (s.folded = !s.folded));
          this.drawTree();
        });

      this.skillTree
        .selectAll("text")
        .data(nodes)
        .join("text")
        .attr("x", (d) => d.x)
        .attr("y", (d) => d.y)
        .attr("stroke", "white")
        .text( (d) => d.data.label );

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

  },
  beforeUnmount() {
  }
};
</script>

<style>
#corpusDiagram text {
  pointer-events: none;
}
</style>