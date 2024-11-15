<template>
  <div class="home">
    <div class="container">
      <div class="row mt-4">
        <div class="col-8">
          <Title title="LiRI Corpus Platform" />
          <p>
            The LiRI Corpus Platform (LCP) is a software system for handling and querying corpora of different kinds. Users can query corpora directly from their browser, and upload their own corpora using a command-line interface.
          </p>
        </div>
        <div class="col mt-1 text-end" v-if="userData && userData.user && userData.user.displayName">
          <button
            type="button"
            class="btn btn-secondary btn-sm"
            data-bs-toggle="modal"
            data-bs-target="#newProjectModal"
            @click="modalIndexKey++"
          >
            <FontAwesomeIcon :icon="['fas', 'circle-plus']" class="me-1" />
            Add new group
          </button>
        </div>
      </div>
      <div class="row mt-3">
        <div class="col">
          <div class="input-group mb-3">
            <span class="input-group-text" id="basic-addon1">
              <FontAwesomeIcon :icon="['fas', 'magnifying-glass']" />
            </span>
            <input type="text" class="form-control" v-model="corporaFilter" placeholder="Find Corpora" />
          </div>
          <div v-if="corporaFilter && filterError && filterError.message" class="alert notification alert-danger">
            {{ filterError.message }}
          </div>
        </div>
      </div>
    </div>
    <div class="container mt-4 text-start">
      <div class="row">
        <nav ref="tabsnav" class="tabsnav">
          <div class="scroller scroller-left" @click="tabsScrollLeft" ref="leftcaret">
            <FontAwesomeIcon :icon="['fas', 'caret-left']" class="me-1" />
          </div>
          <div class="scroller scroller-right" @click="tabsScrollRight" ref="rightcaret">
            <FontAwesomeIcon :icon="['fas', 'caret-right']" class="me-1" />
          </div>
          <div class="tabs-wrapper" ref="tabswrapper">
            <div class="nav nav-tabs tabs-list" id="nav-tab" ref="tabslist" role="tablist">
              <button
                v-for="(project, index) in projectsGroups"
                :key="project.id"
                class="nav-link"
                :class="[index == 0 ? 'active' : '', corporaFilter && project.corpora.length == 0 ? 'no-corpora' : '']"
                :id="`nav-${project.id}-tab`"
                data-bs-toggle="tab"
                :data-bs-target="`#nav-${project.id}`"
                type="button" role="tab"
                :aria-controls="`nav-${project.id}`"
                aria-selected="true"
                @click="currentProject = project"
              >
                <FontAwesomeIcon
                  :icon="projectIcons(project)"
                  class="me-1"
                />
                {{ project.title }}
                <span class="api-badge">({{ project.corpora.length }})</span>
                <span class="ms-1 api-badge" v-if="project.api">[API]</span>
              </button>
            </div>
          </div>
        </nav>
        <div class="tab-content pt-3" id="nav-tabContent">
          <div v-for="(project, index) in projectsGroups" :key="project.id" class="tab-pane fade"
            :class="index == 0 ? 'active show' : ''" :id="`nav-${project.id}`" role="tabpanel"
            aria-labelledby="nav-results-tab">
            <div class="alert alert-success" role="alert" v-if="project.description || project.isAdmin">
              <div class="row">
                <div class="col-11">
                  <div class="row" v-if="project.isAdmin">
                    <div class="col-3">
                      Start date: <b>{{ formatDate(project.startDate, "DD.MM.YYYY") }}</b>
                    </div>
                    <div class="col-3">
                      Finish date: <b>{{ formatDate(project.finishDate, "DD.MM.YYYY") }}</b>
                    </div>
                    <!-- <div class="col-2">
                      Institution: <b>{{ project.institution }}</b>
                    </div> -->
                    <div class="col-3">
                      API: <b>{{ project.api ? "Enabled" : "Disabled" }}</b>
                    </div>
                    <!-- <div class="col-3">
                      Visibility: <b>{{ project.additionalData && project.additionalData.visibility ? project.additionalData.visibility : "private" }}</b>
                    </div> -->
                  </div>
                  <div class="row" v-if="project.description">
                    <div class="col-12">
                      Description: <b>{{ project.description }}</b>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="row mt-2">
              <!-- @click="openDropdown(corpus)" -->
              <div
                v-for="corpus in filterCorpora(project.corpora)"
                :key="corpus.id"
                @click.stop="openQueryWithCorpus(corpus, 'catchphrase')"
                class="col-4 mb-3"
              >
                <div
                  class="corpus-block"
                  :class="`data-type-${corpusDataType(corpus)}`"
                  v-on:mouseleave="clearDropdowns"
                >
                  <div class="corpus-block-header px-4 py-3">
                    <p class="title mb-0">{{ corpus.meta.name }}</p>
                    <!-- <p class="author mb-0">
                      <span v-if="corpus.meta.author">{{ corpus.meta.author }}</span>
                    </p> -->
                  </div>
                  <div class="px-4">
                    <p class="description mt-3">
                      {{ corpus.meta.corpusDescription }}
                    </p>
                    <p class="word-count">
                      <template v-if="corpus.partitions">
                        <span
                          class="badge text-bg-primary me-1 tooltips" title="Partition"
                          v-for="language in corpus.partitions.values"
                          v-html="language.toUpperCase()" :key="`${corpus.id}-${language}`"
                        />
                      </template>
                      <span class="badge text-bg-primary me-1 tooltips" title="Word count"
                      >{{
                        nFormatter(
                          calculateSum(Object.values(corpus.token_counts))
                        )
                      }}</span>
                      <span
                        class="badge text-bg-primary me-1 tooltips"
                        :title="`Revision: ${corpus.meta.revision}`"
                        v-if="corpus.meta.revision"
                      >R{{ corpus.meta.revision }}</span>
                    </p>
                  </div>

                  <div class="details-button icon-1" v-if="hasAccessToCorpus(corpus, userData)">
                    <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
                    <FontAwesomeIcon class="ms-1" :icon="['fas', 'caret-down']" />
                    <!-- :class="corpusBlockDropDowns.includes(corpus.meta.id) ? 'open' : ''" -->
                    <div
                      class="dropdown-app-content"
                    >
                      <a
                        href="#"
                        @click.stop="openQueryWithCorpus(corpus, 'catchphrase')"
                      >
                        <FontAwesomeIcon :icon="['fas', 'font']" class="me-2" />
                        <i>catchphrase</i>
                      </a>
                      <a
                        href="#"
                        v-if="['audio', 'video'].includes(corpusDataType(corpus))"
                        @click.stop="openQueryWithCorpus(corpus, 'soundscript')"
                      >
                        <FontAwesomeIcon :icon="['fas', 'music']" class="me-2" />
                        <i>soundscript</i>
                      </a>
                      <a
                        href="#"
                        v-if="['video'].includes(corpusDataType(corpus))"
                        @click.stop="openQueryWithCorpus(corpus, 'videoscope')"
                      >
                        <FontAwesomeIcon :icon="['fas', 'video']" class="me-2" />
                        <i>videoscope</i>
                      </a>
                    </div>
                  </div>
                  <div
                    class="details-button icon-1 tooltips disabled"
                    title="You currently don't have permissions to query this corpus. Please see the corpus description to learn how to gain access."
                    v-else-if="userData.user.displayName"
                  >
                    <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
                  </div>
                  <div
                    class="details-button icon-1 tooltips disabled"
                    title="Access to this corpus is restricted. We need you to log in to evaluate your permissions."
                    v-else
                  >
                    <FontAwesomeIcon :icon="['fas', 'magnifying-glass-chart']" />
                  </div>

                  <div class="details-button icon-2">
                    <span
                      v-if="project.isAdmin"
                      class="tooltips icon-x"
                      title="Corpus edit"
                      @click.stop="openCorpusEdit(corpus)"
                    >
                      <FontAwesomeIcon :icon="['fas', 'gear']" />
                    </span>
                    <span
                      :href="corpusStore.getLicenseByTag(corpus.meta.license)"
                      class="tooltips icon-x"
                      target="_blank"
                      :title="`Corpus licence: User defined - Check details`"
                      v-if="corpus.meta.license == 'user-defined'"
                    >
                      <FontAwesomeIcon :icon="['fas', 'certificate']" />
                    </span>
                    <a
                      :href="corpusStore.getLicenseByTag(corpus.meta.license).url"
                      target="_blank"
                      class="tooltips icon-x"
                      v-else-if="corpus.meta.license"
                      :title="`Corpus licence: ${corpus.meta.license}`"
                    >
                      <FontAwesomeIcon :icon="['fas', 'certificate']" />
                    </a>
                    <span class="tooltips icon-x" title="Corpus details" @click.stop="openCorpusDetailsModal(corpus)">
                      <FontAwesomeIcon :icon="['fas', 'circle-info']" />
                    </span>
                    <a class="tooltips icon-x" :href="getURLWithProtocol(corpus.meta.url)" title="Corpus origin"
                      :disabled="!corpus.meta.url" target="_blank" @click.stop>
                      <FontAwesomeIcon :icon="['fas', 'link']" />
                    </a>
                  </div>
                  <div class="details-data-type icon-3 tooltips" title="Data type" v-if="appType == 'lcp'">
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

    <!-- Modals -->
    <div class="modal fade" id="newProjectModal" tabindex="-1" aria-labelledby="newProjectModalLabel" aria-hidden="true"
      ref="vuemodal">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="newProjectModalLabel">New Group</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start">
            <ProjectNewView @updated="updateProjectModalData" :key="modalIndexKey" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              Close
            </button>
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="saveModalProject"
              :disabled="!allowProjectModalSave">
              Save
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
              Corpus details
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start" v-if="corpusModal">
            <CorpusDetailsModal :corpusModal="corpusModal" :key="modalIndexKey" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              Close
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
            <h5 class="modal-title" id="corpusEditModalLabel">
              Corpus settings
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start" v-if="corpusModal">
            <MetadataEdit :corpus="corpusModal" :key="modalIndexKey" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="saveModalCorpus">
              Save
            </button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              Close
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
              <b v-if="currentProject">{{ currentProject.title }}</b> group settings
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start" v-if="currentProject && currentProject.id">
            <ProjectEdit :project="currentProject" :key="modalIndexKey" @updated="updateProjectModalData" />
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="saveModalEditProject" :disabled="!allowProjectModalSave">
              Save
            </button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              Close
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
import { useProjectStore } from "@/stores/projectStore";
import { useUserStore } from "@/stores/userStore";
import { useNotificationStore } from "@/stores/notificationStore";

