<template>
  <div class="home">
    <div class="container">
      <!-- <div class="row mt-4">
        <div class="col">
          <Title :title="appName" :isItalic="appType == 'lcp' ? false : true" />
        </div>
      </div> -->
      <div class="row mt-3">
        <div class="col">
          <div class="input-group mb-3">
            <!-- Include: Text | Sound | Video (once we have a single instance) -->
            <input type="text" class="form-control" v-model="corporaFilter" :placeholder="$t('platform-general-find-corpora')" />
          </div>
          <div v-if="corporaFilter && filterError && filterError.message" class="alert notification alert-danger">
            {{ filterError.message }}
          </div>
          <div id="languages-filter" v-if="allLanguages">
            <span>Languages:</span>
            <span
              v-for="language in allLanguages"
              :key="language.langCode"
              class="language-filter"
            >
              <input
                type="checkbox"
                :id="`language-filter-${language.langCode}`"
                :value="language.langCode"
                v-model="languageFilter"
              />
              <label
                :for="`language-filter-${language.langCode}`"
                :title="language.langName"
                class="tooltips"
              >
                {{ language.langCode }}
              </label>
            </span>
          </div>
        </div>
      </div>
    </div>
    <div class="container mt-4 text-start">
      <div class="row">
        <div class="tab-content pt-3" id="nav-tabContent" ref="projects">
          <div
            v-for="project in projectsGroups"
            :key="project.id"
            :id="`project-${project.id}`"
            class="tab-pane fade active show"
            :style="`order: ${filterCorpora(project.corpora).length == 0 ? 2 : 1}`"
            @pointerenter="currentProject=project"
            @wheel="e=>wheelScroll(e, project.id)"
          >
            <div class="project-header">
              <span
                class="project-name"
                :class="project.corpora.length == 0 ? 'no-corpora' : ''"
                type="button"
              >
                <FontAwesomeIcon
                  :icon="projectIcons(project)"
                  class="me-1 tooltips"
                  :title="project.isPublic ? 'Public collection' : (project.isSemiPublic ? 'Log-in required' : 'Private collection')"
                />
                <strong>{{ project.title }}</strong>
                <span class="api-badge"> ({{ project.corpora.length }})</span>
              </span>
              <div class="project-details">
                <div
                  class="project-description tooltips"
                  :title="project.description"
                  :style="project.isAdmin ? '' : 'max-width: 90%;'"
                  v-if="project.description"
                >
                  {{ project.description }}
                </div>
                <div class="project-admin" v-if="project.isAdmin">
                  <div>
                    {{ formatDate(project.startDate, "DD.MM.YYYY") || 'ever' }} > {{ formatDate(project.finishDate, "DD.MM.YYYY") || 'ever' }}
                  </div>
                  <div>
                    {{ project.institution }}
                  </div>
                  <div>
                    <FontAwesomeIcon :icon="['fas', project.api ? 'check' : 'ban']" />
                    API
                  </div>
                </div>
              </div>
              <div class="project-settings" v-if="project.isAdmin">
                <button
                  type="button"
                  class="btn btn-sm btn-light"
                  data-bs-toggle="modal"
                  data-bs-target="#editProjectModal"
                  @click="[modalIndexKey++,currentProject=project]"
                >
                  <FontAwesomeIcon :icon="['fas', 'gear']" />
                </button>
              </div>
            </div>
            <div
              class="scroller-left"
              :style="project.id in overflowingLeft ? '' : 'display: none;'"
              @pointerdown="scrollProject(project.id, 'left')"
            >
              &lt;
            </div>
            <div
              class="scroller-right"
              :style="project.id in overflowingRight ? '' : 'display: none;'"
              @pointerdown="scrollProject(project.id, 'right')"
            >
              &gt;
            </div>
            <div class="corpora-container" :style="corporaContainer(filterCorpora(project.corpora))" @pointerdown="e=>dragScrollProjects(e,project.id)">
              <div
                v-for="corpus in filterCorpora(project.corpora)"
                :key="corpus.id"
                @click.stop="openQueryWithCorpus(corpus)"
              >
                <div class="corpus-block" :class="`data-type-${corpusDataType(corpus)}`">
                  <div class="corpus-block-header px-4 py-3">
                    <p class="title mb-0">
                      {{ corpus.meta.name }}
                      <span
                        class="badge revision text-bg-primary me-1 tooltips"
                        :title="`${$t('common-revision')}: ${corpus.meta.revision}`"
                        v-if="corpus.meta.revision"
                      >r.{{ corpus.meta.revision }}</span>
                    </p>
                    <!-- <p class="author mb-0">
                      <span v-if="corpus.meta.author">by {{ corpus.meta.author }}</span>
                    </p> -->
                    <button
                      v-if="project.isAdmin"
                      class="tooltips icon-x btn btn-sm btn-light"
                      :title="$t('platform-general-corpus-edit')"
                      @click.stop="openCorpusEdit(corpus)"
                    >
                      <FontAwesomeIcon :icon="['fas', 'gear']" />
                    </button>
                  </div>
                  <div class="px-4">
                    <p class="description mt-3">
                      {{ corpus.meta.corpusDescription }}
                    </p>
                    <p class="word-count">
                      <!-- These are listed in reverse (flex-direction: row-reverse) -->
                      <span class="badge text-bg-primary me-1 tooltips" :title="$t('common-word-count')"
                      >{{
                        nFormatter(
                          calculateSum(Object.entries(corpus.token_counts).filter(kv=>kv[0].endsWith("0")).map(kv=>kv[1]))
                        )
                      }}</span>
                      <template v-if="corpus.partitions">
                        <span
                          class="badge text-bg-primary me-1 tooltips language" :title="corpus.partitions.values.map(l=>this.getLanguage(l)).reverse().join(', ')"
                          v-for="language in corpus.partitions.values"
                          v-html="language.toUpperCase()" :key="`${corpus.id}-${language}`"
                        ></span>
                      </template>
                      <span
                        class="badge text-bg-primary me-1 tooltips language" :title="this.getLanguage(corpus.meta.language)"
                        v-else-if="corpus.meta.language"
                        v-html="corpus.meta.language.toUpperCase()"
                      ></span>
                    </p>
                  </div>
                  <div class="details-button icon-2">
                    <span
                      :href="corpusStore.getLicenseByTag(corpus.meta.license)"
                      class="tooltips icon-x"
                      target="_blank"
                      :title="$t('platform-general-user-license')"
                      @click.stop="openCorpusDetailsModal(corpus)"
                      v-if="corpus.meta.license == 'user-defined'"
                    >
                      <FontAwesomeIcon :icon="['fas', 'certificate']" />
                    </span>
                    <a
                      :href="corpusStore.getLicenseByTag(corpus.meta.license).url"
                      target="_blank"
                      class="tooltips icon-x"
                      v-else-if="corpus.meta.license"
                      :title="`${$t('platform-general-corpus-license')}: ${corpus.meta.license}`"
                    >
                      <FontAwesomeIcon :icon="['fas', 'certificate']" />
                    </a>
                    <span class="tooltips icon-x" :title="$t('platform-general-corpus-details')" @click.stop="openCorpusDetailsModal(corpus)">
                      <FontAwesomeIcon :icon="['fas', 'circle-info']" />
                    </span>
                  </div>
                  <div class="details-data-type icon-3 tooltips" :title="$t('platform-general-data-type')" v-if="appType == 'lcp'">
                    <FontAwesomeIcon :icon="['fas', 'music']" v-if="corpusDataType(corpus) == 'audio'" />
                    <FontAwesomeIcon :icon="['fas', 'video']" v-else-if="corpusDataType(corpus) == 'video'" />
                    <FontAwesomeIcon :icon="['fas', 'font']" v-else />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div id="new-collection" class="col mt-1 text-end" v-if="userData && userData.user && userData.user.displayName">
      <button
        type="button"
        class="btn btn-secondary btn-sm tooltips"
        :title="$t('common-add-group')"
        data-bs-toggle="modal"
        data-bs-target="#newProjectModal"
        @click="modalIndexKey++"
      >
        <FontAwesomeIcon :icon="['fas', 'circle-plus']" class="me-1" />
      </button>
    </div>

    <!-- Modals -->
    <div class="modal fade" id="newProjectModal" tabindex="-1" aria-labelledby="newProjectModalLabel" aria-hidden="true"
      ref="vuemodal">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="newProjectModalLabel">{{ $t('modal-project-new') }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start">
            <ProjectNewView @updated="updateProjectModalData" :key="modalIndexKey" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="saveModalProject"
              :disabled="!allowProjectModalSave">
              {{ $t('common-save') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" id="corpusDetailsModal" tabindex="-1" aria-labelledby="corpusDetailsModalLabel"
      aria-hidden="true" ref="vuemodaldetails">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="corpusDetailsModalLabel">
              {{ $t('platform-general-corpus-details') }}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start" v-if="corpusDetailsModal">
            <CorpusDetailsModal :corpusModal="corpusDetailsModal" :key="modalIndexKey" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" id="corpusEditModal" tabindex="-1" aria-labelledby="corpusEditModalLabel"
      aria-hidden="true" ref="vuemodal">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="corpusEditModalLabel" v-if="corpusModal">
              {{ $t('platform-general-corpus-settings') }} - <em>{{ corpusModal.meta.name }}</em>
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start fit-body" v-if="corpusModal">
            <MetadataEdit
              :corpus="corpusModal"
              :key="modalIndexKey"
              @submitSWISSUbase="submitModalSWISSUbase"
              :allProjects="getUniqueProjects"
              ref="metadataedit"
             />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="saveModalCorpus">
              {{ $t('common-save') }}
            </button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" id="editProjectModal" tabindex="-1" aria-labelledby="projectEditModalLabel"
      aria-hidden="true" ref="vuemodal">
      <div class="modal-dialog modal-xl">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="projectEditModalLabel">
              <b v-if="currentProject">{{ currentProject.title }}</b> {{ $t('common-group-settings').toLowerCase() }}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start" v-if="currentProject && currentProject.id">
            <ProjectEdit :project="currentProject" :key="modalIndexKey" @updated="updateProjectModalData" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="saveModalEditProject" :disabled="!allowProjectModalSave">
              {{ $t('common-save') }}
            </button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from "pinia";
import { useCorpusStore } from "@/stores/corpusStore";
import { useSWISSUbaseStore } from "@/stores/swissubaseStore";
import { useProjectStore } from "@/stores/projectStore";
import { useUserStore } from "@/stores/userStore";
import { useNotificationStore } from "@/stores/notificationStore";

// import Title from "@/components/TitleComponent.vue";
import ProjectNewView from "@/components/project/NewView.vue";
import CorpusDetailsModal from "@/components/corpus/DetailsModal.vue";
import MetadataEdit from "@/components/corpus/MetadataEdit.vue";
import ProjectEdit from "@/components/project/EditView.vue";
import router from "@/router";
import Utils from "@/utils";
import config from "@/config";
import { setTooltips, removeTooltips } from "@/tooltips";
import { Modal } from "bootstrap";

export default {
  name: "HomeView",
  data() {
    return {
      corpusModal: null,
      corpusDetailsModal: null,
      allowProjectModalSave: false,
      modalProjectData: null,
      appName: config.appName,
      appType: config.appType,
      // tooltips: [],
      corporaFilter: "",
      showLanguageFilters: true,
      languageFilter: null,
      currentProject: null,
      filterError: null,
      currentEditTab: "metadata",
      inviteEmails: '',
      currentProjectToSubmit: null,
      modalIndexKey: 0,
      corpusStore: useCorpusStore(),
      overflowingLeft: {},
      overflowingRight: {},
      scrollProjectTimeout: null,
      resizeObserver: new ResizeObserver((entries) => entries.forEach(e=>{
        const cc = e.target.querySelector(".corpora-container");
        if (!cc) return;
        cc.style.marginLeft = 0;
        this.updateOverflows();
      })),
      dragScrolling: []
    };
  },
  components: {
    // Title,
    ProjectNewView,
    CorpusDetailsModal,
    MetadataEdit,
    ProjectEdit,
  },
  methods: {
    corpusOverflow(projectId, where) {
      const projectRef = this.$refs.projects;
      if (!projectRef) return false;
      const projectNode = projectRef.querySelector(`#project-${projectId}`);
      if (!projectNode) return false;
      const corporaNode = projectNode.querySelector(".corpora-container");
      if (!corporaNode) return false;
      const projectEdge = projectNode.getBoundingClientRect()[where];
      return [...corporaNode.children].find(c=>(where == "left" ? -1 : 1) * (c.getBoundingClientRect()[where] - projectEdge) > 0);
    },
    corporaContainer(corpora) {
      let ret = "";
      const projectsWithCorpora = this.projectsGroups.filter(p=>this.filterCorpora(p.corpora).length>0);
      if (projectsWithCorpora.length < 2) {
        if (this.projectsGroups.length == 1)
          ret = "height: unset; flex-flow: row wrap;";
        else
          ret = "height: calc(100vh - 300px); flex-flow: row wrap;"
      }
      if (projectsWithCorpora.length > 2)
        ret = "height: 250px";
      if (corpora.length == 0)
        ret = "height: 0px;"
      return ret;
    },
    dragScrollProjects(event, projectId) {
      this.dragScrolling = [event.clientx, projectId];
    },
    wheelScroll(event, projectId) {
      if (!event.deltaX && !event.shiftKey) return;
      const d = event.shiftKey ? event.deltaY : event.deltaX;
      this.scrollProject(projectId, d > 0 ? "right" : "left");
      this.scrollProjectTimeout = clearTimeout(this.scrollProjectTimeout);
      event.stopPropagation();
      event.preventDefault();
    },
    switchLanguageFilter() {
      this.showLanguageFilters = !this.showLanguageFilters;
      if (this.languageFilter instanceof Array) return;
      this.languageFilter = this.allLanguages.map(l=>l.langCode);
    },
    hasAccessToCorpus: Utils.hasAccessToCorpus,
    getLanguage(lg) {
      if (!lg) return "Undefined";
      const cl = this.corpusLanguages.find(v=>v.value.toLowerCase() == lg.toLowerCase());
      if (cl)
        return cl.name;
      return lg;
    },
    projectIcons(project) {
      let icons = ['fas']
      if (project.isPublic == true || project.isSemiPublic == true) {
        icons.push('globe')
      }
      else if (project.isAdmin) {
        icons.push('user-gear')
      }
      else {
        icons.push('users')
      }
      return icons
    },
    filterCorpora(corpora) {
      if (this.corporaFilter) {
        let rgx = null;
        // use a try/catch statement to test the regex
        try { rgx = new RegExp(this.corporaFilter, "i"); }
        catch (e) {
          if (!this.filterError || this.filterError.pattern != this.corporaFilter) {
            this.filterError = { pattern: this.corporaFilter };
            setTimeout(() => {
              if (!this.filterError) return;
              this.filterError.message = `Invalid search pattern (${e.message})`;
            }, 1000); // allow 1s for the user to correct/complete the pattern
          }
        }
        if (rgx) {
          corpora = corpora.filter(
            (c) =>
              c.meta.name.search(rgx) > -1 ||
              c.meta.authors.search(rgx) > -1
          );
          this.filterError = null;
        }
      }
      if (this.languageFilter instanceof Array)
        corpora = corpora.filter(c=>
          this.languageFilter.includes(c.meta.language) ||
          (c.partitions && c.partitions.values.some(p=>this.languageFilter.includes(p))) ||
          (!c.meta.language && this.languageFilter.includes("und"))
        );

      function compare(a, b) {
        if (a.meta.name < b.meta.name) {
          return -1;
        }
        if (a.meta.name > b.meta.name) {
          return 1;
        }
        return 0;
      }
      corpora = corpora.sort(compare)
      return corpora;
    },
    openCorpusDetailsModal(corpus) {
      this.corpusDetailsModal = { ...corpus };
      let modal = new Modal(document.getElementById('corpusDetailsModal'));
      this.modalIndexKey++
      modal.show()
    },
    openCorpusEdit(corpus) {
      this.corpusModal = { ...corpus };
      // let tab = Tab.getInstance(this.$refs);
      this.modalIndexKey++
      let modal = new Modal(document.getElementById('corpusEditModal'));
      modal.show();
    },
    openQueryWithCorpus(corpus) {
      if (this.scrollProjectTimeout) return;
      if (this.hasAccessToCorpus(corpus, this.userData)) {
        if (config.appType == "videoscope") {
          router.push(`/query/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`);
        } else {
          router.push(`/query/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`);
        }
      }
    },
    calculateSum(array) {
      return array.reduce((accumulator, value) => {
        return accumulator + value;
      }, 0);
    },
    nFormatter: Utils.nFormatter,
    formatDate: Utils.formatDate,
    getURLWithProtocol: Utils.getURLWithProtocol,
    updateProjectModalData(valid, data) {
      this.allowProjectModalSave = valid;
      this.modalProjectData = data;
    },
    async saveModalProject() {
      let retval = await useProjectStore().create(this.modalProjectData);
      if (retval) {
        if (retval.status == false) {
          useNotificationStore().add({
            type: "error",
            text: retval.msg,
          });
        }
        else {
          useUserStore().fetchUserData();
          useNotificationStore().add({
            type: "success",
            text: `The project is successfully created`,
          });
        }
      }
    },
    async saveModalEditProject() {
      let retval = await useProjectStore().update(this.modalProjectData);
      this.modalProjectData = null
      if (retval) {
        if (retval.status == false) {
          useNotificationStore().add({
            type: "error",
            text: retval.msg,
          });
        }
        else {
          useUserStore().fetchUserData();
          useNotificationStore().add({
            type: "success",
            text: `The project is successfully updated`,
          });
        }
      }
    },
    async saveModalCorpus(){
      const meta = {
        corpusId: this.corpusModal.corpus_id,
        metadata: this.corpusModal.meta,
        descriptions: this.corpusModal.layer,
        globals: this.corpusModal.globalAttributes
      };
      const isSuperAdmin = useUserStore().isSuperAdmin;
      if (isSuperAdmin)
        meta.projects = this.corpusModal.projects;
      let retval = await useCorpusStore().updateMeta(meta);
      if (retval && retval.status == false)
        useNotificationStore().add({
          type: "error",
          text: retval.msg,
        });
      const metadataedit = this.$refs.metadataedit;
      const overwriteCorpus = metadataedit.overwriteCorpus;
      if ([null, undefined].includes(overwriteCorpus))
        return;
      retval = await useCorpusStore().overwriteCorpus(this.corpusModal.corpus_id, overwriteCorpus.id);
      if (retval && retval.status == false)
        useNotificationStore().add({
          type: "error",
          text: retval.msg,
        });
    },
    async submitModalSWISSUbase() {
      await this.saveModalCorpus();
      useSWISSUbaseStore().submitSWISSUbase(this.corpusModal.corpus_id)
      // console.log("Saving SWISSUbase corpus data");
    },
    corpusDataType: Utils.corpusDataType,
    // setTooltips() {
    //   this.removeTooltips();tooltip
    //   const tooltipTriggerList = Array.from(
    //     document.querySelectorAll(".tooltips")
    //   );
    //   tooltipTriggerList.forEach((tooltipTriggerEl) => {
    //     let tooltipInstance = new Tooltip(tooltipTriggerEl);
    //     this.tooltips.push(tooltipInstance);
    //   });
    // },
    // removeTooltips() {
    //   this.tooltips.forEach((tooltipInstance) => {
    //     tooltipInstance.dispose();
    //   });
    //   this.tooltips = [];
    // },
    updateOverflows() {
      this.overflowingLeft = {1:1, ...Object.fromEntries(this.projectsGroups.filter(p=>this.corpusOverflow(p.id, 'left')).map(p=>[p.id,1]))};
      this.overflowingRight = {1:1, ...Object.fromEntries(this.projectsGroups.filter(p=>this.corpusOverflow(p.id, 'right')).map(p=>[p.id,1]))};
    },
    scrollProject(projectId, direction, delta) {
      delta = delta || 100;
      if (this.scrollProjectTimeout)
        this.scrollProjectTimeout = clearTimeout(this.scrollProjectTimeout);
      const projectsRef = this.$refs.projects;
      if (!projectsRef) return;
      const projectContainer = projectsRef.querySelector(`#project-${projectId}`);
      if (!projectContainer) return;
      const corporaContainer = projectContainer.querySelector(".corpora-container");
      if (!corporaContainer) return;
      const projectContainerRight = projectContainer.getBoundingClientRect().right;
      const lastChildLeft = [...corporaContainer.children].at(-1).getBoundingClientRect().left;
      const left = parseInt(window.getComputedStyle(corporaContainer).marginLeft);
      let newMargin = left + (direction=='right'?-1:1) * delta;
      if (newMargin > 0) newMargin = 0;
      if (lastChildLeft+350 < projectContainerRight) newMargin = Math.max(newMargin, left);
      corporaContainer.style.marginLeft = `${newMargin}px`;
      this.updateOverflows();
      this.scrollProjectTimeout = setTimeout(()=>this.scrollProject(projectId, direction), 5);
    }
  },
  computed: {
    ...mapState(useCorpusStore, ["queryData", "corpora"]),
    ...mapState(useCorpusStore, {
      corpusLicenses: "licenses",
      corpusLanguages: "languages",
    }),
    ...mapState(useUserStore, ["projects", "userData"]),
    allLanguages() {
      const lgDict = {};
      for (let c of this.corpora) {
        if (c.meta.language)
          lgDict[c.meta.language] = {langCode: c.meta.language, langName: this.getLanguage(c.meta.language)};
        else if (c.partitions && c.partitions.values instanceof Array) {
          for (let p of c.partitions.values)
            lgDict[p] = {langCode: p, langName: this.getLanguage(p)};
        }
      }
      return Object.values(lgDict).sort((a,b)=>a.langName > b.langName);
    },
    projectsGroups() {
      const isSuperAdmin = useUserStore().isSuperAdmin;
      let projects = {};
      let projectIds = [];
      this.projects.forEach((project) => {
        let isPublic = project.additionalData && project.additionalData.public == true;
        let isSemiPublic = project.additionalData && project.additionalData.semiPublic == true;
        projectIds.push(project.id);
        if (isSuperAdmin) project.isAdmin = true;
        projects[project.id] = {
          ...project,
          corpora: [],
          isPublic: isPublic,
          isSemiPublic: isSemiPublic,
        };
      });
      let publicProjects = this.projects.filter(project => project.additionalData && project.additionalData.public == true);
      let publicProjectId = publicProjects.length ? publicProjects[0].id : -1;

      this.corpora.forEach((corpus) => {
        corpus.projects.forEach(projectId => {
          projectId = projectId == "all" ? publicProjectId : projectId;  // -1 for public
          if (projectIds.includes(projectId) && !projects[projectId].corpora.includes(corpus)) {
            if (
              this.corporaFilter == '' ||
              corpus.meta.name.toLowerCase().includes(this.corporaFilter.toLowerCase()) // Filter corpora by name
            ) {
              projects[projectId].corpora.push(corpus);
            }
          }
        })
      });
      let sortedProjects = []

      // Show public projects first
      Object.keys(projects).forEach((projectId) => {
        if (projects[projectId].isPublic) {
          sortedProjects.push(projects[projectId])
          delete projects[projectId]
        }
      })
      // Show semi-public projects second
      Object.keys(projects).forEach((projectId) => {
        if (projects[projectId].isSemiPublic) {
          sortedProjects.push(projects[projectId])
          delete projects[projectId]
        }
      })
      // Rest
      sortedProjects.push(...Object.values(projects));
      return sortedProjects;
    },
    getUniqueProjects() {
      return this.projects.filter((p, n) => !this.projects.slice(n+1, ).find(p2 => p2.id == p.id))
    },
  },
  mounted() {
    // this.setTooltips();
    setTooltips();
    window.addEventListener("keydown", e=>{
      if (!this.currentProject) return;
      if (e.key == "ArrowLeft") this.scrollProject(this.currentProject.id, 'left');
      if (e.key == "ArrowRight") this.scrollProject(this.currentProject.id, 'right');
    });
    window.addEventListener("keyup", ()=>{
      if (!this.scrollProjectTimeout) return;
      this.scrollProjectTimeout = clearTimeout(this.scrollProjectTimeout);
    });
    window.addEventListener("pointermove", e=>{
      const [lastX, projectId] = this.dragScrolling;
      if (!projectId) return;
      const diff = lastX - e.clientX;
      this.scrollProject(projectId, diff > 0 ? 'right' : 'left', Math.abs(diff));
      // Don't automatically keep scrolling but keep a 500ms timeout to prevent pointerup from opening corpora 
      if (this.scrollProjectTimeout) clearTimeout(this.scrollProjectTimeout);
      this.scrollProjectTimeout = setTimeout(()=>this.scrollProjectTimeout = null, 500);
      this.dragScrolling[0] = e.clientX;
    });
    window.addEventListener("pointerup", ()=>{
      this.dragScrolling = [];
      if (!this.scrollProjectTimeout) return;
      clearTimeout(this.scrollProjectTimeout);
      this.scrollProjectTimeout = setTimeout(()=>this.scrollProjectTimeout = null, 500); // prevent clicks on corpora
    });
  },
  watch: {
    projects() {
    },
    allLanguages() {
      this.languageFilter = this.allLanguages.map(l=>l.langCode);
    }
  },
  async updated() {
    // this.setTooltips();
    // setTooltips();
    this.languageFilter = this.languageFilter || this.allLanguages.map(l=>l.langCode);
    if (Object.keys(this.overflowingLeft).length > 0 || Object.keys(this.overflowingRight).length > 0) return;
    await new Promise(r=>setTimeout(r, 500));
    this.updateOverflows();
    this.resizeObserver.disconnect();
    for (let c of this.$refs.projects.querySelectorAll(".corpora-container"))
      this.resizeObserver.observe(c.parentElement);
  },
  beforeUnmount() {
    // this.removeTooltips();
    removeTooltips();
  },
};
</script>

<style scoped>
.no-corpora {
  opacity: 0.5;
}
.tabs-wrapper {
  position: relative;
  margin: 0 auto;
  overflow: hidden;
  padding: 5px;
  height: 39px;
}

.tabs-wrapper .tabs-list {
  position: absolute;
  left: 0px;
  top: 0px;
  min-width: 3000px;
  margin-left: 0px;
  margin-top: 0px;
  transition: all 0.5s;
}

.tabs-wrapper .tabs-list button {
  display: table-cell;
  position: relative;
  text-align: center;
  cursor: pointer;
  vertical-align: middle;
}

.fit-body {
  max-height: 80vh;
  overflow-y: scroll;
}

.nav-tabs {
  box-shadow: none !important;
  border-bottom: none !important;
}

.tabsnav {
  border-bottom: 1px solid #dee2e6;
  box-shadow: 0 5px 7px -8px #777;
}

.row.mt-3 {
  max-width: 80%;
  margin: auto;
}

.language-filter input {
  display: none;
}

.language-filter label {
  width: 2.75em;
  text-align: center;
  margin: 0em 0.25em;
  border-radius: 20px;
  border: solid 1px gray;
  font-variant: petite-caps;
  font-size: 1.2em;
}

.language-filter input:checked + label {
  background-color: burlywood;
  color: white;
}

#nav-tabContent {
  display: flex;
  flex-direction: column;
}

#nav-tabContent .tab-pane {
  padding: 0.25em;
  border-radius: 0.5em;
  margin-bottom: 1em;
  box-shadow: 0px 5px 5px lightgray;
  position: relative;
  overflow: hidden;
}

.project-header {
  display: flex;
  margin-bottom: 0.5em;
  position:relative;
  justify-content: space-between;
}
.project-header div {
  padding-right: 0.5em;
}
.project-header .project-name, .project-header .project-details {
  white-space: nowrap;
  flex-shrink: 1;
  overflow-x: hidden;
  text-overflow: ellipsis;
}
.project-header .project-name {
  max-width: 33%;
}
.project-header .project-details {
  display: flex;
  max-width: 80%;
  flex-grow: 1;
}
.project-header .project-details .project-description {
  max-width: 55%;
  overflow-x: hidden;
  text-overflow: ellipsis;
  font-style: italic;
}
.project-header .project-details .project-admin {
  display: flex;
}
.project-header .project-settings {
  position: absolute;
  top: -0.33em;
  right: 0.5em;
}

.scroller-left, .scroller-right {
  height: calc(100% - 3em);
  width: 2em;
  display: block;
  position: absolute;
  z-index: 99;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  font-weight: bold;
  color: white;
  cursor: pointer;
  opacity: 0.5;
  user-select: none;
}
.scroller-left:hover, .scroller-right:hover {
  color: black;
  opacity: 1;
}
.scroller-left {
  background: linear-gradient(90deg,rgb(130, 130, 130) 0%, rgb(179, 179, 179) 50%, rgba(255, 255, 255, 0) 100%);
}
.scroller-right {
  right: 3px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0) 0%, rgb(179, 179, 179) 50%, rgb(130, 130, 130) 100%);
}

