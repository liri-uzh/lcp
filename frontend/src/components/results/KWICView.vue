<template>
  <div id="kwic-view">
    <PaginationComponent
      v-if="data"
      class="paggination"
      :resultCount="data.length"
      :resultsPerPage="resultsPerPage"
      :currentPage="currentPage"
      @update="updatePage"
      :key="data.length"
      :loading="loading"
    />
    <table class="table" v-if="data">
      <thead>
        <tr>
          <template
            v-for="(group, groupIndex) in groups"
            :key="`thead-${groupIndex}`"
          >
            <th scope="col" :class="`header-${groupIndex == 0 ? 'left' : 'form'}`">
              {{ groupIndex == 0 ? "Left context" : "Context" }}
            </th>
            <th scope="col" class="header-form">Match</th>
          </template>
          <th scope="col">Right context</th>
          <th scope="col">-</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(item, resultIndex) in results"
          :key="resultIndex"
          :data-index="resultIndex"
        >
          <template
            v-for="(group, groupIndex) in groups"
            :key="`tbody-${groupIndex}`"
          >
            <td
              scope="row"
              :class="groupIndex == 0 ? 'left-context' : 'middle-context'"
            >
              <span
                class="token"
                v-for="(token, tokenIndex) in item[groupIndex * 2]"
                :key="`rc-${tokenIndex}`"
                :class="[
                  (columnHeaders && token[columnHeaders.indexOf('spaceAfter')]===0 ? 'nospace' : ''),
                  ...bgCheck(resultIndex, groupIndex, tokenIndex, item, 1)
                ]"
                @mousemove="showPopover(token, resultIndex, $event)"
                @mouseleave="closePopover"
              >
                {{ token[0] }}
              </span>
            </td>
            <td scope="row" class="match-context text-bold">
              <span
                class="token"
                v-for="(token, tokenIndex) in item[groupIndex * 2 + 1]"
                :key="`form-${tokenIndex}`"
                :class="[
                  (columnHeaders && token[columnHeaders.indexOf('spaceAfter')]===0 ? 'nospace' : ''),
                  ...bgCheck(resultIndex, groupIndex, tokenIndex, item, 2)
                ]"
                @mousemove="showPopover(token, resultIndex, $event)"
                @mouseleave="closePopover"
              >
                {{ token[0] }}
              </span>
            </td>
          </template>
          <td scope="row" class="right-context">
            <span
              class="token"
              v-for="(token, tokenIndex) in item[groups.length * 2]"
              :key="`lt-${tokenIndex}`"
              :class="[
                (columnHeaders && token[columnHeaders.indexOf('spaceAfter')]===0 ? 'nospace' : ''),
                bgCheck(resultIndex, groups.length - 1, tokenIndex, item, 3)
              ]"
              @mousemove="showPopover(token, resultIndex, $event)"
              @mouseleave="closePopover"
            >
              {{ token[0] }}
            </span>
          </td>
          <td>
            <button
              type="button"
              class="btn btn-secondary btn-sm"
              data-bs-toggle="modal"
              :data-bs-target="`#detailsModal${randInt}`"
              @click="showModal(resultIndex)"
            >
              Details
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <PaginationComponent
      v-if="data"
      class="paggination"
      :resultCount="data.length"
      :resultsPerPage="resultsPerPage"
      :currentPage="currentPage"
      @update="updatePage"
      :key="data.length"
      :loading="loading"
    />
    <div
      class="popover-liri"
      v-if="currentToken"
      :style="{ top: popoverY + 'px', left: popoverX + 'px' }"
    >
      <table class="table popover-table">
        <thead>
          <tr>
            <th v-for="(item, index) in columnHeaders.filter(ch=>ch!= 'spaceAfter')" :key="`th-${index}`">
              {{ item }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td v-for="(item, index) in columnHeaders.filter(ch=>ch!= 'spaceAfter')" :key="`tr-${index}`">
              <span v-if="item == 'head'" v-html="headToken"> </span>
              <span
                v-else
                :class="
                  item.indexOf('pos') > -1
                    ? 'badge rounded-pill bg-secondary'
                    : ''
                "
                v-html="currentToken[index]"
              ></span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      class="modal fade"
      :id="`detailsModal${randInt}`"
      tabindex="-1"
      aria-labelledby="detailsModalLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog modal-full">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="detailsModalLabel">Details</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body text-start">
            <div class="modal-body-content">
              <ResultsDetailsModalView
                :data="data[modalIndex]"
                :sentences="sentences[data[modalIndex][0]]"
                :corpora="corpora"
                :languages="languages"
                :key="modalIndex"
                v-if="modalVisible"
              />
            </div>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.paggination {
  float: right;
}
.header-form {
  text-align: center;
}
.popover-table th {
  text-transform: uppercase;
  font-size: 10px;
}
.popover-table {
  margin-bottom: 0;
}
.header-left {
  text-align: right;
}
.left-context {
  text-align: right;
  overflow: hidden;
  white-space: nowrap;
  max-width: 0;
  direction: rtl;
  width: 40%;
  text-overflow: ellipsis;
}
.middle-context {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 10vw;
  text-align: center;
}
.left-context:before, .middle-context:before {
    float: right;
    content: attr(data-tail);
}
.right-context {
  white-space: nowrap;
  overflow: hidden;
  white-space: nowrap;
  max-width: 0;
  width: 40%;
  text-overflow: ellipsis;
  text-align: left;
}
.popover-liri {
  position: fixed;
  background: #cfcfcf;
  padding: 2px;
  border: #cbcbcb 1px solid;
  border-radius: 5px;
  z-index: 200;
}
.match-context {
  white-space: nowrap;
  text-align: center;
}
.token {
  padding-left: 2px;
  padding-right: 2px;
  display: inline-block;
  transition: 0.3s all;
  border-radius: 2px;
}
.token:hover {
  background-color: #2a7f62;
  color: #fff;
  cursor: pointer;
}
.token.nospace {
  padding-right: 0px;
  margin-right: -2px; /* compensate for next token's padding-left */
}
.highlight {
  background-color: #1e999967;
}
</style>

<script>
import ResultsDetailsModalView from "@/components/results/DetailsModalView.vue";
import PaginationComponent from "@/components/PaginationComponent.vue";

export default {
  name: "ResultsKWICView",
  emits: ["updatePage"],
  props: [
    "data",
    "sentences",
    "languages",
    "attributes",
    "corpora",
    "resultsPerPage",
    "loading",
  ],
  data() {
    return {
      popoverY: 0,
      popoverX: 0,
      currentToken: null,
      currentResultIndex: null,
      modalVisible: false,
      modalIndex: null,
      currentPage: 1,
      groups: this.data ? this.getGroups(this.data[0], true) : [],
      randInt: Math.floor(Math.random() * 1000)
    };
  },
  components: {
    ResultsDetailsModalView,
    PaginationComponent,
  },
  methods: {
    // getGroups1(data) {
    //   let groups = [];
    //   let tmpGroup = [];
    //   let tokenData = JSON.parse(JSON.stringify(data));
    //   tokenData = tokenData.splice(1, tokenData.length)[0];
    //   tokenData.forEach((tokenId, idx) => {
    //     if (idx > 0 && Math.abs(tokenData[idx] - tokenData[idx - 1]) > 1) {
    //       if (tmpGroup.length > 0) {
    //         groups.push(tmpGroup.sort());
    //       }
    //       tmpGroup = [];
    //     }
    //     tmpGroup.push(tokenId);
    //   });
    //   groups.push(tmpGroup.sort());
    //   return groups;
    // },
    getGroups(data, initial=false) {
      let groups = [];
      if (data) {
        let tokenData = JSON.parse(JSON.stringify(data));
        tokenData = tokenData.splice(1, tokenData.length).sort();
        if (initial === true) {
          tokenData = tokenData[0]
        }
        groups = tokenData.map(tokenOrArrayOfTokens =>
          tokenOrArrayOfTokens instanceof Array
            ? tokenOrArrayOfTokens
            : [tokenOrArrayOfTokens]
        );
      }
      return groups;
    },
    showPopover(token, resultIndex, event) {
      this.popoverY = event.clientY + 10;
      this.popoverX = event.clientX + 10;
      this.currentToken = token;
      this.currentResultIndex =
        resultIndex + (this.currentPage - 1) * this.resultsPerPage;
    },
    closePopover() {
      this.currentToken = null;
      this.currentResultIndex = null;
    },
    showModal(index) {
      this.modalIndex = index + (this.currentPage - 1) * this.resultsPerPage;
      this.modalVisible = true;
    },
    updatePage(currentPage) {
      this.currentPage = currentPage;
      this.$emit("updatePage", this.currentPage);
    },
    bgCheck(resultIndex, groupIndex, tokenIndexInResultset, range, type) {
      let classes = [];
      // if (type) {
      if (this.currentResultIndex == resultIndex && this.currentToken) {
        // Because of pages
        resultIndex =
          resultIndex + (this.currentPage - 1) * this.resultsPerPage;

        let sentenceId = this.data[resultIndex][0];
        let startId = this.sentences[sentenceId][0];
        let currentTokenId = 0;
        let groupStartIndex = 0;

        // Left context of resultset
        if (type == 1) {
          // Beacuse of reverse
          if (range[groupIndex].length >= tokenIndexInResultset) {
            tokenIndexInResultset = range[groupIndex].length - tokenIndexInResultset - 1
          }
          if (groupIndex > 0) {
            groupStartIndex = range[range.length - 1][groupIndex - 1].at(-1) + 1;
          }
        } else if (type == 3) {
          groupStartIndex = range[range.length - 1].at(-1).at(-1) + 1;
        } else if (type == 2) {
          // console.log("RD", groupIndex, range[range.length - 1][groupIndex], range[range.length - 1])
          if (range[range.length - 1][groupIndex]) {
            groupStartIndex = range[range.length - 1][groupIndex][0];
          }
        }

        currentTokenId = groupStartIndex + tokenIndexInResultset;
        classes.push(`TR-${currentTokenId}-L${groupStartIndex}`)

        currentTokenId = startId + groupStartIndex + tokenIndexInResultset;

        let headIndex = this.columnHeaders.indexOf("head");
        let currentTokenHeadId = this.currentToken[headIndex];
        if (currentTokenId == currentTokenHeadId) {
          classes.push("highlight");
        }
      }
      return classes;
    },
    columnEllipses() {
      [...document.querySelectorAll("#kwic-view td.left-context,#kwic-view td.middle-context")].forEach( (cell) => {
        if (cell.scrollWidth > cell.offsetWidth)
          cell.dataset.tail = [...cell.children].at(-1).textContent;
        else
        cell.dataset.tail = "";
      });
    }
  },
  computed: {
    headToken() {
      let token = "-";
      let headIndex = this.columnHeaders.indexOf("head");
      let lemmaIndex = this.columnHeaders.indexOf("lemma");
      if (headIndex) {
        let tokenId = this.currentToken[headIndex];
        if (tokenId) {
          let sentenceId = this.data[this.currentResultIndex][0];
          let startId = this.sentences[sentenceId][0];
          let tokenIndexInList = tokenId - startId;
          token = this.sentences[sentenceId][1][tokenIndexInList][lemmaIndex];
        }
      }
      return token;
    },
    results() {
      let start = this.resultsPerPage * (this.currentPage - 1);
      let end = start + this.resultsPerPage;
      return this.data
        .filter((row, rowIndex) => {
          return rowIndex >= start && rowIndex < end;
        })
        .map((row) => {
          let sentenceId = row[0];
          let startIndex = this.sentences[sentenceId][0];
          let tokens = this.sentences[sentenceId][1];
          let tokenData = this.getGroups([0, ...row[1]]);
          // Handle sequences (arrays of tokens)
          let expandedTokenData = [];
          tokenData.forEach( (tokensArr) => {
            if (tokensArr.every(v=>v instanceof Array)) expandedTokenData.push(...tokensArr);
            else expandedTokenData.push(tokensArr);
          });
          // let range = tokenData.map((tokensArr) =>
          let range = expandedTokenData.map((tokensArr) =>
            tokensArr.map((tokenId) => tokenId - startIndex)
          );

          let retval = [
            // Before first
            tokens.filter((_, index) => index < range[0][0]).reverse(),
            // tokens.filter((_, index) => index < range[0][0])
          ];

          for (let index = 0; index < range.length; index++) {
            retval.push(
              tokens.filter(
                (_, tokenIndex) =>
                  tokenIndex >= range[index][0] &&
                  tokenIndex <= range[index].at(-1)
              )
            );
            // Context between forms
            if (index + 1 < range.length) {
              retval.push(
                tokens.filter(
                  (_, tokenIndex) =>
                    tokenIndex > range[index].at(-1) &&
                    tokenIndex < range[index + 1][0]
                )
              );
            }
          }

          // After last form
          retval.push(tokens.filter((_, index) => index > range.at(-1).at(-1)));
          retval.push(range);
          return retval;
        });
    },
    columnHeaders() {
      const corpus = this.corpora.corpus;
      let partitions = corpus.partitions
        ? corpus.partitions.values
        : [];
      let columns = corpus["mapping"]["layer"][corpus["segment"]];
      if (partitions.length) {
        columns = columns["partitions"][partitions[0]];
      }
      const headers = columns["prepared"]["columnHeaders"];
      // for (let [layer, props] of Object.entries(corpus["layer"])) {
      //   if (layer.toLowerCase() == corpus["segment"].toLowerCase()
      //       || (props["contains"]||"").toLowerCase() != corpus["token"].toLowerCase())
      //     continue;
      //   headers.push(layer);
      // }
      return headers;
    },
  },
  mounted() {
    this.columnEllipses();
  },
  updated() {
    this.columnEllipses();
  }
};
</script>
