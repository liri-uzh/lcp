<template>
  <div class="home">
    <div class="container">
      <div class="row mt-4">
        <div class="col">
          <Title title="User profile" />
        </div>
      </div>
      <div class="row my-5 border-secondary" v-if="userData && userData.user">
        <h4>{{ $t('common-user-info') }}</h4>
        <p class="my-1" v-if="userData.user.email">
            {{ $t('common-name') }}: <strong>{{ userData.user.displayName}}</strong>
        </p>
        <p class="my-1" v-if="userData.user.email">
          {{ $t('common-email') }}: <strong>{{ userData.user.email }}</strong>
        </p>
        <p class="my-1" v-if="userData.user.homeOrganization">
          {{ $t('common-organization') }}: <strong>{{ userData.user.homeOrganization }}</strong>
        </p>
      </div>
      <div class="row my-5">
        <h4>{{ $t('common-saved-queries') }}</h4>
        <p>
          {{ $t('platform-user-saved-query-description') }}
        </p>
        <div class="form-floating mb-3">
          <div class="tab-content" id="nav-main-tabContent">
            <div class="row">
              <div class="col-lg-6">
                <div class="m-3">
                  <div class="container-fluid" v-if="userQueryVisible()">
                    <multiselect
                      v-model="selectedQuery"
                      :options="processedSavedQueries"
                      :searchable="true"
                      :clear-on-select="false"
                      :close-on-select="true"
                      :placeholder="$t('common-select-saved-queries')"
                      label="query_name"
                      track-by="idx"
                      @select="handleQuerySelection"
                    ></multiselect>
                  </div>
                </div>
                <div class="form-floating mb-3" v-if="selectedQuery">
                  <nav>
                    <div class="nav nav-tabs justify-content-end" id="nav-query-tab" role="tablist">
                      <button class="nav-link" id="nav-plaintext-tab" data-bs-toggle="tab"
                        data-bs-target="#nav-plaintext" type="button" role="tab" aria-controls="nav-plaintext"
                        aria-selected="false" @click="setTab('text')">
                        {{ $t('common-text') }}
                      </button>
                      <button class="nav-link active" id="nav-dqd-tab" data-bs-toggle="tab" data-bs-target="#nav-dqd"
                        type="button" role="tab" aria-controls="nav-dqd" aria-selected="true" @click="setTab('dqd')">
                        DQD
                      </button>
                      <button class="nav-link" id="nav-cqp-tab" data-bs-toggle="tab" data-bs-target="#nav-cqp"
                        type="button" role="tab" aria-controls="nav-cqp" aria-selected="false" @click="setTab('cqp')">
                        CQP
                      </button>
                    </div>
                  </nav>
                  <div class="tab-content" id="nav-query-tabContent">
                    <div class="tab-pane fade pt-3" id="nav-plaintext" role="tabpanel"
                      aria-labelledby="nav-plaintext-tab">
                      <input readonly class="form-control" type="text" placeholder="Query (e.g. a cat)" :class="isQueryValidData == null || isQueryValidData.valid == true
                        ? 'ok'
                        : 'error'
                        " v-model="textsearch" />
                      <!-- <label for="floatingTextarea">Query</label> -->
                      <p class="error-text text-danger" v-if="isQueryValidData && isQueryValidData.valid != true">
                        {{ isQueryValidData.error }}
                      </p>
                    </div>
                    <div class="tab-pane fade show active pt-3" id="nav-dqd" role="tabpanel"
                      aria-labelledby="nav-results-tab">
                      <ReadonlyEditorView :query="queryDQD" :defaultQuery="defaultQueryDQD" :invalidError="isQueryValidData && isQueryValidData.valid != true
                        ? isQueryValidData.error
                        : null
                        " @update="updateQueryDQD" />
                      <p class="error-text text-danger mt-3" v-if="
                        isQueryValidData && isQueryValidData.valid != true && debug
                      ">
                        {{ isQueryValidData.error }}
                      </p>
                    </div>
                    <div class="tab-pane fade pt-3" id="nav-cqp" role="tabpanel" aria-labelledby="nav-cqp-tab">
                      <textarea readonly class="form-control query-field"
                        :placeholder="processedSavedQueries?.length > 0 ? $t('common-select-saved-queries-dropdown') : $t('common-select-no-saved-queries')"
                        :class="isQueryValidData == null || isQueryValidData.valid == true
                          ? 'ok'
                          : 'error'
                          " v-model="cqp" @keyup="$event.key == 'Enter' && $event.ctrlKey && this.submit()"></textarea>
                      <!-- <label for="floatingTextarea">Query</label> -->
                      <p class="error-text text-danger" v-if="isQueryValidData && isQueryValidData.valid != true">
                        {{ isQueryValidData.error }}
                      </p>
                    </div>
                  </div>
                </div>
                <div class="mt-3">
                  <div class="d-flex container-fluid justify-content-end">
                    <button type="button"
                      v-if="!loading && userData.user.anon != true && userQueryVisible() && selectedQuery"
                      :disabled="(isQueryValidData && isQueryValidData.valid != true)" class="btn btn-danger me-1 mb-1"
                      data-bs-toggle="modal" data-bs-target="#deleteQueryModal">
                      <FontAwesomeIcon :icon="['fas', 'trash']" />
                      {{ $t('common-delete-query') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="modal fade" id="editQueryModal" tabindex="-1" aria-labelledby="editQueryModalLabel" aria-hidden="true">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="editQueryModalLabel">Rename query</h5>
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
          <button type="button" :disabled="!queryName" @click="saveQuery" class="btn btn-primary me-1"
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
          <button type="button" :disabled="!queryName" @click="deleteQuery" class="btn btn-danger me-1"
            data-bs-dismiss="modal">
            {{ $t('common-delete-query') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped></style>

<script>
import { mapState } from "pinia";

// Components
import Title from "@/components/TitleComponent.vue";
import ReadonlyEditorView from "@/components/ReadonlyEditorView.vue";

// Stores
import { useUserStore } from "@/stores/userStore";
import { useCorpusStore } from "@/stores/corpusStore";
import { useWsStore } from "@/stores/wsStore";

export default {
  name: "UserView",
  data() {
    return {
      currentTab: "dqd",
      selectedCorpora: null,
      selectedLanguages: ["en"],
      loading: false,

      userQueries: [],
      wsConnected: false,
      WSDataResults: "",
      WSDataMeta: {},
      WSDataSentences: "",

      query: "",
      queryDQD: "",
      textsearch: "",
      cqp: "",
      defaultQueryDQD: "",
      queryName: "",

      isQueryValidData: null,

      selectedQuery: null,
    };
  },
  components: {
    Title,
    ReadonlyEditorView
  },
  watch: {
    userData() {
      useWsStore().connectToRoom(this.$socket, this.userData.user.id, this.roomId)
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
    currentTab() {
      // this.validate();
    },
  },
  methods: {
    setTab(tab) {
      this.selectedQuery = null;
      this.textsearch = "";
      this.query = "";
      this.queryDQD = "";
      this.defaultQueryDQD = "";
      this.updateQueryDQD('');

      this.currentTab = tab;
    },
    onSocketMessage(data) {
      if (Object.prototype.hasOwnProperty.call(data, "action")) {
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
        }

        if (data["action"] === "delete_query") {
          this.selectedQuery = null;
          this.fetch(); // Fetch the updated query list

          return;
        }
      }
    },
    fetch() {
      let data = {
        user: this.userData.user.id,
        room: this.roomId,
      };
      useCorpusStore().fetchQueries(data);
    },
    deleteQuery() {
      if (!this.selectedQuery) return;
      useCorpusStore().deleteQuery(this.userData.user.id, this.roomId, this.selectedQuery.idx);
    },
    userQueryVisible() {
      if (this.currentTab == "text" || this.currentTab == "dqd" || this.currentTab == "cqp") {
        return true;
      }

      return false;
    },
    updateQueryDQD(queryDQD) {
      if (this.loading)
        this.loading = "resubmit";
      this.queryDQD = queryDQD;
      // this.validate();
    },
    handleQuerySelection(selectedQuery) {
      if (!selectedQuery) return;

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

      this.queryName = selectedQuery.query.query_name;

      return;
    },
  },
  computed: {
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
    processedSavedQueries() {
      if (!this.userQueries) return [];

      return this.userQueries.map((q) => ({
        ...q,
        query_name: q.query?.query_name || "",
      })).filter((q) => q.query?.query_type === this.currentTab);
    },
  },
  mounted() {
    useUserStore().fetchUserData().then(async () => {
      this.fetch(); // Fetch the queries once we get the user data
    });
  },
};
</script>
