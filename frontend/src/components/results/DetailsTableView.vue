<template>
  <div id="details-view" v-if="data">
    <table class="table mb-5" :class="isModal ? 'modal-table' : ''">
      <tbody>
        <tr>
          <td v-if="sentences.length > 2" key="annotations"></td>
          <td v-for="(header, index) in filteredColumnHeaders" :key="`tr-header-${index}`">
            <th>{{ header }}</th>
          </td>
        </tr>
        <tr v-for="(token, tIndex) in sentences[1]" :key="`tr-token-${tIndex}`" :class="rowClasses(tIndex)">
          <td
            v-if="sentences.length > 2"
            v-html="annotations(tIndex, sentences)"
            key="annotations"
          ></td>
          <td v-for="(column, cIndex) in filteredColumnHeaders" :key="`td-${tIndex}-${cIndex}`">
            <span v-if="column == 'head'" v-html="headToken(token, tIndex)"> </span>
            <span
              v-else-if="isJson(token[cIndex])"
              :class="objectClasses(token[cIndex])"
            >
              {{ objectColumn(token[cIndex]) }}
              <span class="ufeat-info-button tooltips" data-bs-html="true" :title="tooltipText(token[cIndex])">
                <FontAwesomeIcon :icon="['fas', 'circle-info']" />
              </span>
            </span>
            <span
              v-else
              :class="textClasses(column)"
              v-html="token[cIndex]"
            > </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style>
.modal {
  width: unset !important;
  max-width: calc(100vw - 2em);
  left: 50vw;
  transform: translateX(-50%);
  min-width: 50vw;
}
.modal-content {
  padding-left: 1em;
  padding-right: 1em;
}
.table-box {
  overflow: auto;
}
.modal-table.table {
  width: 100%;
}
.object-column {
  display: block;
  height: 1.5em;
  position: relative;
  white-space: nowrap;
  padding-right: 25px;
}
.object-column button {
  float: right;
  margin-top: -0.25em;
}
.object-column button::before {
  content: "▶";
}
.object-column span.whenFolded {
  display: block;
}
.object-column.unfolded {
  height: unset;
  overflow-y: visible;
}
.object-column.unfolded button::before {
  content: "▼";
}
.object-column.unfolded pre {
  margin-top: 0;
}
.object-column.unfolded .whenFolded {
  display: none;
}
.object-column.unfolded .whenUnfolded {
  display: block;
  white-space: pre;
}
.object-column .ufeat-info-button {
  position: absolute;
  cursor: pointer;
  right: 0px;
  top: 0px;
}
</style>

<script>
import Utils from '@/utils';
import { setTooltips, removeTooltips } from "@/tooltips";

export default {
  name: "ResultsDetailsTableView",
  props: ["data", "sentences", "corpora", "columnHeaders", "isModal"],
  data() {
    return {
      ufeatOrder: [
        'Typo', 'ExtPos', 'NumForm', 'NumType', 'Tense', 'VerbForm', 'Mood', 'Polarity',
        'Definite', 'Foreign', 'Reflex', 'Number', 'Abbr', 'Voice', 'Poss', 'PronType',
        'Case', 'Degree', 'Style', 'Person', 'Gender'
      ],
      filteredColumnHeaders: this.columnHeaders.filter(ch=>ch!="spaceAfter")
    }
  },
  methods: {
    headToken(tokenData, tIndex) {
      let token = ""
      let headIndex = this.columnHeaders.indexOf("head")
      let lemmaIndex = this.columnHeaders.indexOf("lemma")
      let startId = this.sentences[0]
      if (headIndex && lemmaIndex) {
        let tokenId = tokenData[headIndex];
        if (tokenId) {
          token = this.sentences[1][tokenId - startId][lemmaIndex]
          let difference = tokenId - startId - tIndex;
          let arrow = "↓", tag="sub";
          if (difference<0) {
            arrow = "↑";
            tag = "sup";
            difference = Math.abs(difference);
          }
          token += ` <${tag}>${arrow}${difference}</${tag}>`;
        }
      }
      return token;
    },
    calcColumnHeaders() {
      let partitions = this.corpora.corpus.partitions
        ? this.corpora.corpus.partitions.values
        : [];
      let columns = this.corpora.corpus["mapping"]["layer"][this.corpora.corpus["segment"]];
      if (partitions.length) {
        columns = columns["partitions"][partitions[0]];
      }
      return columns["prepared"]["columnHeaders"].filter( (column) => column!="spaceAfter" );
    },
    textClasses(item) {
      let classes = [];
      if (item.indexOf('pos') > -1 || item.indexOf('label') > -1) {
        // classes.push('badge rounded-pill')
        classes.push('badge')
        classes.push('bg-secondary')
      }
      return classes
    },
    rowClasses(tIndex) {
      let classes = [];
      let startId = this.sentences[0];
      let tokenId = startId + tIndex;
      let group = this.data[1].findIndex(v => v instanceof Array ? v.includes(tokenId) : v == tokenId);
      if (group >= 0) classes.push(`tr-color-group-${group}`);
      return classes
    },
    isJson(content) {
      if (content instanceof Object && Object.keys(content).length > 0)
        return true;
      let isJson = false;
      try {
        let json = JSON.parse(content);
        isJson = json instanceof Object && Object.keys(json).length > 0;
      }
      catch {
        return false;
      }
      return isJson;
    },
    objectClasses(content) {
      if (content)
        return ['object-column'];
      else
        return [''];
    },
    objectColumn(content) {
      let retval = "";
      if (content) {
        // ufeats
        const jsonContent = content instanceof Object && Object.keys(content).length ? content : JSON.parse(content);
        let ufeatValues = this.ufeatOrder.filter(key => key in jsonContent).map(key => jsonContent[key]);
        retval = ufeatValues.join(" ");
        // retval = `<button class="btn btn-sm btn-primary" onclick="this.parentNode.classList.toggle('unfolded')"> </button>
        //   <span class='whenFolded'>${Utils.dictToStr(jsonContent)}</span>
        //   <span class='whenUnfolded'>${JSON.stringify(jsonContent,null,2).replace(/\n/g,'<br>')}</span>`;
      }
      return retval
    },
    tooltipText(content) {
      let retval = "";
      if (content) {
        const jsonContent = content instanceof Object && Object.keys(content).length ? content : JSON.parse(content);
        let _tmpUfeats = []
        this.ufeatOrder.forEach(key => {
          if (key in jsonContent) {
            _tmpUfeats.push(`${key}: ${jsonContent[key]}`);
          }
        });
        retval = _tmpUfeats.join("<br>");
      }
      return retval
    },
    annotations(tIndex, sentence) {
      const [offset, _, annotations] = sentence; // eslint-disable-line no-unused-vars
      const tokenIndexOffset = tIndex + offset;
      let ret = [];
      for (let [layer, entities] of Object.entries(annotations)) {
        for (let [entityOffset, entityLength, attributes] of entities) {
          if (tokenIndexOffset < entityOffset || tokenIndexOffset >= (entityOffset+entityLength))
            continue
          ret.push(`${layer}: ${Utils.dictToStr(attributes,{replaceYesNo: true, addTitles: true})}`)
        }
      }
      return ret.join(", ");
    }
  },
  mounted() {
    setTooltips();
  },
  updated() {
    setTooltips();
  },
  beforeUnmount() {
    removeTooltips();
  },
};
</script>