.corpora-container {
  display: flex;
  height: 500px;
  flex-flow: column wrap;
  overflow-x: hidden;
  resize: vertical;
  user-select: none;
}

.corpus-block {
  border: 1px solid #d4d4d4;
  border-radius: 5px;
  cursor: pointer;
  position: relative;
  height: 233px;
  width: 350px;
  margin: 0em 1em 1em 0em;
}

.corpus-block-header {
  width: 100%;
  background-color: #d1e7dd;
  transition: all 0.3s;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
}

.corpus-block-header .icon-x:hover {
  background-color: white;
}

.corpus-block:hover .corpus-block-header {
  background-color: #b4d8c8;
}

.data-type-video .corpus-block-header {
  background-color: #ede7f0;
}

.data-type-video:hover .corpus-block-header {
  background-color: #d7cade;
}

.data-type-audio .corpus-block-header {
  background-color: #e8eff8;
}

.data-type-audio:hover .corpus-block-header {
  background-color: #c3d5ed;
}

.author {
  font-size: 70%;
  height: 10px;
}

.corpus-block:hover {
  background-color: #f9f9f9;
}

.title {
  font-size: 110%;
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.badge.revision {
  transform: translate(-0.25em, -0.5em) scale(0.75);
  background-color: #5599be !important;
  padding: 0.2em;
}

.description {
  font-size: 90%;
  height: 108px;
  overflow: hidden;
}

.word-count {
  font-size: 80%;
}

.corpus-block .word-count {
  display: inline-flex;
  flex-direction: row-reverse;
  transform: translateY(-50%);
}

.corpus-block .badge {
  box-shadow: 0px 0px 2px black;
}

.badge.language:not(:last-child):not(:first-child) {
  margin-left: -1.25em;
  width: 2.2em;
}

.badge.language:last-child::before {
  content: '🚩';
  position: absolute;
  transform: translate(-100%, -100%);
}

.project-box {
  border: 1px solid #f2f2f2;
  border-radius: 3px;
}

.project-title {
  font-size: 14px;
  margin-top: 7px;
}

.api-badge {
  font-size: 80%;
  font-weight: bold;
}

.details-data-type {
  position: absolute;
  top: 18px;
  color: #2a7f62;
  opacity: 0.9;
  right: 10px;
}

.details-button {
  position: absolute;
  bottom: 10px;
  /* background-color: #2a7f62;
  padding: 3px 10px;
  border-radius: 4px;
  color: #fff; */
  color: #2a7f62;
  opacity: 0.9;
}

.data-type-text .details-button .icon-x {
  color: #2a7f62;
}

.details-button:disabled {
  filter: grayscale(100);
  opacity: 0.5;
}

.corpus-block:hover .details-button {
  opacity: 1;
}

.details-button .icon-1:hover,
.details-button .icon-x:hover {
  opacity: 0.7 !important;
}

.details-button.icon-1 {
  right: 0;
  bottom: 0;
  background-color: #2a7f62;
  padding: 15px 10px 10px 15px;
  color: #fff;
  border-radius: 40px 0 0;
}

.details-button.icon-1:hover {
  opacity: 1 !important;
}

.details-button.icon-1:hover .dropdown-app-content {
  display: block;
}

.data-type-audio .details-data-type,
.data-type-audio .details-button,
.data-type-audio .icon-x {
  color: #0059be;
}

.data-type-audio .details-button.icon-1 {
  background-color: #0059be;
  color: #fff;
}

.data-type-audio .text-bg-primary {
  background-color: #0059be !important;
}

.data-type-video .details-data-type,
.data-type-video .details-button,
.data-type-video .icon-x {
  color: #622A7F;
}

.data-type-video .text-bg-primary {
  background-color: #622A7F !important;
}

.data-type-video .details-button.icon-1 {
  background-color: #622A7F;
  color: #fff;
}

.details-button.icon-1.disabled {
  background-color: #969696;
  width: 45px;
}

.details-button.icon-2 {
  right: 5px;
}

.icon-x {
  display: inline-block;
  padding-left: 7px;
  padding-right: 7px;
}

.details-button .icon-x {
  scale: 1.33;
}

.horizontal-space {
  margin: 0em 1em;
}

#new-collection {
  width: min-content;
  position: sticky;
  bottom: 1.5em;
  left: calc(100vw - 3.5em);
  scale: 3;
}
#new-collection button {
  border-radius: 50%;
  width: 1em;
  height: 1em;
  padding: 0px;
  color: gray;
  background-color: white;
  box-shadow: 0px 0px 2px gray;
}
#new-collection:hover button {
  color: whitesmoke !important;
  background-color: gray !important;
}
#new-collection button svg {
  transform: translate(-1px,-4px);
}


/* #languages-filter {
  position: absolute;
  right: 0;
  max-width: 300px;
  margin-top: 2.3em;
  background-color: var(--bs-tertiary-bg);
  border: solid 1px var(--bs-border-color);
  z-index: 99;
  display: flex;
  flex-direction: column;
} */
</style>
