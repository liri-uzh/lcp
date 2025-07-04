<template>
  <div ref="mermaidcontainer">
    <SvgPanZoom
      :zoomEnabled="true"
      :controlIconsEnabled="true"
      :fit="false"
      :center="true"
    >
      <vue3-mermaid
        :nodes="graphData"
        type="graph TD"
        :config="mermaidConfig"
        :key="graphIndex"
        @nodeClick="clickOnLayer"
      ></vue3-mermaid>
    </SvgPanZoom>
  </div>
</template>

<script>
import { setTooltips, removeTooltips } from "@/tooltips";
// import svgPanZoom from 'svg-pan-zoom';
import { SvgPanZoom } from "vue-svg-pan-zoom";

// Mermaid does not support arrows pointing to the source node(!)
// This hack finds all the paths associated with an "in" label and reverses their line commands
function reverseIns(graph) {
  let inLabels = [...graph.querySelectorAll("span.edgeLabel")].filter( s=>s.innerText=="in" );
  let inPaths = [];
  inLabels.forEach( label=>{
    let inPathClasses = [...label.classList].map( cls => '.' + (
      cls=="edgeLabel"
        ? "edgePath"
        : cls.replace(/(^L-|')/g,'') // An L- prefix and some single quotes get inserted in labels' classes for some reason
      )
    ).join('');
    let inPath = graph.querySelector( inPathClasses + " path" );
    if (inPath) inPaths.push(inPath);
  });
  inPaths.forEach( path => {
    let dPath = path.getAttribute("d");
    let commands = dPath.split(/(?=[MLC])/).reverse().map( (command,i) => {
      if (i==0) return command.replace(/^L/,"M");
      else if (command.startsWith("C")) {
        let curbs = command.match(/(\d+)(\.\d+)*,(\d+)(\.\d+)*/g);
        return "C" + curbs.reverse().join(","); // this doesn't produce the smoothest curves, but they're still readable
      }
      else
        return command.replace(/^M/,"L");
    }).join('');
    path.setAttribute("d", commands);
  } );
  return true;
}

let unfoldedIndices = [];
class UnfoldAttribute {
  constructor() {
    this.name = "5+ attributes";
    this.type = "categorical";
    this.values = ["Click to unfold"];
  }
}

function computeAttributes(corpus_layer) {
  const corpus_layers_attributes = {};
  for (let index = 0; index < Object.keys(corpus_layer).length; index++){
    let layer_name = Object.keys(corpus_layer)[index];
    let layer_props = corpus_layer[layer_name];
    if (!("attributes" in layer_props))
      continue;
    let corpus_layer_attributes = {};
    for (let [a_name, a_value] of Object.entries(layer_props.attributes)) {
      if (a_name == "meta")
        for (let [sub_a_name, sub_a_value] of Object.entries(a_value)){
          let name = sub_a_name;
          if (name == "end") sub_a_name = "eոd"; // use a lookalike character
          corpus_layer_attributes[sub_a_name] = sub_a_value;
        }
      else
        corpus_layer_attributes[a_name] = a_value;
    };
    // Disable until we find a fix
    // if (!unfoldedIndices.includes(index) && Object.keys(corpus_layer_attributes).length > 4)
    //   corpus_layers_attributes[layer_name] = {'5+attributes': new UnfoldAttribute()};
    // else
      corpus_layers_attributes[layer_name] = corpus_layer_attributes;
  }
  return corpus_layers_attributes;
}

const STYLES = {
  text: "fill:#FBD573,stroke:#333,stroke-width:2px",
  categorical: "fill:#FBD573,stroke:#333,stroke-width:2px",
  dict: "fill:#6BD5F3,stroke:#333,stroke-width:2px",
  jsonb: "fill:#6BD5F3,stroke:#333,stroke-width:2px", // Should become obsolete -- update DB
  number: "fill:#ABF513,stroke:#333,stroke-width:2px",
  labels: "fill:#3BF5B3,stroke:#333,stroke-width:2px",
  ref: "fill:#6264FF,stroke:#333,stroke-width:2px",
  entity: "fill:#F321AA,stroke:#333,stroke-width:2px",
}

const isAnchored = (layer, conf, anchor) => {
  if (conf[layer].anchoring && conf[layer].anchoring[anchor] == true)
    return true;
  if (conf[layer].contains && conf[layer].contains in conf)
    return isAnchored(conf[layer].contains, conf, anchor);
  return false;
}

export default {
  name: "CorpusGraphView",
  data() {
    const corpus_layers_attributes = computeAttributes(this.corpus.layer);
    return {
      graphIndex: 0,
      mermaidConfig: {
        theme: "neutral",
        // themeVariables: {
        //   'primaryColor': '#BB2528',
        //   'primaryTextColor': '#fff',
        //   'primaryBorderColor': '#7C0000',
        //   'lineColor': '#F8B229',
        //   'secondaryColor': '#006100',
        //   'tertiaryColor': '#fff'
        // }
      },
      corpusLayersAttributes: corpus_layers_attributes
    };
  },
  components: {
    SvgPanZoom,
  },
  props: ["corpus"],
  methods: {
    clickOnLayer(nodeId) {
      const layerId = Number(nodeId.replace(/^a-(\d+)-.+$/, "$1"));
      console.log("clicked on", nodeId, layerId);
      if (unfoldedIndices.includes(layerId))
        unfoldedIndices = unfoldedIndices.filter( id => id != layerId );
      else
        unfoldedIndices = [...unfoldedIndices, layerId];
      const cla = computeAttributes(this.corpus.layer);
      this.corpusLayersAttributes = cla;
      setTimeout(()=>this.$emit("graphReady", this.$refs.mermaidcontainer), 1000);
    }
  },
  computed: {
    graphData() {
      let corpus = this.corpus;
      const corpusName = corpus.meta.name.replace(/[}{)(]+/gi, "").replace(/@/gi, "-at-");
      let data = [
        {
          id: "1",
          text: corpusName,
          next: Object.keys(corpus.layer).filter( (layer) => !("partOf" in corpus.layer[layer]) ).map(
            (layer) => `l-${layer.toLowerCase().replace(/@/gi, "_")}`
          ),
          style: "fill:#FFF,stroke:#000,stroke-width:1px",
          edgeType: "round"
        },
      ];
      let globalAttributesDone = {};
      let partOfs = {};
      Object.keys(corpus.layer).forEach((layer, index) => {
        let next = [], link = [];
        if (layer in this.corpusLayersAttributes) {
          let layer_type = corpus.layer[layer].layerType;
          for (let [attribute_name, attribute_props] of Object.entries(this.corpusLayersAttributes[layer])) {
            let attributeId = `a-${index}-${attribute_name.replace("_","").toLowerCase()}`;
            let text = attribute_name.replace(/@/gi, "_");
            // console.log("attribute_name", attribute_name, "layer", layer);
            if (layer_type == "relation" && "name" in attribute_props)
              text = attribute_props.name;
            let attributeData = {
              id: attributeId,
              text: text,
              edgeType: "round",
              style: "fill:#FBD573,stroke:#333,stroke-width:2px",
              editable: attribute_props instanceof UnfoldAttribute
            };

            const tooltipNotes = ["Type: text"];
            if (attribute_props.description)
              tooltipNotes.push("Description: "+attribute_props.description.replace(/[^a-zA-Z0-9\s]+/,""));

            if ("entity" in attribute_props && attribute_props.entity in corpus.layer) {
              attributeData.next = [`l-${attribute_props.entity.toLowerCase().replace(/@/gi, "_")}`];
              attributeData.link = ["-.->|refers to|"];
              attributeData.style = STYLES.entity;
              tooltipNotes[0] = `Type: ${attribute_props.entity}`;
            }
            else if (attribute_props.type=="categorical") {
              let warnings = [];
              let possibleValues = Object.keys(attribute_props);
              if (attribute_props.values instanceof Array && attribute_props.values.length>0) {
                // possibleValues = attribute_props.values.filter(v=>v.match(/^[^'"()<>\u005B\u005D]+$/));
                possibleValues = attribute_props.values.filter(v=>v.match(/^[a-zA-Z0-9\s]+$/));
                if (possibleValues.length != attribute_props.values.length)
                  warnings.push("values with special characters not listed");
              }
              else if (attribute_props.isGlobal && attribute_name in corpus.glob_attr)
                possibleValues = corpus.glob_attr[attribute_name];
              else
                possibleValues = ["List of values missing from specs"];
              let stringPossibleValues = possibleValues.reduce( (stringSoFar,newWord) => (newWord+" "+stringSoFar).length < 200 ? stringSoFar + " " + newWord : stringSoFar , "" );
              if (stringPossibleValues.length < possibleValues.join(" ").length) {
                stringPossibleValues += " ..."
                warnings.push("too many values to display");
              }
              tooltipNotes.push(`Possible values: ${stringPossibleValues}${warnings.length?' /!\\ '+warnings.join(' - ')+' /!\\':''}`);
            }
            if (attribute_props.type && attribute_props.type in STYLES)
              attributeData.style = STYLES[attribute_props.type];
            if (attribute_props.ref) {
              attributeData.style = STYLES.ref;
              tooltipNotes[0] = "Type: global attribute";
              if (!(attribute_props.ref in globalAttributesDone)) {
                attributeData.link = [];
                attributeData.next = [];
                const ga = corpus.globalAttributes[attribute_props.ref];
                for (let [gk,gv] of Object.entries(ga.keys)) {
                  attributeData.link.push("---");
                  attributeData.next.push(`${attributeId}-${gk}`);
                  data.push({
                    id: `${attributeId}-${gk}`,
                    text: `<abbr title='${gv.type}' class='tooltips'>${gk}</abbr>`,
                    edgeType: "round",
                    style: "fill:#FBD573,stroke:#333,stroke-width:2px",
                    editable: false
                  });
                }
                globalAttributesDone[attribute_props.ref] = 1;
              }
            }

            if (attribute_props.type && !(attribute_props.type in {text:1, categorical:1}))
              tooltipNotes[0] = `Type: ${attribute_props.type}`;

            attributeData.text = `<abbr title='${tooltipNotes.join(' -- ')}' class='tooltips'>${attributeData.text}</abbr>`
            data.push(attributeData);
            next.push(attributeId);
            link.push("---")
          };
        }
        // Is this necessary? Meta is an attribute itself
        if ("meta" in corpus.layer[layer]) {
          Object.keys(corpus.layer[layer].meta).forEach((meta) => {
            let metaId = `a-${index}-${meta.toLowerCase()}`;
            data.push({
              id: metaId,
              text: meta.replace(/@/gi, "_"),
              edgeType: "round",
              style: "fill:#FBD573,stroke:#333,stroke-width:2px",
            });
            next.push(metaId);
            link.push("---")
          });
        }
        if ("contains" in corpus.layer[layer]) {
          let containedId = `l-${corpus.layer[layer].contains.toLowerCase().replace(/@/gi, "_")}`;
          next.push(containedId);
          link.push("-- in -->")
          data[0].next = data[0].next.filter( (layerId) => layerId != containedId );
        }
        let layer_title = [];
        const anchorings = [];
        for (let [anchor, init, desc] of [
          ["stream", 'c', "character aligned"],
          ["time", 't', "time aligned"],
          ["location", 'l', "location aligned"]
        ]) {
          if (!isAnchored(layer, corpus.layer, anchor))
            continue;
          anchorings.push(init + ".");
          layer_title.push(desc)
        }
        if (corpus.layer[layer].description)
          layer_title.push(corpus.layer[layer].description.replace(/[^a-zA-Z0-9\s]+/g, ""));
        let layer_text = layer.replace(/@/gi, "_") + " " + anchorings.join('');
        if (layer_title.length)
          layer_text = `<abbr title='${layer_title.join(' - ')}' class='tooltips'>${layer_text}</abbr>`;
        let layerData = {
          id: `l-${layer.toLowerCase().replace(/@/gi, "_")}`,
          text: layer_text,
          next: next,
          link: link
        };
        if ("partOf" in corpus.layer[layer]) {
          let parentLayerId = `l-${corpus.layer[layer].partOf.toLowerCase().replace(/@/gi,"")}`;
          partOfs[parentLayerId] = [...(partOfs[parentLayerId]||[]), layerData];
        }
        data.push(layerData);
      });
      // Handle the partOfs after adding their parents to the structure
      for (let parentLayerId in partOfs) {
        let parentLayer = data.find( (layer) => layer.id==parentLayerId );
        if (parentLayer===undefined) continue;
        // Remove the attributes from the parent: they will be inherited by the children
        // let parentAttributes = [];
        // parentLayer.next = parentLayer.next.filter( (layerId) =>
        //   !String.prototype.startsWith.call(layerId,'a-') || (parentAttributes.push(layerId) && false)
        // );
        for (let childLayerData of partOfs[parentLayerId]) {
          // Inherit the attributes
          // childLayerData.next.push(...parentAttributes);
          // childLayerData.link.push(...parentAttributes.map( (_) => `-->|via ${parentLayer.text}|` ))
          // Add and flag the layer as "part of" the parent
          parentLayer.next.push(childLayerData);
          parentLayer.link.push("---|part of|");
        }
      }
      // console.log("data", data);
      return data;
    },
  },
  mounted() {
    // Dirty fix -- ask Igor why a fix is needed in the first place
    let updateGraphUntilSuccessful = ()=> {
      if (this.$refs.mermaidcontainer==null) return;
      if (this.$refs.mermaidcontainer.querySelector("text.error-text")===null) {
        reverseIns(this.$refs.mermaidcontainer); // reverse the direction of the arrows of the 'in' relations
        setTooltips(this.$refs.mermaidcontainer);
        this.$emit("graphReady", this.$refs.mermaidcontainer);
        return;
      }
      this.graphIndex += 1;
      window.requestAnimationFrame(updateGraphUntilSuccessful);
    }
    updateGraphUntilSuccessful();
  },
  beforeUnmount() {
    // this.removeTooltips();
    removeTooltips();
  }
};
</script>

<style>
.mermaid .tooltips {
  border-bottom: dotted 1px black;
  cursor: help;
}
</style>
