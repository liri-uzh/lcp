<template>
  <div class="query">
    <div class="container-fluid mt-4 px-4">
      <div class="row">
        <div class="col">
          <Title :title="$t('common-query')" />
        </div>
      </div>
      <div class="row mt-2">
        <div class="col-12 col-md-4">
          <div class="form-group row">
            <label for="staticEmail" class="col-sm-3 col-form-label">
              {{ $t('common-corpora') }}
              <!-- <div
                v-if="selectedCorpora && selectedCorpora.corpus"
                class="details-button icon-3 tooltips corpus-structure-button"
                @click.stop="switchGraph()"
                title="Show/hide corpus structure"
              >
                <FontAwesomeIcon :icon="['fas', 'circle-info']" />
              </div> -->
            </label>
            <div class="col-sm-8">
              <multiselect
                v-model="selectedCorpora"
                :options="corporaOptions"
                placeholder="Select corpus"
                :multiple="false"
                label="name"
                track-by="value"
              ></multiselect>
            </div>
            <span
              class="btn icon-x col-sm-1"
              @click.stop="openCorpusDetailsModal(selectedCorpora.corpus)"
              v-if="selectedCorpora && selectedCorpora.corpus"
            >
              <FontAwesomeIcon :icon="['fas', 'circle-info']" />
            </span>
          </div>
          <div class="form-group row mt-1">
            <label for="staticEmail" class="col-sm-3 col-form-label">{{ $t('common-languages') }}</label>
            <div class="col-sm-9">
              <multiselect
                v-model="selectedLanguages"
                :options="availableLanguages"
                :multiple="true"
                 v-if="selectedCorpora && availableLanguages.length > 1"
              ></multiselect>
              <label class="col-sm-3 col-form-label" v-else-if="selectedCorpora && availableLanguages.length == 1">
                {{ getLanguageName(availableLanguages[0]) }}
              </label>
            </div>
          </div>
        </div>
      </div>
      <div class="row mt-5" v-if="selectedCorpora">
        <div class="col-12 mt-3">
          <div class="form-floating mb-3">
            <nav>
              <div class="nav nav-tabs" id="nav-main-tab" role="tablist"
                :class="{ 'reverse-items': ['soundscript', 'videoscope'].includes(appType) }">
                <button class="nav-link" :class="{ active: activeMainTab === 'query' }" id="nav-query-tab"
                  data-bs-toggle="tab" data-bs-target="#nav-query" type="button" role="tab" aria-controls="nav-query"
                  aria-selected="true" @click="activeMainTab = 'query'">
                  {{ $t('common-query') }}
                </button>
                <button class="nav-link" :class="{ active: activeMainTab === 'data' }" id="nav-data-tab"
                  data-bs-toggle="tab" data-bs-target="#nav-data" type="button" role="tab" aria-controls="nav-data"
                  aria-selected="false" @click="activeMainTab = 'data'">
                  {{ $t('common-data') }}
                  <div class="lds-ripple lds-white lds-xs" v-if="loading">
                    <div></div>
                    <div></div>
                  </div>
                </button>
                <!-- <button
                  class="nav-link"
                  :class="{ active: activeMainTab === 'explore' }"
                  id="nav-explore-tab"
                  data-bs-toggle="tab"
                  data-bs-target="#nav-explore"
                  type="button"
                  role="tab"
                  aria-controls="nav-explore"
                  aria-selected="false"
                  v-if="showExploreTab()"
                >
                  Explore
                </button> -->
              </div>
            </nav>
            <div class="tab-content" id="nav-main-tabContent">
              <div class="tab-pane fade pt-3"
                :class="{ active: activeMainTab === 'query', show: activeMainTab === 'query' }" id="nav-query"
                role="tabpanel" aria-labelledby="nav-query-tab">
                <div class="mt-3">
                  <button type="button" @click="submit" class="btn btn-primary me-1 mb-1"
                    :disabled="isSubmitDisabled || !currentQuery">
                    <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
                    {{ loading == "resubmit" ? $t('common-resubmit') : $t('common-submit') }}
                  </button>

                  <button
                    type="button"
                    v-if="queryStatus in {'satisfied':1,'finished':1} && !loading && userData.user.anon != true"
                    class="btn btn-primary me-1 mb-1"
                    data-bs-toggle="modal"
                    data-bs-target="#exportModal"
                    @click="setExportFilename('xml')"
                  >
                    <FontAwesomeIcon :icon="['fas', 'file-export']" />
                    {{ $t('common-export') }}
                  </button>

                  <button type="button" v-if="queryStatus == 'satisfied' && !loading && userData.user.anon != true"
                    @click="submitFullSearch" class="btn btn-primary me-1 mb-1">
                    <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
                    {{ $t('common-search-whole') }}
                  </button>
                  <button v-else-if="loading" type="button" @click="stop" :disabled="loading == false"
                    class="btn btn-primary me-1 mb-1">
                    <FontAwesomeIcon :icon="['fas', 'xmark']" />
                    {{ $t('common-stop') }}
                  </button>
                </div>
                <div class="row">
                  <div class="col-12 col-md-6">
                    <div class="form-floating mb-3">
                      <nav>
                        <div class="nav nav-tabs justify-content-end" id="nav-query-tab" role="tablist">
                          <button class="nav-link active" id="nav-plaintext-tab" data-bs-toggle="tab"
                            data-bs-target="#nav-plaintext" type="button" role="tab" aria-controls="nav-plaintext"
                            aria-selected="true" @click="setTab('text')">
                            {{ $t('common-text') }}
                          </button>
                          <button class="nav-link" id="nav-dqd-tab" data-bs-toggle="tab"
                            data-bs-target="#nav-dqd" type="button" role="tab" aria-controls="nav-dqd"
                            aria-selected="false" @click="setTab('dqd')">
                            DQD
                          </button>
                          <button class="nav-link" id="nav-cqp-tab" data-bs-toggle="tab" data-bs-target="#nav-cqp"
                            type="button" role="tab" aria-controls="nav-cqp" aria-selected="false"
                            @click="setTab('cqp')">
                            CQP
                          </button>
                          <button class="nav-link" id="nav-json-tab" data-bs-toggle="tab" data-bs-target="#nav-json"
                            type="button" role="tab" aria-controls="nav-json" aria-selected="false"
                            @click="setTab('json')" v-if="local">
                            JSON
                          </button>
                          <button v-if="sqlQuery" class="nav-link" id="nav-sql-tab" data-bs-toggle="tab"
                            data-bs-target="#nav-sql" type="button" role="tab" aria-controls="nav-sql"
                            aria-selected="false" @click="setTab(currentTab = 'sql')">
                            SQL
                          </button>
                        </div>
                      </nav>
                      <div class="tab-content" id="nav-query-tabContent">
                        <div class="tab-pane fade show active pt-3" id="nav-plaintext" role="tabpanel"
                          aria-labelledby="nav-plaintext-tab">
                          <input class="form-control" type="text" :placeholder="$t('common-plain-query')" :class="isQueryValidData == null || isQueryValidData.valid == true
                            ? 'ok'
                            : 'error'
                            " v-model="textsearch" @keyup="$event.key == 'Enter' && this.submit()" />
                          <!-- <label for="floatingTextarea">Query</label> -->
                          <p class="error-text text-danger" v-if="isQueryValidData && isQueryValidData.valid != true">
                            {{ isQueryValidData.error }}
                          </p>
                        </div>
                        <div class="tab-pane fade pt-3" id="nav-dqd" role="tabpanel"
                          aria-labelledby="nav-results-tab">
                          <EditorView :query="queryDQD" :defaultQuery="defaultQueryDQD" :corpora="selectedCorpora"
                            :invalidError="isQueryValidData && isQueryValidData.valid != true
                              ? isQueryValidData.error
                              : null
                              " @submit="submit" @update="updateQueryDQD" />
                          <p class="error-text text-danger mt-3" v-if="
                            isQueryValidData && isQueryValidData.valid != true
                          ">
                            {{ isQueryValidData.error }}
                          </p>
                        </div>
                        <div class="tab-pane fade pt-3" id="nav-cqp" role="tabpanel" aria-labelledby="nav-cqp-tab">
                          <textarea class="form-control query-field" :placeholder="$t('common-cqp-query')"
                            :class="isQueryValidData == null || isQueryValidData.valid == true
                              ? 'ok'
                              : 'error'
                              " v-model="cqp"
                            @keyup="$event.key == 'Enter' && $event.ctrlKey && this.submit()"></textarea>
                          <!-- <label for="floatingTextarea">Query</label> -->
                          <p class="error-text text-danger" v-if="isQueryValidData && isQueryValidData.valid != true">
                            {{ isQueryValidData.error }}
                          </p>
                        </div>
                        <div class="tab-pane fade pt-3" id="nav-json" role="tabpanel" aria-labelledby="nav-json-tab">
                          <textarea class="form-control query-field" placeholder="Query (e.g. test.*)" :class="isQueryValidData == null || isQueryValidData.valid == true
                            ? 'ok'
                            : 'error'
                            " v-model="query"></textarea>
                          <!-- <label for="floatingTextarea">Query</label> -->
                          <p class="error-text text-danger" v-if="isQueryValidData && isQueryValidData.valid != true">
                            {{ isQueryValidData.error }}
                          </p>
                        </div>
                        <div v-if="sqlQuery" class="tab-pane fade pt-3" id="nav-sql" role="tabpanel"
                          aria-labelledby="nav-sql-tab">
                          <textarea class="form-control query-field" v-model="sqlQuery"></textarea>
                        </div>
                      </div>
                    </div>
                    <div class="mt-5">
                      <button type="button" v-if="!loading && userData.user.anon != true && userQueryVisible()"
                        :disabled="saveQueryDisabled" class="btn btn-primary me-2 mb-2"
                        data-bs-toggle="modal" data-bs-target="#saveQueryModal">
                        <FontAwesomeIcon :icon="['fas', 'file-export']" />
                        {{ $t('common-save-query') }}
                      </button>
                      <button type="button" v-if="!loading && userQueryVisible() && selectedQuery"
                        :disabled="(isQueryValidData && isQueryValidData.valid != true)"
                        class="btn btn-danger me-2 mb-2" data-bs-toggle="modal" data-bs-target="#deleteQueryModal">
                        <FontAwesomeIcon :icon="['fas', 'trash']" />
                        {{ $t('common-delete-query') }}
                      </button>
                      <div v-if="userQueryVisible()">
                        <multiselect v-model="selectedQuery" :options="processedSavedQueries" :searchable="true"
                          :clear-on-select="false" :close-on-select="true" :placeholder="$t('common-select-saved-queries')"
                          label="query_name" track-by="idx" @select="handleQuerySelection"></multiselect>
                        <!-- <p v-if="selectedQuery">
                          Selected query: {{ selectedQuery.query_name }}
                        </p> -->
                      </div>
                    </div>
                  </div>
                  <div class="col-12 col-md-6">
                    <div class="corpus-graph mt-3" v-if="selectedCorpora">
                      <FontAwesomeIcon :icon="['fas', 'expand']" @click="openGraphInModal" data-bs-toggle="modal"
                        data-bs-target="#corpusGraphModal" />
                      <CorpusGraphViewNew :corpus="selectedCorpora.corpus" :key="graphIndex" v-if="showGraph == 'main'"
                        @graphReady="resizeGraph" />
                    </div>
                  </div>
                </div>
              </div>
              <div class="tab-pane fade" :class="{ active: activeMainTab === 'data', show: activeMainTab === 'data' }"
                id="nav-data" role="tabpanel" aria-labelledby="nav-data-tab">
                <PlayerComponent v-if="selectedCorpora && showExploreTab()" :key="selectedCorpora"
                  :selectedCorpora="selectedCorpora" :selectedMediaForPlay="selectedMediaForPlay"
                  :hoveredResult="hoveredResult" :dataType="corpusDataType(selectedCorpora.corpus)"
                  @switchToQueryTab="setMainTab" />

                <hr>
                <div class="mt-5 row" v-if="querySubmitted">
                  <div v-if="loading" class="col-12 col-md-1">
                    <button type="button" @click="stop"
                      class="btn btn-primary me-1 mb-1">
                      <FontAwesomeIcon :icon="['fas', 'xmark']" />
                      {{ $t('common-stop') }}
                    </button>
                  </div>
                  <div :class="`col-12 col-md-${loading ? 5 : 6}`">
                    <h6 class="mb-2">{{ $t('common-query-result') }}</h6>
                    <div class="progress mb-2">
                      <div class="progress-bar" :class="loading ? 'progress-bar-striped progress-bar-animated' : ''
                        " role="progressbar" :style="`width: ${percentageDone}%`" :aria-valuenow="percentageDone"
                        aria-valuemin="0" aria-valuemax="100">
                        {{ (percentageDone || 0.0).toFixed(2) }}%
                      </div>
                    </div>
                  </div>
                  <div class="col-12 col-md-6">
                    <h6 class="mb-2">{{ $t('common-total-progress') }}</h6>
                    <div class="progress mb-2">
                      <div class="progress-bar" :class="loading ? 'progress-bar-striped progress-bar-animated' : ''
                        " role="progressbar" :style="`width: ${percentageTotalDone}%`"
                        :aria-valuenow="percentageTotalDone" aria-valuemin="0" aria-valuemax="100">
                        {{ percentageTotalDone.toFixed(2) }}%
                      </div>
                    </div>
                  </div>
                  <div class="col-12" id="results">
                    <div class="row mb-4">
                      <div class="col">
                        <p class="mb-1">
                          {{ $t('common-number-results') }}:
                          <span class="text-bold" v-html="WSDataResults.total_results_so_far"></span>
                        </p>
                      </div>
                      <div class="col">
                        <p class="mb-1">
                          {{ $t('common-projected-results') }}:
                          <span class="text-bold" v-html="WSDataResults.projected_results"></span>
                        </p>
                      </div>
                      <div class="col">
                        <p class="mb-1">
                          {{ $t('common-batch-done') }}:
                          <span class="text-bold" v-html="WSDataResults.batches_done"></span>
                        </p>
                      </div>
                      <div class="col">
                        <p class="mb-1">
                          {{ $t('common-status') }}:
                          <!-- <span class="text-bold" v-html="WSDataResults.status"></span> -->
                          <span class="text-bold" v-html="queryStatus"></span>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="showResultsNotification && queryStatus == 'satisfied' && !loading"
                  class="tooltip bs-tooltip-auto fade show" role="tooltip" style="
                    position: absolute;
                    left: 50vw;
                    transform: translate(-50%, -100%);
                    margin: 0px;
                    z-index: 10;
                  " data-popper-placement="top">
                  <div class="tooltip-arrow" style="position: absolute; left: 50%"></div>
                  <div class="tooltip-inner">
                    <div>
                      {{ $t('platform-general-fetched-results') }}
                    </div>
                    <div style="margin-top: 0.5em">
                      <input type="checkbox" id="dontShowResultsNotif" />
                      <label for="dontShowResultsNotif">{{ $t('common-dont-show-again') }}</label>
                      <button @click="dismissResultsNotification" style="
                          border: solid 1px white;
                          border-radius: 0.5em;
                          margin-left: 0.25em;
                          color: white;
                          background-color: transparent;
                        ">
                        {{ $t('common-ok').toUpperCase() }}
                      </button>
                    </div>
                  </div>
                </div>

                <div v-if="percentageDone == 100 && (!WSDataSentences || !WSDataSentences.result)"
                  style="text-align: center" class="mb-3 mt-2">
                  <div v-if="noResults">
                    {{ $t('common-no-results') }}!
                  </div>
                  <div v-else>
                    {{ $t('common-loading-results') }}...
                  </div>
                </div>
                <div class="mt-2">
                  <div class="row">
                    <div class="col-12" v-if="WSDataResults && WSDataResults.result">
                      <div
                        v-if="queryStatus in {'satisfied':1,'finished':1} && !loading && userData.user.anon != true && !noResults"
                        data-bs-toggle="modal"
                        data-bs-target="#exportModal"
                        @click="setExportFilename('xml')"
                        class="export btn btn-primary me-1 mb-1"
                        :title="$t('common-export')"
                      >
                        <FontAwesomeIcon :icon="['fas', 'file-export']" />
                      </div>
                      <div
                        v-else
                        class="export btn btn-primary me-1 mb-1"
                        disabled="true"
                        :title="$t('common-export')"
                      >
                        <FontAwesomeIcon :icon="['fas', 'file-export']" />
                      </div>
                      <nav>
                        <div class="nav nav-tabs" id="nav-results-tabs" role="tablist">
                          <template
                            v-for="(resultSet, index) in WSDataResults.result['0']
                              .result_sets"
                          >
                            <button
                              class="nav-link"
                              :class="index == 0 ? 'active' : ''"
                              :id="`nav-results-tabs-${index}`"
                              data-bs-toggle="tab"
                              :data-bs-target="`#nav-results-${index}`"
                              @click.stop.prevent="activeResultIndex = (index+1)"
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
                              ">
                              <FontAwesomeIcon v-if="resultSet.type == 'plain'" :icon="['fas', 'barcode']" />
                              <FontAwesomeIcon v-else-if="resultSet.type == 'collocation'"
                                :icon="['fas', 'circle-nodes']" />
                              <FontAwesomeIcon v-else :icon="['fas', 'chart-simple']" />
                              {{ resultSet.name }}
                              <small>
                                <span>{{
                                  WSDataResults && WSDataResults.result[index + 1]
                                    ? WSDataResults.result[index + 1].length
                                    : 0
                                }}</span>
                              </small
                              >
                            </button>
                          </template>
                        </div>
                      </nav>
                      <div class="tab-content" id="nav-results-tabsContent">
                        <div class="tab-pane fade show pt-3" :class="index == 0 ? 'active' : ''"
                          :id="`nav-results-${index}`" role="tabpanel" :aria-labelledby="`nav-results-${index}-tab`"
                          v-for="(resultSet, index) in WSDataResults.result['0'].result_sets"
                          :key="`result-tab-${index}`">
                          <span v-if="
                            resultSet.type == 'plain' &&
                            WSDataSentences &&
                            WSDataSentences.result
                          ">
                            <div class="btn-group mt-2 btn-group-sm mb-3">
                              <a href="#" @click.stop.prevent="plainType = 'table'" class="btn" :class="plainType == 'table' || resultContainsSet(resultSet)
                                ? 'active btn-primary'
                                : 'btn-light'
                                ">
                                <FontAwesomeIcon :icon="['fas', 'table']" />
                                {{ $t('common-plain') }}
                              </a>
                              <a v-if="resultContainsSet(resultSet) == false" href="#"
                                @click.stop.prevent="plainType = 'kwic'" class="btn" :class="plainType == 'kwic' ? 'active btn-primary' : 'btn-light'
                                  " aria-current="page">
                                <FontAwesomeIcon :icon="['fas', 'barcode']" />
                                KWIC
                              </a>
                            </div>
                            <ResultsPlainTableView
                              v-if="plainType == 'table' || resultContainsSet(resultSet)"
                              :data="WSDataResults.result[index + 1] || []"
                              :sentences="WSDataSentences.result[-1] || []"
                              :languages="selectedLanguages"
                              :meta="WSDataMeta"
                              :attributes="resultSet.attributes"
                              :corpora="selectedCorpora"
                              @updatePage="updatePage"
                              @playMedia="playMedia"
                              @hoverResultLine="hoverResultLine"
                              :resultsPerPage="resultsPerPage"
                              :loading="loading"
                            />
                            <ResultsKWICView
                              v-else-if="resultContainsSet(resultSet) == false"
                              :data="WSDataResults.result[index + 1] || []"
                              :sentences="WSDataSentences.result[-1] || []"
                              :languages="selectedLanguages"
                              :meta="WSDataMeta"
                              :attributes="resultSet.attributes"
                              :corpora="selectedCorpora"
                              @updatePage="updatePage"
                              :resultsPerPage="resultsPerPage"
                              :loading="loading"
                            />
                          </span>
                          <ResultsTableView v-else-if="resultSet.type != 'plain'"
                            :data="WSDataResults.result[index + 1]" :languages="selectedLanguages"
                            :attributes="resultSet.attributes" :meta="WSDataMeta" :resultsPerPage="resultsPerPage"
                            :total="resultSet.total || []"
                            :type="resultSet.type" :corpora="selectedCorpora" />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="dataTabEmpty">
                  The results of your queries will be displayed here.
                </div>

              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <div class="modal fade" id="exportModal" tabindex="-1" aria-labelledby="exportModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="exportModalLabel">{{ $t('common-export-results') }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start">
            <div class="form-floating mb-3">
              <nav>
                <div class="nav nav-tabs justify-content-end" id="nav-export-tab" role="tablist">
                  <button
                    class="nav-link active"
                    id="nav-exportxml-tab"
                    data-bs-toggle="tab"
                    data-bs-target="#nav-exportxml"
                    type="button"
                    role="tab"
                    aria-controls="nav-exportxml"
                    aria-selected="false"
                    @click="(exportTab = 'xml') && setExportFilename('xml')"
                  >
                    XML
                  </button>
                  <button
                    class="nav-link"
                    id="nav-exportswissdox-tab"
                    data-bs-toggle="tab"
                    data-bs-target="#nav-exportswissdox"
                    type="button"
                    role="tab"
                    aria-controls="nav-exportswissdox"
                    aria-selected="false"
                    @click="(exportTab = 'swissdox') && setExportFilename('swissdox')"
                    v-if="selectedCorpora && selectedCorpora.corpus && selectedCorpora.corpus.shortname.match(/swissdox/i)"
                  >
                    SwissdoxViz
                  </button>
                </div>
              </nav>
              <div class="tab-content" id="nav-exportxml-tabContent">
                <div
                  class="tab-pane fade show active pt-3"
                  id="nav-exportxml"
                  role="tabpanel"
                  aria-labelledby="nav-exportxml-tab"
                >
                  <label for="nExport">Number of hits:</label>
                  <input
                    type="text"
                    class="form-control"
                    id="nExport"
                    name="nExport"
                    v-model="nExport"
                  />
                  <label for="nameExport">Filename:</label>
                  <input
                    type="text"
                    class="form-control"
                    id="nameExport"
                    name="nameExport"
                    v-model="nameExport"
                  />
                  <button
                    type="button"
                    @click="exportResults('xml', /*download=*/true, /*preview=*/true)"
                    class="btn btn-primary me-1"
                    data-bs-dismiss="modal"
                  >
                    Download
                  </button>
                </div>
              </div>
              <div class="tab-content" id="nav-exportswissdox-tabContent">
                <div
                  class="tab-pane fade pt-3"
                  id="nav-exportswissdox"
                  role="tabpanel"
                  aria-labelledby="nav-exportswissdox-tab"
                >
                  <label for="nameExport">Filename:</label>
                  <input
                    type="text"
                    class="form-control"
                    id="nameExport"
                    name="nameExport"
                    v-model="nameExport"
                  />
                  <button
                    type="button"
                    @click="exportResults('swissdox', /*download=*/true, /*preview=*/true)"
                    class="btn btn-primary me-1"
                    data-bs-dismiss="modal"
                  >
                    Launch export
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal fade" id="saveQueryModal" tabindex="-1" aria-labelledby="saveQueryModalLabel" aria-hidden="true">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="saveQueryModalLabel">{{ $t('common-save-query') }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start">
            <label for="queryName" class="form-label">{{ $t('common-query-name') }}</label>
            <input type="text" class="form-control" id="queryName" v-model="queryName" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
            <button type="button" :disabled="saveQueryDisabled || !this.queryName" @click="saveQuery" class="btn btn-primary me-1"
              data-bs-dismiss="modal">
              {{ $t('common-save-query') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal fade" id="deleteQueryModal" tabindex="-1" aria-labelledby="deleteQueryModalLabel"
      aria-hidden="true">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="deleteQueryModalLabel">{{ $t('common-delete-query') }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start">
            <p>{{ $t('common-delete-query-sure') }}</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
            <button type="button" @click="deleteQuery" class="btn btn-danger me-1"
              data-bs-dismiss="modal">
              {{ $t('common-delete-query') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal fade" id="corpusGraphModal" tabindex="-1" aria-labelledby="corpusGraphModalLabel"
      aria-hidden="true" ref="vuemodal">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="corpusGraphModallLabel">
              {{ $t('corpus-structure') }}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start" v-if="showGraph == 'modal'">
            <div class="row">
              <p class="title mb-0">{{ selectedCorpora.corpus.meta.name }}</p>
              <CorpusGraphViewNew :corpus="selectedCorpora.corpus" />
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="lcp-progress-bar" :title="$t('common-refresh-progress')" v-if="showLoadingBar">
      <div class="lcp-progress-bar-driver" :style="`width: ${navPercentage}%;`"></div>
    </div>

    <div class="modal fade" id="corpusDetailsModal" tabindex="-1" aria-labelledby="corpusDetailsModalLabel"
      aria-hidden="true" ref="vuemodaldetails">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="corpusDetailsModalLabel">
              {{ $t('platform-general-corpus-details') }}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start" v-if="corpusModal">
            <CorpusDetailsModal :corpusModal="corpusModal" :key="modalIndexKey" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>


  </div>
</template>

<style scoped>
.export {
  float: left;
}
.export[disabled=true] {
  opacity: 0.5;
  cursor: unset;
}
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

.corpus-structure-button {
  display: inline-block;
  float: right;
}

.reverse-items>button#nav-query-tab {
  order: 2;
}

.reverse-items>button#nav-data-tab {
  order: 1;
}
</style>
<style>
#corpus-details-modal div:nth-child(1) {
  width: 100%;
}
#corpus-details-modal div:nth-child(2) {
  display: none;
}
</style>

<script>
import { mapState } from "pinia";
import { Modal } from "bootstrap";
import { nextTick } from 'vue'

import { useCorpusStore } from "@/stores/corpusStore";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import { useWsStore } from "@/stores/wsStore";

import CorpusDetailsModal from "@/components/corpus/DetailsModal.vue";
import Title from "@/components/TitleComponent.vue";
import ResultsTableView from "@/components/results/TableView.vue";
import ResultsKWICView from "@/components/results/KWICView.vue";
import ResultsPlainTableView from "@/components/results/PlainTableView.vue";
import EditorView from "@/components/EditorView.vue";
// import CorpusGraphView from "@/components/CorpusGraphView.vue";
import CorpusGraphViewNew from "@/components/CorpusGraphViewNew.vue";
import PlayerComponent from "@/components/PlayerComponent.vue";
import { setTooltips, removeTooltips } from "@/tooltips";
import Utils from "@/utils";
import config from "@/config";


export default {
  name: "QueryView",
  data() {
    return {
      query: "",
      queryDQD: "",
      textsearch: "",
      cqp: "",
      defaultQueryDQD: "",
      preselectedCorporaId: this.$route.params.id,
      wsConnected: false,
      selectedCorpora: null,
      isQueryValidData: null,
      WSDataResults: "",
      WSDataMeta: {},
      WSDataSentences: {},
      nResults: 200,
      activeResultIndex: 1,
      selectedLanguages: ["en"],
      queryName: "",
      nExport: 200,
      nameExport: "",
      currentTab: "text",
      exportTab: "xml",
      simultaneousMode: false,
      percentageDone: 0,
      percentageTotalDone: 0,
      percentageWordsDone: 0,
      loading: false,
      requestId: "",
      stats: null,
      queryTest: "const noop = () => {}",
      resultsPerPage: 100,
      failedStatus: false,
      plainType: "table",
      sqlQuery: null,
      isDebug: false,
      queryStatus: null,
      // corpusGraph: null,
      corpusModal: null,
      showGraph: '',
      showResultsNotification: false,
      showLoadingBar: false,

      selectedMediaForPlay: null,
      hoveredResult: null,

      selectedQuery: null,
      userQueries: [],

      // selectedDocument: null,
      // documentDict: {},
      // userId: null,
      // corpusData: [],

      activeMainTab: ['soundscript', 'videoscope'].includes(config.appType) ? "data" : "query",
      graphIndex: 0,
      appType: config.appType,
      querySubmitted: false,
      // playerIndex: 0,

      // loadingDocument: false,
      // currentDocumentData: null,
      // currentDocument: null,
      // currentMediaDuration: 0,
      // loadingMedia: false,
      // timelineEntry: null,

      modalIndexKey: 0,
      local: window.location.hostname == "localhost"
    };
  },
  components: {
    Title,
    ResultsKWICView,
    ResultsPlainTableView,
    ResultsTableView,
    EditorView,
    CorpusDetailsModal,
    // CorpusGraphView,
    CorpusGraphViewNew,
    PlayerComponent,
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
            this.defaultQueryDQD = this.getSampleQuery();
            this.queryDQD = this.getSampleQuery();
            this.preselectedCorporaId = null;
            this.showGraph = 'main'
            setTimeout(() => this.graphIndex++, 1)
            this.fetch(); // Retrieve the saved queries
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
    activeMainTab() {
      if (this.activeMainTab == 'query') {
        this.showGraph = 'main'
      }
      else {
        this.showGraph = ''
      }
    },
    selectedCorpora() {
      this.activeMainTab = ['soundscript', 'videoscope'].includes(config.appType) ? "data" : "query"
      this.querySubmitted = false
      this.queryStatus = null
      this.checkAuthUser();
      // let updateGraph = false;
      // if (this.corpusGraph) {
      //   this.corpusGraph = null;
      //   updateGraph = true;
      // }
      // this.validate();
      if (this.selectedCorpora) {
        // this.loadDocuments();
        this.defaultQueryDQD = this.getSampleQuery();
        this.queryDQD = this.getSampleQuery();
        history.pushState(
          {},
          null,
          `/query/${this.selectedCorpora.value}/${this.selectedCorpora.corpus.shortname}`
        );
        // if (updateGraph)
        //   // make sure to delay the re-setting of corpusGraph
        //   setTimeout(() => (this.corpusGraph = this.selectedCorpora.corpus), 1);
        this.showGraph = 'main'
        setTimeout(() => this.graphIndex++, 1)
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
        this.nameExport = "";
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
    currentTab() {
      this.validate();
    },
    query() {
      // console.log("Check is valid")
      if (this.currentTab != "dqd") {
        this.validate();
      }
    },
    textsearch() {
      if (this.currentTab != "text") return;
      this.validate();
    },
    cqp() {
      if (this.currentTab != "cqp") return;
      this.validate();
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
    // currentDocument() {
    //   this.loadDocument();
    // },
  },
  methods: {
    getLanguageName(lg) {
      const cl = this.corpusLanguages.find(v=>v.value.toLowerCase() == lg.toLowerCase());
      if (cl)
        return cl.name;
      return lg;
    },
    getSampleQuery() {
      const corpus = this.selectedCorpora;
      if (!corpus) return "";
      return corpus.corpus.meta.sample_query || corpus.corpus.sample_query || ""
    },
    setExportFilename(format) {
      if (!this.nameExport)
        this.nameExport = `${this.selectedCorpora.corpus.shortname} ${new Date().toLocaleString()}.${format}`;
      else
        this.nameExport = this.nameExport.replace(/\.[^.]+$/,"."+format);
      this.nameExport = this.nameExport.replace(/\/+/g,"-").replace(/,+/g,"");
    },
    setMainTab() {
      this.activeMainTab = 'query'
    },
    setTab(tab) {
      this.selectedQuery = null;
      this.currentTab = tab;
    },
    hoverResultLine(line) {
      this.hoveredResult = line;
    },
    playMedia(data) {
      this.selectedMediaForPlay = data;
    },
    corpusDataType: Utils.corpusDataType,
    showExploreTab() {
      return this.selectedCorpora
        && ['audio', 'video'].includes(Utils.corpusDataType(this.selectedCorpora.corpus))
        && config.appType != "catchphrase"
    },
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
      const allNonActiveResults = Object.entries(this.nKwics)
        .filter(r=>String(r[0])!=String(this.activeResultIndex))
        .reduce((v,s)=>s+(v[1]||[]).length,0);
      const newNResults = allNonActiveResults + this.resultsPerPage * Math.max(currentPage + 1, 3);
      const allActiveResults = Object.values(this.nKwics).reduce((v,s)=>s+(v||[]).length,0);
      console.log(
        "PageUpdate",
        this.nKwics,
        this.activeResultIndex,
        allNonActiveResults,
        newNResults,
        allActiveResults,
        this.WSDataResults.more_data_available
      );
      if (
        newNResults > allActiveResults && this.WSDataSentences && this.WSDataResults.more_data_available
      ) {
        // console.log("Submit");
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
    openCorpusDetailsModal(corpus) {
      this.corpusModal = { ...corpus };
      let modal = new Modal(document.getElementById('corpusDetailsModal'));
      this.modalIndexKey++
      modal.show()
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
      // console.log("R", data)
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
          this.selectedLanguages = this.selectedLanguages.filter(v => this.availableLanguages.includes(v));
          if (this.selectedLanguages == 0) {
            this.selectedLanguages = [this.availableLanguages[0]];
          }
          // console.log("Query validation", data);
          if (data.kind in { dqd: 1, text: 1, cqp: 1 } && data.valid == true)
            this.query = JSON.stringify(data.json, null, 2);
          else
            this.query = "";
          if (data.kind == "cqp" && !data.valid)
            data.error = "Incomplete query or invalid CQP syntax";
          else if (data.error) {
            data.error = (data.error || "").replace(/^Unexpected [^\s]+ [^(]+\('[^']+',\s*('[^']+')\)/, "Unexpected $1");
            data.error = data.error.replace(/\s*Expected one of(.|\n)+$/,"");
          }
          this.isQueryValidData = data;
          return;
        }
        if (data["action"] === "stats") {
          // console.log("stats", data);
          this.stats = data;
          return;
        }

        if (data["action"] === "document") {
          // console.log("DOC", data)
          useWsStore().addMessageForPlayer(data);
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
          if (!data["queries"]) return;

          let queries;
          if (typeof data["queries"] === 'string') {
            try {
              queries = JSON.parse(data["queries"]);
            } catch (e) {
              queries = [];
            }
          } else {
            queries = data["queries"];
          }
          this.userQueries = queries;
          return;
        } else if (data["action"] === "store_query") {
          console.log('store_query', data);

          if (data['status'] === 'success') {
            useNotificationStore().add({
              type: "success",
              text: `Query successfully saved.`
            });
          }

          this.fetch(); // Fetch the updated query list

          return;
        } else if (data["action"] == "delete_query") {
          this.selectedQuery = null;
          this.fetch(); // Fetch the updated query list

          return;
        } else if (data["action"] == "export_complete") {
          const info = {
            hash: data.hash,
            format: data.format,
            offset: data.offset || 0,
            requested: data.total_results_requested || 200
          };
          useCorpusStore().fetchExport(info);
        } else if (data["action"] === "document_ids") {
          useWsStore().addMessageForPlayer(data)
          return;
        } else if (data["action"] === "stopped") {
          if (data.request) {
            console.log("queries stopped", data);
            useNotificationStore().add({
              type: "success",
              text: "Query stopped",
            });
            this.loading = false;
            if (this.requestId == data.request)
              this.requestId = null;
          }
          return;
        } else if (data["action"] == "started_export") {
          this.loading = false;
          if (this.requestId == data.request)
            this.requestId = null;
        } else if (data["action"] === "query_result") {
          useWsStore().addMessageForPlayer(data)
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
          for (let p of [
            "batches_done",
            "total_results_so_far",
            "projected_results",
            "more_data_available",
            "percentage_done",
            "percentage_words_done"
          ]) {
            if (parseInt(data.batches_done||0) < parseInt(this.WSDataResults.batches_done||0))
              break;
            this.WSDataResults[p] = data[p];
          }
          this.percentageDone = this.WSDataResults.percentage_done || 0;
          this.percentageWordsDone = this.WSDataResults.percentage_words_done || 0;
          if (!this.WSDataResults.result)
            return this.WSDataResults.result = data.result;
          const kwic_keys = ((data.result[0]||{}).result_sets||[]).map((rs,n)=>rs.type=="plain"?n+1:-1).filter(n=>n>0);
          for (let rkey in data.result) {
            if (!kwic_keys.includes(parseInt(rkey))) {
              this.WSDataResults.result[rkey] = data.result[rkey];
              continue;
            }
            this.WSDataResults.result[rkey] = [
              ...(this.WSDataResults.result[rkey]||[]),
              ...data.result[rkey]
            ];
          }
          return;
        } else if (data["action"] === "segments") {
          useWsStore().addMessageForPlayer(data);
          this.updateLoading(data.status);
          const segment = this.selectedCorpora.corpus.firstClass.segment;
          const meta = data.result["-2"] || []; // change this?
          const meta_labels = ((data.result["0"] || {}).meta_labels || [])
            .map( ml => [ml.split("_")[0],ml.split("_").slice(1,).join("_")] );
          for (let hit_meta of meta) {
            let segment_id = "";
            const meta_object = {};
            for (let n in hit_meta) {
              let value = hit_meta[n];
              const [layer, attr] = meta_labels[n];
              if (layer == segment && attr == "id")
                segment_id = value;
              meta_object[layer] = meta_object[layer] || {};
              if (attr.endsWith("_range") && value) {
                const ranges = value.match(/\[(\d+),(\d+)\)/);
                if (ranges)
                  value = [parseInt(ranges[1]),parseInt(ranges[2])];
              }
              if (typeof(value) == "string")
                value = value.trim();
              meta_object[layer][attr] = value;
            }
            this.WSDataMeta[segment_id] = meta_object;
          }
          if (
            this.WSDataSentences &&
            this.WSDataSentences.hash == data.hash &&
            !data.full
          ) {
            Object.keys(this.WSDataSentences.result).forEach((key) => {
              if (key > 0 && key in data.result) {
                this.WSDataSentences.result[key] = this.WSDataSentences.result[
                  key
                ].concat(data.result[key]);
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
                this.WSDataResults.result["0"] = { result_sets: [] };
              this.WSDataResults.result["0"].result_sets.forEach(
                (_resultSet, index) => {
                  if (_resultSet.type == "plain") {
                    let resultIndex = index + 1;
                    if (!(resultIndex in this.WSDataSentences.result))
                      this.WSDataSentences.result[resultIndex] = [];
                  }
                }
              );
            }
          }
          // if (["satisfied", "overtime"].includes(this.WSDataResults.status)) {
          //   this.loading = false;
          // }
          return;
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
    openGraphInModal() {
      this.$refs.vuemodal.addEventListener("shown.bs.modal", () => {
        this.showGraph = 'modal';
      });
      this.$refs.vuemodal.addEventListener("hide.bs.modal", () => {
        this.showGraph = 'main';
        // if (restoreSmallGraphWith) this.corpusGraph = restoreSmallGraphWith;
        // restoreSmallGraphWith = null;
      });
    },
    resizeGraph(container) {
      let svg = container.querySelector("svg");
      if (svg === null) return;
      let g = svg.querySelector("g");
      if (g === null) return;
      svg.style.height = `${g.getBoundingClientRect().height}px`;
    },
    async exportResults(format, download = false, preview = false) {
      const to_export = {};
      to_export.format = {
        'plain': 'dump',
        'swissdox': 'swissdox',
        'xml': 'xml'
      }[format];
      to_export.preview = preview;
      to_export.download = download;
      this.setExportFilename(format);
      to_export.filename = this.nameExport;
      let full = !preview;
      let resume = full; // If not a full query, no need to resume the query: we already have the necessary results
      if (format == 'swissdox') {
        resume = false;
        full = true;
      }
      this.submit(null, /*resumeQuery=*/resume, /*cleanResults=*/false, /*full=*/full, /*to_export=*/to_export);
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
      if (this.isSubmitDisabled || !this.currentQuery || !this.query)
        return;
      if (!localStorage.getItem("dontShowResultsNotif"))
        this.showResultsNotification = true;
      if (!to_export && resumeQuery == false) {
        this.failedStatus = false;
        this.stop();
        if (cleanResults == true) {
          this.WSDataResults = {};
          this.WSDataSentences = {};
        }
      }
      let data = {
        corpus: this.selectedCorpora.value,
        query: this.query,
        user: this.userData.user.id,
        room: this.roomId,
        languages: this.selectedLanguages,
        requested: this.resultsPerPage * (resumeQuery ? 1 : 3),
        offset: resumeQuery ? Object.values(this.nKwics).reduce((v,s)=>s+(v||[]).length,0) : 0
      };
      if (fullSearch) {
        data["full"] = true;
      }
      if (to_export) {
        data["to_export"] = to_export;
        data["requested"] = Math.max(this.nExport, 1);
      }
      console.log("submitting with total results requested", data["total_results_requested"]);
      let retval = await useCorpusStore().fetchQuery(data);
      if (retval.status == "started") {
        this.loading = true;
        this.percentageDone = 0.001;
        this.percentageWordsDone = 0;
        this.requestId = retval.request;
      }

      // console.log(document.querySelector("button#nav-results-tab"))
      this.querySubmitted = true
      this.activeMainTab = 'data'
      nextTick(() => {
        const section = document.getElementById("results");
        if (section) {
          section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
      // .tab("show")
    },
    resume() {
      this.submit(null, true);
    },
    stop() {
      this.percentageDone = 0;
      this.percentageTotalDone = 0;
      this.failedStatus = false;
      this.loading = false;
      if (!this.requestId)
        return;
      useWsStore().sendWSMessage({
        action: "stop",
        request: this.requestId
      });
    },
    enough(job) {
      useWsStore().sendWSMessage({
        action: "enough_results",
        job: job,
      });
    },
    validate() {
      const query = this.currentQuery;
      if (!query || query.match(/^(\s|\n)+$/)) {
        this.isQueryValidData = {valid: true};
        return;
      }
      useWsStore().sendWSMessage({
        action: "validate",
        query: query,
        kind: this.currentTab,
        corpus: this.selectedCorpora.value
      });
    },
    userQueryVisible() {
      if (this.currentTab == "text" || this.currentTab == "dqd" || this.currentTab == "cqp") {
        return true;
      }

      return false;
    },
    saveQuery() {
      let data = {
        // corpora: this.selectedCorpora.map((corpus) => corpus.value),
        corpora: this.selectedCorpora.value,
        query: this.currentQuery,
        user: this.userData.user.id,
        room: this.roomId,
        // room: null,
        page_size: this.resultsPerPage,
        languages: this.selectedLanguages,
        total_results_requested: this.nResults,
        query_name: this.queryName,
        query_type: this.currentTab,
      };

      console.log('data', JSON.stringify(data));

      this.queryName = "";
      useCorpusStore().saveQuery(data);
    },
    deleteQuery() {
      if (!this.selectedQuery) return;
      useCorpusStore().deleteQuery(this.userData.user.id, this.roomId, this.selectedQuery.idx);
    },
    fetch() {
      let data = {
        user: this.userData.user.id,
        room: this.roomId,
        // query_type: this.currentTab,
        // room: null,
      };
      useCorpusStore().fetchQueries(data);
    },
    handleQuerySelection(selectedQuery) {
      if (this.currentTab == "text") {
        this.textsearch = selectedQuery.query.query;
      }
      else if (this.currentTab == "dqd") {
        this.queryDQD = selectedQuery.query.query;
        this.defaultQueryDQD = selectedQuery.query.query;
        this.updateQueryDQD(selectedQuery.query.query);
      }
      else if (this.currentTab == "cqp") {
        this.cqp = selectedQuery.query.query;
      }
      return;
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
    ...mapState(useCorpusStore, {corpusLanguages: "languages"}),
    ...mapState(useUserStore, ["userData", "roomId", "debug"]),
    ...mapState(useWsStore, ["messages"]),
    availableLanguages() {
      let retval = [];
      if (this.selectedCorpora) {
        const corpus = this.corpora.find((c) => c.meta.id == this.selectedCorpora.value);
        if (corpus) {
          retval = Object.keys(corpus.layer)
            .filter((key) => key.startsWith("Token@") || key.startsWith("Token:"))
            .map((key) => key.replace(/Token[@:]/, ""));
          if (retval.length == 0)
            retval = [corpus.meta.language || "en"];
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
    processedSavedQueries() {
      if (!this.userQueries) return [];

      return this.userQueries.map((q) => ({
        ...q,
        query_name: q.query?.query_name || "",
      })).filter((q) => q.query?.query_type === this.currentTab);
    },
    nKwics() {
      const kwic_keys = ((this.WSDataResults.result[0]||{}).result_sets||[])
        .map((rs,n)=>rs.type=="plain"?n+1:-1)
        .filter(n=>n>0);
      return Object.fromEntries(
        Object.entries(this.WSDataResults.result)
          .filter(r=>kwic_keys.includes(parseInt(r[0])))
          .map(([rkey,results])=>[rkey,results.length])
      );
    },
    currentQuery() {
      let query = this.query;
      if (this.currentTab == "text")
        query = this.textsearch;
      if (this.currentTab == "dqd")
        query = this.queryDQD + "\n";
      if (this.currentTab == "cqp")
        query = this.cqp;
      return query;
    },
    saveQueryDisabled() {
       return !this.currentQuery || this.currentQuery.match(/^\s*$/);
    },
    dataTabEmpty() {
      if (this.selectedCorpora && this.showExploreTab())
        return false;
      if (this.querySubmitted)
        return false;
      if (this.loading)
        return false;
      if (this.showResultsNotification && this.queryStatus == "satisfied")
        return false;
      if (this.percentageDone == 100)
        return false;
      return true;
    },
    isSubmitDisabled() {
      return (this.selectedCorpora && this.selectedCorpora.length == 0) ||
        this.loading === true ||
        (this.isQueryValidData != null && this.isQueryValidData.valid == false) ||
        !this.query ||
        !this.selectedLanguages
    },
    noResults() {
      const dr = JSON.parse(JSON.stringify(this.WSDataResults)) || {};
      const ds = JSON.parse(JSON.stringify(this.WSDataSentences)) || {};
      dr.result = dr.result || {};
      ds.result = ds.result || {};
      console.log("dr", dr, "ds", ds);
      return [dr,ds].every(d=>Object.entries(d.result).every(([k,v])=>k==0 || !v || v.length==0));
    }
  },
  mounted() {
    // this.userId = this.userData.user.id;
    setTooltips();
  },
  beforeUnmount() {
    removeTooltips();
  },
};
</script>
