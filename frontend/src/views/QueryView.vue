<template>
  <div class="query">
    <div class="container mt-4">
      <div class="row">
        <div class="col">
          <Title :title="'Query'" />
        </div>
      </div>
      <div class="row">
        <div class="col-4">
          <div class="mb-3 mt-3">
            <label class="form-label">Corpora</label>
            <div
              v-if="selectedCorpora && selectedCorpora.corpus"
              class="details-button icon-3 tooltips"
              @click.stop="switchGraph()"
              title="Show/hide corpus structure"
              :style="{
                position: 'absolute',
                lineHeight: '40px',
                transform: 'translate(calc(-100% - 0.5em))',
              }"
            >
              <FontAwesomeIcon :icon="['fas', 'circle-info']" />
            </div>
            <multiselect
              v-model="selectedCorpora"
              :options="corporaOptions"
              :multiple="false"
              label="name"
              track-by="value"
            ></multiselect>
          </div>
          <div class="mb-3"
            v-if="selectedCorpora && availableLanguages.length > 1"
          >
            <label class="form-label">Languages</label>
            <multiselect
              v-model="selectedLanguages"
              :options="availableLanguages"
              :multiple="true"
            ></multiselect>
          </div>
          <!-- <div class="mb-3">
            <label class="form-label">Room</label>
            <input
              type="text"
              class="form-control"
              disabled
            />
          </div> -->
          <!-- <div class="mb-3">
            <label class="form-label"
              >Query name</label
            >
            <input type="text" class="form-control" v-model="queryName" />
          </div> -->
          <!-- <div class="mb-3">
            <label class="form-label">User</label>
            <input
              type="text"
              class="form-control"
              v-model="userId"
              disabled
            />
          </div> -->
          <!-- <div class="row">
            <div class="col-3">
              <div class="mb-3">
                <label class="form-label">Res. per page</label>
                <input
                  type="number"
                  class="form-control"
                  disabled
                  v-model="resultsPerPage"
                />
              </div>
            </div>
            <div class="col-3">
              <div class="mb-3">
                <label class="form-label">No. of results</label>
                <input
                  type="number"
                  class="form-control"
                  disabled
                  v-model="nResults"
                />
              </div>
            </div>
            <div class="col-6">
              <div class="mb-3">
                <label class="form-label">Languages</label>
                <multiselect
                  v-model="languages"
                  :options="availableLanguages"
                  :multiple="true"
                ></multiselect>
              </div>
            </div>
          </div> -->
          <div class="mb-3">
            <button
              type="button"
              @click="submit"
              class="btn btn-primary me-1 mb-1"
              :disabled="isSubmitDisabled()"
            >
              <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
              {{ loading == "resubmit" ? 'Resubmit' : 'Submit' }}
            </button>

            <button
              type="button"
              v-if="queryStatus in {'satisfied':1,'finished':1} && !loading"
              class="btn btn-primary me-1 mb-1"
              data-bs-toggle="modal"
              data-bs-target="#exportModal"
            >
              <FontAwesomeIcon :icon="['fas', 'file-export']" />
              Export
            </button>

            <button
              type="button"
              v-if="queryStatus == 'satisfied' && !loading"
              @click="submitFullSearch"
              class="btn btn-primary me-1 mb-1"
            >
              <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
              Search whole corpus
            </button>
            <button
              v-else-if="loading"
              type="button"
              @click="stop"
              :disabled="loading == false"
              class="btn btn-primary me-1 mb-1"
            >
              <FontAwesomeIcon :icon="['fas', 'xmark']" />
              Stop
            </button>
            <!-- <button
              type="button"
              @click="resume"
              class="btn btn-primary"
              :disabled="selectedCorpora.length == 0"
            >
              Resume
            </button>
            <button
              type="button"
              @click="stop"
              :disabled="loading == false"
              class="btn btn-primary"
            >
              Stop
            </button>
            <button
              type="button"
              class="btn btn-primary"
              data-bs-toggle="modal"
              data-bs-target="#saveQueryModal"
            >
              Save query
            </button>
            <button type="button" @click="fetch" class="btn btn-primary">
              Fetch
            </button> -->
            <!-- <button type="button" @click="validate" :disabled="!query.trim()" class="btn btn-primary">Validate</button> -->
          </div>
          <div class="lds-ripple" v-if="loading">
            <div></div>
            <div></div>
          </div>
          <div class="corpus-graph" v-if="corpusGraph">
            <FontAwesomeIcon
              :icon="['fas', 'expand']"
              @click="openGraphInModal"
              data-bs-toggle="modal"
              data-bs-target="#corpusDetailsModal"
            />
            <CorpusGraphView :corpus="corpusGraph" @graphReady="resizeGraph" />
          </div>
        </div>
        <div class="col-8">
          <div class="form-floating mb-3">
            <nav>
              <div class="nav nav-tabs" id="nav-tab" role="tablist">
                <button
                  class="nav-link active"
                  id="nav-dqd-tab"
                  data-bs-toggle="tab"
                  data-bs-target="#nav-dqd"
                  type="button"
                  role="tab"
                  aria-controls="nav-dqd"
                  aria-selected="true"
                  @click="currentTab = 'dqd'"
                >
                  DQD
                </button>
                <button
                  class="nav-link"
                  id="nav-json-tab"
                  data-bs-toggle="tab"
                  data-bs-target="#nav-json"
                  type="button"
                  role="tab"
                  aria-controls="nav-json"
                  aria-selected="false"
                  @click="currentTab = 'json'"
                >
                  JSON
                </button>
                <button
                  v-if="sqlQuery"
                  class="nav-link"
                  id="nav-sql-tab"
                  data-bs-toggle="tab"
                  data-bs-target="#nav-sql"
                  type="button"
                  role="tab"
                  aria-controls="nav-sql"
                  aria-selected="false"
                  @click="currentTab = 'sql'"
                >
                  SQL
                </button>
              </div>
            </nav>
            <div class="tab-content" id="nav-tabContent">
              <div
                class="tab-pane fade show active pt-3"
                id="nav-dqd"
                role="tabpanel"
                aria-labelledby="nav-results-tab"
              >
                <EditorView
                  :query="queryDQD"
                  :defaultQuery="defaultQueryDQD"
                  :corpora="selectedCorpora"
                  :invalidError="
                    isQueryValidData && isQueryValidData.valid != true
                      ? isQueryValidData.error
                      : null
                  "
                  :errorList="isQueryValidData && isQueryValidData.valid != true
                      ? isQueryValidData.errorList
                      : null
                  "
                  @submit="submit"
                  @update="updateQueryDQD"
                />
                <p
                  class="error-text text-danger mt-3"
                  v-if="
                    isQueryValidData && isQueryValidData.valid != true && debug
                  "
                >
                  {{ isQueryValidData.error }}
                </p>
              </div>
              <div
                class="tab-pane fade pt-3"
                id="nav-json"
                role="tabpanel"
                aria-labelledby="nav-json-tab"
              >
                <textarea
                  class="form-control query-field"
                  placeholder="Query (e.g. test.*)"
                  :class="
                    isQueryValidData == null || isQueryValidData.valid == true
                      ? 'ok'
                      : 'error'
                  "
                  v-model="query"
                ></textarea>
                <!-- <label for="floatingTextarea">Query</label> -->
                <p
                  class="error-text text-danger"
                  v-if="isQueryValidData && isQueryValidData.valid != true"
                >
                  {{ isQueryValidData.error }}
                </p>
              </div>
              <div
                v-if="sqlQuery"
                class="tab-pane fade pt-3"
                id="nav-sql"
                role="tabpanel"
                aria-labelledby="nav-sql-tab"
              >
                <textarea
                  class="form-control query-field"
                  v-model="sqlQuery"
                ></textarea>
              </div>
            </div>
          </div>
        </div>
        <!-- <div class="col-12">
          <button type="button" @click="submit" class="btn btn-primary" :disabled="selectedCorpora.length == 0">
            Submit
          </button>
          <button type="button" @click="resume" class="btn btn-primary" :disabled="selectedCorpora.length == 0">
            Resume
          </button>
          <button type="button" @click="stop" class="btn btn-primary">
            Stop
          </button>
          <button type="button" @click="save" :disabled="!queryName" class="btn btn-primary">Save</button>
          <button type="button" @click="fetch" class="btn btn-primary">Fetch</button>
          <button type="button" @click="validate" :disabled="!query.trim()" class="btn btn-primary">Validate</button>

        </div> -->
        <div class="col">
          <hr class="mt-5 mb-5" />
          <span>
            <h6 class="mb-3">Query result</h6>
            <div class="progress mb-2">
              <div
                class="progress-bar"
                :class="
                  loading ? 'progress-bar-striped progress-bar-animated' : ''
                "
                role="progressbar"
                aria-label="Basic example"
                :style="`width: ${percentageDone}%`"
                :aria-valuenow="percentageDone"
                aria-valuemin="0"
                aria-valuemax="100"
              >
                {{ percentageDone.toFixed(2) }}%
              </div>
            </div>
            Total progress
            <div class="progress mb-2">
              <div
                class="progress-bar"
                :class="
                  loading ? 'progress-bar-striped progress-bar-animated' : ''
                "
                role="progressbar"
                aria-label="Basic example"
                :style="`width: ${percentageTotalDone}%`"
                :aria-valuenow="percentageTotalDone"
                aria-valuemin="0"
                aria-valuemax="100"
              >
                {{ percentageTotalDone.toFixed(2) }}%
              </div>
            </div>
            <div class="row mb-4">
              <div class="col">
                <p class="mb-1">
                  Number of results:
                  <span
                    class="text-bold"
                    v-html="WSDataResults.total_results_so_far"
                  ></span>
                </p>
              </div>
              <div class="col">
                <p class="mb-1">
                  Projected results:
                  <span
                    class="text-bold"
                    v-html="WSDataResults.projected_results"
                  ></span>
                </p>
              </div>
              <div class="col">
                <p class="mb-1">
                  Batch done:
                  <span
                    class="text-bold"
                    v-html="WSDataResults.batches_done"
                  ></span>
                </p>
              </div>
              <div class="col">
                <p class="mb-1">
                  Status:
                  <!-- <span class="text-bold" v-html="WSDataResults.status"></span> -->
                  <span class="text-bold" v-html="queryStatus"></span>
                </p>
              </div>
            </div>
          </span>
        </div>
      </div>
    </div>
    <div
      v-if="showResultsNotification && queryStatus == 'satisfied' && !loading"
      class="tooltip bs-tooltip-auto fade show"
      role="tooltip"
      style="
        position: absolute;
        left: 50vw;
        transform: translate(-50%, -100%);
        margin: 0px;
        z-index: 10;
      "
      data-popper-placement="top"
    >
      <div class="tooltip-arrow" style="position: absolute; left: 50%"></div>
      <div class="tooltip-inner">
        <div>
          The first pages of results have been fetched. More results will be
          fetched if you move to the next page or if you hit Search whole
          corpus.
        </div>
        <div style="margin-top: 0.5em">
          <input type="checkbox" id="dontShowResultsNotif" />
          <label for="dontShowResultsNotif">Don't show this again</label>
          <button
            @click="dismissResultsNotification"
            style="
              border: solid 1px white;
              border-radius: 0.5em;
              margin-left: 0.25em;
              color: white;
              background-color: transparent;
            "
          >
            OK
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="
        percentageDone == 100 && (!WSDataSentences || !WSDataSentences.result)
      "
      style="text-align: center"
      class="mb-3"
    >
      <div v-if="WSDataResults && WSDataResults.total_results_so_far == 0">
        No results found!
      </div>
      <div>
        Loading results...
      </div>
    </div>
    <div class="container-fluid">
      <div class="row">
        <div class="col-12" v-if="WSDataResults && WSDataResults.result">
          <nav>
            <div class="nav nav-tabs" id="nav-tab" role="tablist">
              <template
                v-for="(resultSet, index) in WSDataResults.result['0']
                  .result_sets"
              >
                <button
                  class="nav-link"
                  :class="index == 0 ? 'active' : ''"
                  :id="`nav-results-tab-${index}`"
                  data-bs-toggle="tab"
                  :data-bs-target="`#nav-results-${index}`"
                  type="button"
                  role="tab"
                  :aria-controls="`nav-results-${index}`"
                  aria-selected="true"
                  :key="`result-btn-${index}`"
                  v-if="
                    (resultSet.type == 'plain' &&
                      WSDataSentences &&
                      WSDataSentences.result) ||
                    resultSet.type != 'plain'
                  "
                >
                  <FontAwesomeIcon
                    v-if="resultSet.type == 'plain'"
                    :icon="['fas', 'barcode']"
                  />
                  <FontAwesomeIcon
                    v-else-if="resultSet.type == 'collocation'"
                    :icon="['fas', 'circle-nodes']"
                  />
                  <FontAwesomeIcon v-else :icon="['fas', 'chart-simple']" />
                  {{ resultSet.name }}
                  <small
                    >(<span v-if="resultSet.type == 'plain'">
                      {{
                        WSDataSentences && WSDataSentences.result[index + 1]
                          ? WSDataSentences.result[index + 1].length
                          : 0
                      }}</span
                    >
                    <span v-else>{{
                      WSDataResults && WSDataResults.result[index + 1]
                        ? WSDataResults.result[index + 1].length
                        : 0
                    }}</span>
                    )</small
                  >
                </button>
              </template>
            </div>
          </nav>
          <div class="tab-content" id="nav-tabContent">
            <div
              class="tab-pane fade show pt-3"
              :class="index == 0 ? 'active' : ''"
              :id="`nav-results-${index}`"
              role="tabpanel"
              :aria-labelledby="`nav-results-${index}-tab`"
              v-for="(resultSet, index) in WSDataResults.result['0'].result_sets"
              :key="`result-tab-${index}`"
            >
              <span
                v-if="
                  resultSet.type == 'plain' &&
                  WSDataSentences &&
                  WSDataSentences.result
                "
              >
                <div class="btn-group mt-2 btn-group-sm mb-3">
                  <a
                    href="#"
                    @click.stop.prevent="plainType = 'table'"
                    class="btn"
                    :class="
                      plainType == 'table' || resultContainsSet(resultSet)
                        ? 'active btn-primary'
                        : 'btn-light'
                    "
                  >
                    <FontAwesomeIcon :icon="['fas', 'table']" />
                    Plain
                  </a>
                  <a
                    v-if="resultContainsSet(resultSet) == false"
                    href="#"
                    @click.stop.prevent="plainType = 'kwic'"
                    class="btn"
                    :class="
                      plainType == 'kwic' ? 'active btn-primary' : 'btn-light'
                    "
                    aria-current="page"
                  >
                    <FontAwesomeIcon :icon="['fas', 'barcode']" />
                    KWIC
                  </a>
                </div>
                <ResultsPlainTableView
                  v-if="plainType == 'table' || resultContainsSet(resultSet)"
                  :data="WSDataSentences.result[index + 1]"
                  :sentences="WSDataSentences.result[-1]"
                  :languages="selectedLanguages"
                  :meta="WSDataMeta"
                  :attributes="resultSet.attributes"
                  :corpora="selectedCorpora"
                  @updatePage="updatePage"
                  :resultsPerPage="resultsPerPage"
                  :loading="loading"
                />
                <ResultsKWICView
                  v-else-if="resultContainsSet(resultSet) == false"
                  :data="WSDataSentences.result[index + 1]"
                  :sentences="WSDataSentences.result[-1]"
                  :languages="selectedLanguages"
                  :meta="WSDataMeta"
                  :attributes="resultSet.attributes"
                  :corpora="selectedCorpora"
                  @updatePage="updatePage"
                  :resultsPerPage="resultsPerPage"
                  :loading="loading"
                />
              </span>
              <ResultsTableView
                v-else-if="resultSet.type != 'plain'"
                :data="WSDataResults.result[index + 1]"
                :languages="selectedLanguages"
                :attributes="resultSet.attributes"
                :meta="WSDataMeta"
                :resultsPerPage="resultsPerPage"
                :type="resultSet.type"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <div
      class="modal fade"
      id="exportModal"
      tabindex="-1"
      aria-labelledby="exportModalLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="exportModalLabel">Export results</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body text-start">
            <label class="form-label">Plain format (TSV + JSON)</label>
            <button
              type="button"
              @click="exportResults('plain', /*download=*/true, /*preview=*/true)"
              class="btn btn-primary me-1"
              data-bs-dismiss="modal"
            >
              Download preview
            </button>
            <!-- <button
              type="button"
              @click="exportResults('plain')"
              class="btn btn-primary me-1"
              data-bs-dismiss="modal"
            >
              Launch export
            </button> -->
          </div>
          <div class="modal-body text-start" v-if="selectedCorpora && selectedCorpora.corpus && selectedCorpora.corpus.shortname.match(/swissdox/i)">
            <label class="form-label">Swissdox</label>
            <button
              type="button"
              @click="exportResults('swissdox')"
              class="btn btn-primary me-1"
            >
              Launch export
            </button>
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
    <div
      class="modal fade"
      id="saveQueryModal"
      tabindex="-1"
      aria-labelledby="saveQueryModalLabel"
      aria-hidden="true"
    >
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="saveQueryModalLabel">Save query</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body text-start">
            <label for="queryName" class="form-label">Query name</label>
            <input
              type="text"
              class="form-control"
              id="queryName"
              v-model="queryName"
            />
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              Close
            </button>
            <button
              type="button"
              :disabled="!queryName"
              @click="saveQuery"
              class="btn btn-primary me-1"
            >
              Save query
            </button>
          </div>
        </div>
      </div>
    </div>
    <div
      class="modal fade"
      id="corpusDetailsModal"
      tabindex="-1"
      aria-labelledby="corpusDetailsModalLabel"
      aria-hidden="true"
      ref="vuemodal"
    >
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="corpusDetailsModalLabel">
              Corpus structure
            </h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body text-start" v-if="corpusModal">
            <div class="row">
              <p class="title mb-0">{{ corpusModal.meta.name }}</p>
              <CorpusGraphView :corpus="corpusModal" v-if="showGraph" />
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
    <div
      class="lcp-progress-bar"
      title="Refresh progress bar"
      v-if="showLoadingBar"
    >
      <div
        class="lcp-progress-bar-driver"
        :style="`width: ${navPercentage}%;`"
      ></div>
    </div>
  </div>
