<template>
  <svg xmlns="http://www.w3.org/2000/svg" 
       :width="width+'px'"
       :height="height+'px'"
       ref="corpusSVG"
       v-if="bounds.minX">

    <defs>
      <filter x="0" y="0" width="1" height="1" id="solid">
        <feFlood flood-color="white" result="bg" />
        <feMerge>
          <feMergeNode in="bg"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    
    <g v-for="link in links"
          :key="`line-${link.source.index}`"
          class="link">
      <line
          :x1="coord(link.source, 'x')"
          :y1="coord(link.source, 'y')"
          :x2="coord(link.target, 'x')"
          :y2="coord(link.target, 'y')"
          stroke="black" stroke-width="2"/>

      <text
          :x="(coord(link.source, 'x') + coord(link.target, 'x')) / 2"
          :y="(coord(link.source, 'y') + coord(link.target, 'y')) / 2"
          v-html="link.text"
          filter="url(#solid)"
          v-if="link.text" />
    </g>
    
    <g v-for="node in nodes"
            :key="`group-${node.index}`"
            class="node"
            @click="clickOnNode(node)">
      <rect
            :x="getX(coord(node, 'x'))"
            :y="getY(coord(node, 'y'))"
            :width="rectWidth"
            :height="rectHeight"
            :rx="15" :fill="getNodeColor(node)"
            stroke="black" stroke-width="1"/>

      <text
            :x="getX(coord(node, 'x')) + 10"
            :y="getY(coord(node, 'y')) + 30"
            v-html="node.text"/>
    </g>
    
  </svg>
</template>

<script>
import * as d3 from 'd3'