import Title from "@/components/TitleComponent.vue";
import ProjectNewView from "@/components/project/NewView.vue";
import MetadataEdit from "@/components/corpus/MetadataEdit.vue";
import CorpusDetailsModal from "@/components/corpus/DetailsModal.vue";
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
      allowProjectModalSave: false,
      modalProjectData: null,
      appName: config.appName,
      appType: config.appType,
      appLinks: config.appLinks,
      // tooltips: [],
      corporaFilter: "",
      currentProject: null,
      filterError: null,
      currentEditTab: "metadata",
      inviteEmails: '',
      currentProjectToSubmit: null,
      modalIndexKey: 0,

      corpusBlockDropDowns: [],
      corpusStore: useCorpusStore(),
    };
  },
  components: {
    Title,
    ProjectNewView,
    CorpusDetailsModal,
    MetadataEdit,
    ProjectEdit,
  },
  methods: {
    hasAccessToCorpus: Utils.hasAccessToCorpus,
    corpusDataType: Utils.corpusDataType,
    getURLWithProtocol: Utils.getURLWithProtocol,
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
    openDropdown(corpus) {
      this.corpusBlockDropDowns.push(corpus.meta.id)
    },
    clearDropdowns() {
      this.corpusBlockDropDowns = []
    },
    tabsScrollLeft() {
      let left = Math.abs(parseInt(this.$refs.tabslist.style.left || 0, 10)) - this.scrollBoxSize() + 200
      if (left < 0) {
        left = 0
      }
      this.$refs.rightcaret.style.opacity = 1
      if (left == 0) {
        this.$refs.leftcaret.style.opacity = 0.5
      }
      this.$refs.tabslist.style.left = `-${left}px`
    },
    tabsScrollRight() {
      let left = Math.abs(parseInt(this.$refs.tabslist.style.left || 0, 10)) + this.scrollBoxSize() - 200
      if (left > this.widthOfTabs()) {
        left = this.widthOfTabs() - 200
      }
      this.$refs.leftcaret.style.opacity = 1
      if ((left + this.scrollBoxSize()) >= this.widthOfTabs()) {
        this.$refs.rightcaret.style.opacity = 0.5
      }
      this.$refs.tabslist.style.left = `-${left}px`
    },
    scrollBoxSize() {
      return this.$refs.tabsnav.offsetWidth;
    },
    widthOfTabs() {
      let itemsWidth = 0;
      this.$refs.tabslist.querySelectorAll('button').forEach((item) => {
        itemsWidth += item.offsetWidth;
      });
      return itemsWidth;
    },
    updateTabsCarets() {
      // console.log("AE", this.widthOfTabs(), this.scrollBoxSize())
      // if (this.widthOfTabs() > this.scrollBoxSize()) {
        this.$refs.rightcaret.style.display = "block";
        this.$refs.leftcaret.style.display = "block";
      // }
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
              c.meta.author.search(rgx) > -1
          );
          this.filterError = null;
        }
      }

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
      this.corpusModal = { ...corpus };
      let modal = new Modal(document.getElementById('corpusDetailsModal'));
      this.modalIndexKey++
      modal.show()
    },
    openCorpusEdit(corpus) {
      this.corpusModal = { ...corpus };
      // let tab = Tab.getInstance(this.$refs);
      this.modalIndexKey++
      let modal = new Modal(document.getElementById('corpusEditModal'));
      modal.show()
    },
    openQueryWithCorpus(corpus, type) {
      if (this.hasAccessToCorpus(corpus, this.userData)) {
        if (type == "videoscope") {
          router.push(`/player/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`);
        } else {
          router.push(`/query/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`);
        }
      }
    },
    getAppLink: Utils.getAppLink,
    calculateSum(array) {
      return array.reduce((accumulator, value) => {
        return accumulator + value;
      }, 0);
    },
    nFormatter: Utils.nFormatter,
    formatDate: Utils.formatDate,
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
      let retval = await useCorpusStore().updateMeta({
        corpusId: this.corpusModal.corpus_id,
        metadata: this.corpusModal.meta,
      });
      if (retval) {
        if (retval.status == false) {
          useNotificationStore().add({
            type: "error",
            text: retval.msg,
          });
        }
      }
    },
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
  },
  computed: {
    ...mapState(useCorpusStore, ["queryData", "corpora"]),
    ...mapState(useUserStore, ["projects", "userData"]),
    projectsGroups() {
      let projects = {}
      let projectIds = [];
      this.projects.forEach((project) => {
        let isPublic = project.additionalData && project.additionalData.public == true;
        let isSemiPublic = project.additionalData && project.additionalData.semiPublic == true;
        projectIds.push(project.id);
        projects[project.id] = {
          ...project,
          corpora: [],
          isPublic: isPublic,
          isSemiPublic: isSemiPublic,
        };
      });
      let publicProjects = this.projects.filter(project => project.additionalData && project.additionalData.public == true)
      let publicProjectId = publicProjects.length ? publicProjects[0].id : -1

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
      sortedProjects.push(...Object.values(projects))
      // If there is a filter, remove empty projects
      // if (this.corporaFilter.length > 0) {
      //   let _retval = {}
      //   for (let key in retval) {
      //     if (retval[key].corpora.length > 0) {
      //       _retval[key] = retval[key]
      //     }
      //   }
      //   retval = _retval
      // }
      return sortedProjects;
    }
  },
  mounted() {
    // this.setTooltips();
    setTooltips();

    window.addEventListener('resize', this.updateTabsCarets);
    this.updateTabsCarets();
  },
  watch: {
    projects() {
      this.updateTabsCarets();
    },
  },
  updated() {
    // this.setTooltips();
    // removeTooltips();
    setTooltips();
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.updateTabsCarets);
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