</template>

<style scoped>
.lcp-progress-bar {
  position: fixed;
  width: 100%;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  z-index: 2000;
  opacity: 1;
  transition: opacity 3s linear;
}
.lcp-progress-bar-driver {
  height: 1px;
  width: 0%;
  background-color: #dc6027;
  transition: 0.2s;
  box-shadow: 0px 0px 3px 1px #dc6027ad;
}
.container {
  text-align: left;
}
.pre {
  font-family: "Courier New", Courier, monospace;
}
.query {
  margin-bottom: 100px;
}
.query-field {
  height: 328px;
}
.query-field.error {
  border-color: red;
}
textarea {
  font-family: Consolas, Monaco, Lucida Console, Liberation Mono,
    DejaVu Sans Mono, Bitstream Vera Sans Mono, Courier New, monospace;
}
.error-text {
  margin-top: 7px;
}
.corpus-graph .fa-expand {
  opacity: 0.5;
  float: right;
}
.corpus-graph .fa-expand:hover {
  opacity: 1;
  cursor: pointer;
}
</style>

<script>
import { mapState } from "pinia";

import { useCorpusStore } from "@/stores/corpusStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import { useWsStore } from "@/stores/wsStore";

import Title from "@/components/TitleComponent.vue";
import ResultsTableView from "@/components/results/TableView.vue";
import ResultsKWICView from "@/components/results/KWICView.vue";
import ResultsPlainTableView from "@/components/results/PlainTableView.vue";
import EditorView from "@/components/EditorView.vue";
import CorpusGraphView from "@/components/CorpusGraphView.vue";
import { setTooltips, removeTooltips } from "@/tooltips";