export default {
  name: "CorpusGraphView",
  data() {
    const data = {
      graph: {
        nodes: [{index: 0, x: 50, y: 0, text: "Corpus", fixed: true, depth: 0}],
        links: []
      },
      nodes: [],
      links: [],
      width: 100,
      height: 100,
      rectWidth: 125,
      rectHeight: 50,
      padding: 20,
      colors: ['#2196F3', '#E91E63', '#7E57C2', '#009688', '#00BCD4', '#EF6C00', '#4CAF50', '#FF9800', '#F44336', '#CDDC39', '#9C27B0'],
      simulation: null
    };
    if (this.corpus && this.corpus.layer) {
      const layers = Object.entries(this.corpus.layer);
      const parents = {};
      let i = 0;
      for (let [layerName, layerProperties] of layers) {
        i += 1;
        const node = {index: i, x: 0, y: 0, text: layerName, depth: 1, type: "layer", folded: true};
        layerProperties.diagramNode = node;
        if (layerProperties.contains)
          parents[layerProperties.contains] = layers.find(l=>l[0] == layerProperties.contains);
      }
      for (let [layerName, layerProperties] of layers) {
        const node = layerProperties.diagramNode;
        data.graph.nodes.push(node);
        if (layerProperties.contains) {
          const target = this.corpus.layer[layerProperties.contains].diagramNode;
          data.graph.links.push({source: node.index, target: target.index, text: "in"});
        }
        let parentLayer = parents[layerName];
        while (parentLayer) {
          node.depth += 1;
          parentLayer = parents[parentLayer.name];
        }
        if (node.depth == 1)
          data.graph.links.push({source: data.graph.nodes[0].index, target: node.index});
        let attributes = Object({...(layerProperties.attributes||{})});
        if ("meta" in attributes) {
          delete attributes.meta;
          attributes = Object({...attributes, ...layerProperties.attributes.meta});
        }
        for (let attributeName in attributes) {
          i += 1;
          const attributeNode = {index: i, x: 0, y: 0, text: attributeName, depth: node.depth + 1, type: "attribute"};
          data.graph.nodes.push(attributeNode);
          data.graph.links.push({source: node.index, target: attributeNode.index});
        }
      }
    }
    const depths = {};
    for (let node of data.graph.nodes)
      depths[node.depth] = (depths[node.depth]||0) + 1;
    data.width = (data.rectWidth + 2*data.padding) * Math.max(...Object.values(depths));
    data.height = (data.rectHeight + 2*data.padding) * Object.keys(depths).length;
    return data;
  },
  props: ["corpus"],
  methods: {
    clickOnNode(node) {
      const originalNode = this.graph.nodes.find(n=>n.index == node.originalIndex);
      if (node.type == "layer")
        this.switchFold(originalNode);
      else if (node.type == "seeMore")
        this.unfoldParent(node);
    },
    switchFold(node, {switchTo} = {switchTo: undefined}) {
      node.folded = switchTo === undefined ? node.folded !== true : switchTo;
      this.filterNodesLinks();
    },
    unfoldParent(node){
      const parent = this.graph.nodes.find(n=>n.index == node.parentIndex);
      this.switchFold(parent, {switchTo: false});
    },
    checkContainerHeight() {
      if (this.$refs.corpusSVG) {
        const {width, height} = this.$refs.corpusSVG.parentElement.getBoundingClientRect();
        if (width != this.width || height != this.height) {
          this.width = width;
          this.height = height;
        }
      }
      window.requestAnimationFrame(()=>this.checkContainerHeight());
    },
    getX(x) {
      return Math.min(Math.max(x - this.rectWidth/2, 0), this.width - this.rectWidth);
    },
    getY(y) {
      return Math.min(Math.max(y - this.rectHeight/2, 0), this.height - this.rectHeight);
    },
    parentFolded(node) {
      const parentIds = this.graph.links.filter(l=>l.target == node.index).map(l=>l.source);
      const parents = this.graph.nodes.filter(n=>parentIds.includes(n.index));
      if (parents.every(p=>p.folded))
        return true;
      return false;
      // if (parents.length == 0)
      //   return false;
      // return parents.every(p=>this.parentFolded(p));
    },
    filterNodesLinks() {
      const nodes = [], links = [], indexMapping = {};
      let i = 0; //, nSeeMore = this.graph.nodes.length;
      for (let node of this.graph.nodes) {
        if (node.type == "attribute" && this.parentFolded(node))
          continue;
        indexMapping[node.index] = i;
        nodes.push( Object({...node, index: i, originalIndex: node.index}) ); // copy of object (do not mutate)
        for (let link of this.graph.links) {
          if (link.target != node.index)
            continue;
          links.push(Object({...link})); // copy of object (do not mutate)
        }
        // if (node.folded) {
        //   i += 1;
        //   indexMapping[nSeeMore] = i;
        //   nodes.push({
        //     index: nSeeMore,
        //     x: 0,
        //     y: 0,
        //     text: "... +",
        //     type: "seeMore",
        //     depth: node.depth+1,
        //     parentIndex: node.index
        //   });
        //   links.push({source: node.index, target: nSeeMore});
        //   nSeeMore += 1;
        // }
        i += 1;
      }
      for (let link of links) {
        link.source = indexMapping[link.source];
        link.target = indexMapping[link.target];
      }
      this.nodes = nodes;
      this.links = links;
      this.simulate();
    },
    coord(node, which) {
      const min = (which=="x" ? "minX" : "minY"), max = (which=="x" ? "maxX" : "maxY"), dim = (which=="x" ? "width" : "height");
      return this.padding + (node[which] - this.bounds[min]) * (this[dim] - 2*this.padding) / (this.bounds[max] - this.bounds[min]);
    },
    getNodeColor(node) {
      if (node.index==0)
        return "white";
      if (node.type == "attribute")
        return "lightyellow";
      if (node.type == "seeMore")
        return "lightgray";
      return "lightgreen";
    },
    simulate() {
      this.simulation = d3.forceSimulation(this.nodes, this.rectWidth)
        .force('charge', d3.forceManyBody().strength(() => -50))
        .force('link', d3.forceLink(this.links))
        .force('x', d3.forceX())
        .force('y', d3.forceY().y(function(d) {
          return d.depth * 50;
        }));
    }
  },
  computed: {
    bounds() {
      const b = {
        minX: Math.min(...this.nodes.map(n => n.x)),
        maxX: Math.max(...this.nodes.map(n => n.x)),
        minY: Math.min(...this.nodes.map(n => n.y)),
        maxY: Math.max(...this.nodes.map(n => n.y))
      };
      return b;
    }
  },
  mounted() {
    this.filterNodesLinks();
    this.checkContainerHeight();
  },
  beforeUnmount() {
  }
};
</script>
  
<style>

</style>