.scroller {
  text-align: center;
  cursor: pointer;
  /* display: none; */
  padding: 7px;
  padding-top: 11px;
  padding-bottom: 0px;
  white-space: no-wrap;
  vertical-align: middle;
  background-color: #fff;
}

.scroller-right {
  float: right;
  display: none;
}

.scroller-left {
  float: left;
  display: none;
}

.nav-tabs {
  box-shadow: none !important;
  border-bottom: none !important;
}

.tabsnav {
  border-bottom: 1px solid #dee2e6;
  box-shadow: 0 5px 7px -8px #777;
}

.corpus-block {
  border: 1px solid #d4d4d4;
  border-radius: 5px;
  /* padding: 20px; */
  cursor: pointer;
  position: relative;
  height: 233px;
}

.corpus-block-header {
  width: 100%;
  background-color: #d1e7dd;
  transition: all 0.3s;
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

.description {
  font-size: 90%;
  height: 108px;
  overflow: hidden;
}

.word-count {
  font-size: 80%;
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

details-button:disabled {
  filter: grayscale(100);
  opacity: 0.5;
}

.dropdown-app-content {
  display: none;
  position: absolute;
  background-color: #f9f9f9;
  min-width: 160px;
  box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
  z-index: 100;
}

.dropdown-app-content a {
  color: black;
  padding: 12px 16px;
  text-decoration: none;
  display: block;
  transition: all 0.3s;
}

.dropdown-app-content a:hover {
  color: black;
  background-color: #dfdfdf;
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
  width: 55px;
}

.details-button.icon-1:hover {
  opacity: 1 !important;
}

.details-button.icon-1:hover .dropdown-app-content,
.details-button.icon-1 .dropdown-app-content.open {
  display: block;
}

.data-type-audio .details-data-type,
.data-type-audio .details-button,
.data-type-video .icon-x {
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

.details-button.icon-2 {
  right: 65px;
}

.icon-x {
  display: inline-block;
  padding-left: 7px;
  padding-right: 7px;
}

.details-button.icon-1.disabled {
  background-color: #969696;
  width: 45px;
}

.horizontal-space {
  margin: 0em 1em;
}
</style>