export default {
  name: "QueryView",
  data() {
    return {
      query: "",
      queryDQD: "",
      defaultQueryDQD: "",
      preselectedCorporaId: this.$route.params.id,
      wsConnected: false,
      selectedCorpora: [],
      isQueryValidData: null,
      WSDataResults: "",
      WSDataMeta: {},
      WSDataSentences: "",
      pageSize: 100,
      nResults: 200,
      currentResults: 0,
      selectedLanguages: ["en"],
      queryName: "",
      currentTab: "dqd",
      simultaneousMode: false,
      percentageDone: 0,
      percentageTotalDone: 0,
      percentageWordsDone: 0,
      loading: false,
      stats: null,
      queryTest: "const noop = () => {}",
      resultsPerPage: 100,
      failedStatus: false,
      plainType: "table",
      sqlQuery: null,
      isDebug: false,
      queryStatus: null,
      corpusGraph: null,
      corpusModal: null,
      showGraph: false,
      showResultsNotification: false,
      showLoadingBar: false,
    };
  },
  components: {
    Title,
    ResultsKWICView,
    ResultsPlainTableView,
    ResultsTableView,
    EditorView,
    CorpusGraphView,
  },
  watch: {
    corpora: {
      handler() {
        if (this.preselectedCorporaId) {
          let corpus = this.corpora.filter(
            (corpus) => corpus.meta.id == this.preselectedCorporaId
          );
          if (corpus.length) {
            this.selectedCorpora = {
              name: corpus[0].meta.name,
              value: corpus[0].meta.id,
              corpus: corpus[0],
            };
            this.checkAuthUser()
            this.defaultQueryDQD = corpus[0].sample_query || "";
            this.queryDQD = this.defaultQueryDQD;
            this.preselectedCorporaId = null;
          }
          this.validate();
        }
      },
      immediate: true,
      deep: true,
    },
    messages: {
      handler() {
        let _messages = this.messages;
        if (_messages.length > 0) {
          _messages.forEach((message) => this.onSocketMessage(message));
          useWsStore().clear();
        }
      },
      immediate: true,
      deep: true,
    },
    selectedCorpora() {
      this.checkAuthUser();
      let updateGraph = false;
      if (this.corpusGraph) {
        this.corpusGraph = null;
        updateGraph = true;
      }
      // this.validate();
      if (this.selectedCorpora) {
        this.defaultQueryDQD = this.selectedCorpora.corpus.sample_query || "";
        history.pushState(
          {},
          null,
          `/query/${this.selectedCorpora.value}/${this.selectedCorpora.corpus.shortname}`
        );
        if (updateGraph)
          // make sure to delay the re-setting of corpusGraph
          setTimeout(() => (this.corpusGraph = this.selectedCorpora.corpus), 1);
      } else {
        history.pushState({}, null, `/query/`);
      }
      if (
        this.selectedLanguages &&
        !this.availableLanguages.includes(this.selectedLanguages)
      ) {
        this.selectedLanguages = [this.availableLanguages[0]];
      }
      // Switched which corpus is selected: clear results
      if (this.selectedCorpora) {
        this.percentageDone = 0;
        this.percentageTotalDone = 0;
        this.failedStatus = false;
        this.loading = false;
        this.WSDataResults = {};
        this.WSDataMeta = {};
        this.WSDataSentences = {};
      }
    },
    WSDataResults() {
      if (this.WSDataResults) {
        if (this.WSDataResults.percentage_done) {
          this.percentageDone = this.WSDataResults.percentage_done;
        }
        if (this.WSDataResults.percentage_words_done) {
          this.percentageWordsDone = this.WSDataResults.percentage_words_done;
        }
        if (
          this.WSDataResults.total_results_so_far &&
          this.WSDataResults.projected_results
        ) {
          this.percentageTotalDone =
            (this.WSDataResults.total_results_so_far /
              this.WSDataResults.projected_results) *
            100;
        }
        // if (["finished"].includes(this.WSDataResults.status)) {
        //   this.percentageDone = 100;
        //   this.percentageTotalDone = 100;
        //   this.loading = false;
        // }
        // if (["satisfied", "overtime"].includes(this.WSDataResults.status)) {
        //   // this.percentageDone = this.WSDataResults.hit_limit/this.WSDataResults.projected_results*100.
        //   this.percentageDone = 100;
        //   this.loading = false;
        // }
        // console.log("XXX", this.percentageTotalDone, this.percentageDone);
      }

      if (this.WSDataResults.percentage_done >= 100) {
        this.loading = false;
      }
    },
    query() {
      // console.log("Check is valid")
      if (this.currentTab != "dqd") {
        this.validate();
      }
    },
    loading() {
      if (this.loading) {
        this.showLoadingBar = true;
      } else {
        setTimeout(() => {
          this.showLoadingBar = false;
        }, 1500);
      }
    },
  },
  methods: {
    resultContainsSet(resultSet) {
      if (!(resultSet.attributes instanceof Array)) return false;
      let entities = resultSet.attributes.find((v) => v.name == "entities");
      if (!entities) return false;
      return Boolean(
        entities.data instanceof Array &&
          entities.data.find((v) => ["set", "group"].includes(v.type))
      );
    },
    updateLoading(status) {
      this.queryStatus = status;
      if (["finished"].includes(status)) {
        this.percentageDone = 100;
        this.percentageTotalDone = 100;
        this.loading = false;
      }
      if (["satisfied", "overtime"].includes(status)) {
        this.percentageDone = 100;
        this.loading = false;
      }
    },
    updatePage(currentPage) {
      let newNResults = this.resultsPerPage * Math.max(currentPage + 1, 3);
      console.log(
        "PageUpdate",
        newNResults,
        this.nResults,
        this.WSDataSentences
      );
      if (
        newNResults > this.nResults &&
        (!this.WSDataSentences ||
          (this.WSDataSentences && this.WSDataSentences.more_data_available))
      ) {
        console.log("Submit");
        this.nResults = newNResults;
        this.submit(null, /*resumeQuery=*/true, /*cleanResults=*/false);
      }
    },
    updateQueryDQD(queryDQD) {
      if (this.loading)
        this.loading = "resubmit";
      this.queryDQD = queryDQD;
      this.validate();
    },
    checkAuthUser() {
      // Check if user is authaticated
      if (this.selectedCorpora
        && this.selectedCorpora.corpus.authRequired == true
        && (
          !this.userData.user.displayName
          || (this.selectedCorpora.corpus.isSwissdox == true && this.userData.user.swissdoxUser != true)
        )
      ) {
        window.location.replace("/login");
      }
    },
    // sendLeft() {
    //   this.$socket.sendObj({
    //     room: this.roomId,
    //     // room: null,
    //     action: "left",
    //     user: this.userData.user.id,
    //   });
    //   this.wsConnected = false;
    //   console.log("Left WS");
    // },
    // connectToRoom() {
    //   console.log("Connect to WS room", this.wsConnected, this.$socket.readyState)
    //   if (this.$socket.readyState != 1 || this.wsConnected == false){
    //     console.log("Connect to WS")
    //     this.waitForConnection(() => {
    //       this.$socket.sendObj({
    //         room: this.roomId,
    //         // room: null,
    //         action: "joined",
    //         user: this.userId,
    //       });
    //       this.wsConnected = true;
    //       this.$socket.onmessage = this.onSocketMessage;
    //       console.log("Connected to WS")
    //       this.validate();
    //     }, 500);
    //   }
    // },
    // waitForConnection(callback, interval) {
    //   if (this.$socket.readyState === 1) {
    //     callback();
    //   } else {
    //     setTimeout(() => {
    //       this.waitForConnection(callback, interval);
    //     }, interval);
    //   }
    // },
    onSocketMessage(data) {
      // the below is just temporary code
      // let data = JSON.parse(event.data);
      // console.log("R", event)
      if (Object.prototype.hasOwnProperty.call(data, "action")) {
        if (data["action"] === "interrupted") {
          console.log("Query interrupted", data);
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.toString(),
          });
          return;
        }
        if (data["action"] === "timeout") {
          console.log("Query job expired", data);
          this.failedStatus = true;
          this.submit(null, false, false);
          return;
        }
        if (data["action"] === "validate") {
          // Validate is called after setting availableLanguages, so it's a good time to check selectedLanguages
          this.selectedLanguages = this.selectedLanguages.filter(v=>this.availableLanguages.includes(v));
          if (this.selectedLanguages==0) {
            this.selectedLanguages = [this.availableLanguages[0]];
          }
          // console.log("Query validation", data);
          if (data.kind == "dqd" && data.valid == true) {
            // console.log("Set query from server");
            this.query = JSON.stringify(data.json, null, 2);
          }
          this.isQueryValidData = data;
          console.log("isQueryValidData", data);
          return;
        }
        if (data["action"] === "stats") {
          // console.log("stats", data);
          this.stats = data;
          return;
        }
        if (data["action"] === "update_config") {
          // todo: when a new corpus is added, all connected websockets
          // will get this message containing the new config data. plz
          // ensure that it gets added to the corpusstore properly and
          // the app is updated accordingly
          delete data["config"]["-1"];
          // todo: no idea if this is right:
          useCorpusStore().corpora = Object.keys(data["config"]).map(
            (corpusId) => {
              let corpus = data["config"][corpusId];
              corpus.meta["id"] = corpusId;
              return corpus;
            }
          );
          // we could also do this but we already have the data here...
          // useCorpusStore().fetchCorpora();
          return;
        }
        if (data["action"] === "fetch_queries") {
          console.log("do something here with the fetched queries?", data);
          return;
        } else if (data["action"] === "store_query") {
          console.log("query stored", data);
          return;
        } else if (data["action"] == "export_link") {
          this.loading = false;
          this.percentageDone = this.WSDataResults.percentage_done;
          const {schema_path} = this.selectedCorpora.corpus;
          useCorpusStore().fetchExport(schema_path, data.fn);
          useNotificationStore().add({
            type: "success",
            text: "Initiated export download"
          });
        }else if (data["action"] === "stopped") {
          if (data["n"]) {
            console.log("queries stopped", data);
            useNotificationStore().add({
              type: "success",
              text: "Query stopped",
            });
            this.loading = false;
          }
          return;
        } else if (data["action"] === "query_result") {
          // console.log("query_result", data);
          this.updateLoading(data.status);
          if (
            this.failedStatus &&
            data.result.length < this.WSDataResults.n_results
          ) {
            return;
          }
          this.sqlQuery = null;
          if (data.sql) {
            this.sqlQuery = data.sql;
          }
          if (data.consoleSQL) {
            console.log("SQL", data.consoleSQL);
          }
          this.failedStatus = false;
          data["n_results"] = data["result"].length;
          this.WSDataResults = data;
          return;
        } else if (data["action"] === "sentences") {
          // console.log("sentences", data);
          this.updateLoading(data.status);
          if (
            this.WSDataSentences &&
            this.WSDataSentences.first_job == data.first_job &&
            data.full == false
          ) {
            Object.keys(this.WSDataSentences.result).forEach((key) => {
              if (key > 0 && key in data.result) {
                this.WSDataSentences.result[key] = this.WSDataSentences.result[
                  key
                ].concat(data.result[key]);
                this.nResults = this.WSDataSentences.result[key].length;
                this.currentResults = this.WSDataSentences.result[key].length;
              }
            });
            if (-1 in data.result) {
              this.WSDataSentences.result[-1] = {
                ...this.WSDataSentences.result[-1],
                ...data.result[-1],
              };
            }
          } else {
            this.WSDataSentences = data;
            if (this.WSDataResults) {
              if (!this.WSDataResults.result)
                this.WSDataResults.result = {};
              if (!this.WSDataResults.result["0"] || !this.WSDataResults.result["0"].result_sets)
                this.WSDataResults.result["0"] = {result_sets: []};
              this.WSDataResults.result["0"].result_sets.forEach(
                (_resultSet, index) => {
                  if (_resultSet.type == "plain") {
                    let resultIndex = index + 1;
                    if (!(resultIndex in this.WSDataSentences.result)) {
                      this.WSDataSentences.result[resultIndex] = [];
                    }
                    this.nResults =
                      this.WSDataSentences.result[resultIndex].length;
                    this.currentResults =
                      this.WSDataSentences.result[resultIndex].length;
                  }
                }
              );
            }
          }
          this.percentageDone = data.percentage_done;
          this.percentageWordsDone = data.percentage_words_done;
          // if (["satisfied", "overtime"].includes(this.WSDataResults.status)) {
          //   this.loading = false;
          // }
          return;
        } else if (data["action"] == "meta") {
          const meta = data.result["-2"]; // change this?
          for (let layer in meta) {
            this.WSDataMeta[layer] = this.WSDataMeta[layer] || {};
            this.WSDataMeta[layer] = {...this.WSDataMeta[layer], ...meta[layer]};
          }
        } else if (data["action"] === "started_export") {
          this.loading = false;
          useNotificationStore().add({
            type: "success",
            text: "Started the export process...",
          });
        } else if (data["action"] === "failed") {
          this.loading = false;
          if (data.sql) {
            this.sqlQuery = data.sql;
          }
          useNotificationStore().add({
            type: "error",
            text: data.value,
          });
        } else if (data["action"] === "query_error") {
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.info,
          });
        }
      } else if (Object.prototype.hasOwnProperty.call(data, "status")) {
        if (data["status"] == "failed") {
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.value,
          });
        }
        if (data["status"] == "error") {
          this.loading = false;
          useNotificationStore().add({
            type: "error",
            text: data.info,
          });
        }
      }

      // we might need this block for stats related stuff later, don't worry about it much right now
      if (this.simultaneousMode) {
        this.allResults = this.allResults.concat(data["result"]);
        if (this.allResults.length >= data["total_results_requested"]) {
          this.allResults = this.allResults.slice(
            0,
            data["total_results_requested"]
          );
          this.enough(data["simultaneous"]);
          data["status"] = "satisfied";
        }
        data["first_result"] = this.allResults[0];
        data["n_results"] = this.allResults.length;
        delete data["result"];
        data["percentage_done"] += this.percentageDone;
        this.WSDataResults = data;
      }
    },
    isSubmitDisabled() {
      return (this.selectedCorpora && this.selectedCorpora.length == 0) ||
              this.loading === true ||
              (this.isQueryValidData != null && this.isQueryValidData.valid == false) ||
              !this.query ||
              !this.selectedLanguages
    },
    switchGraph() {
      if (!this.corpusGraph && this.selectedCorpora)
        this.corpusGraph = this.selectedCorpora.corpus;
      else this.corpusGraph = null;
    },
    openGraphInModal() {
      if (!this.corpusGraph) return;
      this.corpusModal = this.corpusGraph;
      // Cannot have more than one graph displayed at a time
      let restoreSmallGraphWith = this.corpusGraph;
      this.corpusGraph = null;
      this.$refs.vuemodal.addEventListener("shown.bs.modal", () => {
        this.showGraph = true;
      });
      this.$refs.vuemodal.addEventListener("hide.bs.modal", () => {
        this.showGraph = false;
        if (restoreSmallGraphWith) this.corpusGraph = restoreSmallGraphWith;
        restoreSmallGraphWith = null;
      });
    },
    resizeGraph(container) {
      let svg = container.querySelector("svg");
      if (svg === null) return;
      let g = svg.querySelector("g");
      if (g === null) return;
      svg.style.height = `${g.getBoundingClientRect().height}px`;
    },
    async exportResults(format, download=false, preview=false) {
      const to_export = {};
      to_export.format = {
        'plain': 'dump',
        'swissdox': 'swissdox'
      }[format];
      to_export.preview = preview;
      to_export.download = download;
      let full = !preview;
      this.submit(null, true, false, /*full=*/full, /*to_export=*/to_export);
    },
    submitFullSearch() {
      this.submit(null, true, false, true);
    },
    async submit(
      event,
      resumeQuery = false,
      cleanResults = true,
      fullSearch = false,
      to_export = false
    ) {
      if (!localStorage.getItem("dontShowResultsNotif"))
        this.showResultsNotification = true;
      if (resumeQuery == false) {
        this.failedStatus = false;
        this.stop();
        this.nResults = this.pageSize * 2; // We want load 2 pages at first
        if (cleanResults == true) {
          this.WSDataResults = {};
          this.WSDataSentences = {};
        }
      }
      let data = {
        corpora: this.selectedCorpora.value,
        query: this.query,
        user: this.userData.user.id,
        room: this.roomId,
        page_size: this.resultsPerPage,
        languages: this.selectedLanguages,
        total_results_requested: this.nResults,
        stats: true,
        resume: resumeQuery,
        simultaneous: this.simultaneousMode,
      };
      if (resumeQuery) {
        data["first_job"] = this.WSDataResults.job;
        data["previous"] = this.WSDataResults.job;
        data["current_kwic_lines"] = this.currentResults;
      }
      if (fullSearch) {
        data["full"] = true;
      }
      if (to_export) {
        data["to_export"] = to_export;
      }
      let retval = await useCorpusStore().fetchQuery(data);
      if (retval.status == "started") {
        this.loading = true;
        this.percentageDone = 0.001;
        this.percentageWordsDone = 0;
      }
    },
    resume() {
      this.submit(null, true);
    },
    stop() {
      this.percentageDone = 0;
      this.percentageTotalDone = 0;
      this.failedStatus = false;
      useWsStore().sendWSMessage({
        action: "stop",
      });
      this.loading = false;
    },
    enough(job) {
      useWsStore().sendWSMessage({
        action: "enough_results",
        job: job,
      });
    },
    validate() {
      useWsStore().sendWSMessage({
        action: "validate",
        query: this.currentTab == "json" ? this.query : this.queryDQD + "\n",
        corpus: this.selectedCorpora.value
      });
    },
    saveQuery() {
      let data = {
        // corpora: this.selectedCorpora.map((corpus) => corpus.value),
        corpora: this.selectedCorpora.value,
        query: this.query,
        user: this.userData.user.id,
        room: this.roomId,
        // room: null,
        page_size: this.pageSize,
        languages: this.selectedLanguages,
        total_results_requested: this.nResults,
        query_name: this.queryName,
      };
      useCorpusStore().saveQuery(data);
    },
    fetch() {
      let data = {
        user: this.userData.user.id,
        room: this.roomId,
        // room: null,
      };
      useCorpusStore().fetchQueries(data);
    },
    dismissResultsNotification() {
      this.showResultsNotification = false;
      const dontShowResultsNotif = document.querySelector(
        "#dontShowResultsNotif"
      );
      if (dontShowResultsNotif && dontShowResultsNotif.checked)
        localStorage.setItem("dontShowResultsNotif", true);
    }
  },
  computed: {
    ...mapState(useCorpusStore, ["queryData", "corpora"]),
    ...mapState(useUserStore, ["userData", "roomId", "debug"]),
    ...mapState(useWsStore, ["messages"]),
    availableLanguages() {
      let retval = [];
      if (this.selectedCorpora) {
        if (
          this.corpora.filter(
            (corpus) => corpus.meta.id == this.selectedCorpora.value
          ).length
        ) {
          retval = Object.keys(
            this.corpora.filter(
              (corpus) => corpus.meta.id == this.selectedCorpora.value
            )[0].layer
          )
            .filter((key) => key.startsWith("Token@") || key.startsWith("Token:"))
            .map((key) => key.replace(/Token[@:]/, ""));
          if (retval.length == 0) {
            retval = ["en"];
          }
        }
      }
      return retval;
    },
    corporaOptions() {
      return this.corpora
        ? this.corpora.map((corpus) => {
            return {
              name: corpus.meta.name,
              value: corpus.meta.id,
              corpus: corpus,
            };
          })
        : [];
    },
    navPercentage() {
      if (this.loading)
        return Math.max(this.percentageDone, this.percentageWordsDone);
      else return this.percentageDone;
    },
  },
  mounted() {
    setTooltips();
  },
  beforeUnmount() {
    removeTooltips();
  },
};
</script>
