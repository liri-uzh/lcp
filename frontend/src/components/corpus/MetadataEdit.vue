<template>
  <div id="corpus-warning">
    <div class="row">
      <div class="col-18" style="font-style: italic;">
        {{ $t('modal-meta-warning-before') }} {{ getUserLocale().name }}{{ $t('modal-meta-warning-after') }}
      </div>
    </div>
  </div>
  <div class="nav nav-tabs mt-3" id="nav-main-tab" role="tablist">
    <button class="nav-link" :class="{ active: activeMainTab === 'metadata' }" id="nav-metadata-tab"
      data-bs-toggle="tab" data-bs-target="#nav-metadata" type="button" role="tab" aria-controls="nav-metadata"
      aria-selected="true" @click="activeMainTab = 'metadata'">
      {{ $t('modal-meta-metadata') }}
    </button>
    <button class="nav-link" :class="{ active: activeMainTab === 'structure' }" id="nav-structure-tab"
      data-bs-toggle="tab" data-bs-target="#nav-structure" type="button" role="tab" aria-controls="nav-structure"
      aria-selected="false" @click="activeMainTab = 'structure'">
      {{ $t('modal-meta-structure') }}
    </button>
    <div class="group-selector" v-if="isSuperAdmin">
      <span>Group:</span>
      <multiselect
        v-model="projects"
        :options="allProjects"
        :multiple="true"
        label="title"
        placeholder="Choose a project"
        track-by="id"
      ></multiselect>
    </div>
  </div>
  <div class="tab-content" id="nav-main-tabContent">
    <div class="tab-pane fade pt-3"
      :class="{ active: activeMainTab === 'metadata', show: activeMainTab === 'metadata' }" id="nav-metadata"
      role="tabpanel" aria-labelledby="nav-metadata-tab">
      <div id="corpus-metadata-edit">
        <div class="row">
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-name" class="form-label">{{ $t('modal-meta-name') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.name" id="corpus-name" maxlength="50" />
            </div>
          </div>
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-url" class="form-label">{{ $t('modal-meta-url') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.url" id="corpus-url" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-12">
            <div class="mb-3">
              <label for="corpus-authors" class="form-label">{{ $t('modal-meta-authors') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.authors" id="corpus-authors" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-institution" class="form-label">{{ $t('modal-meta-provider') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.institution" id="corpus-institution" />
            </div>
          </div>
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-revision" class="form-label">{{ $t('modal-meta-revision') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.revision" id="corpus-revision" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-4">
            <div class="mb-3">
              <label for="corpus-language" class="form-label">{{ $t('modal-meta-language') }} </label>
              <multiselect
                v-model="selectedLanguage"
                :options="languages"
                placeholder="Select langauage"
                :multiple="false"
                label="name"
                track-by="value"
              ></multiselect>
            </div>
          </div>
          <!-- <div class="col-7">
            <div class="mb-3">
              <label for="corpus-license" class="form-label">{{ $t('modal-meta-data-type') }} <b>{{ corpusDataType(corpusData) }}</b></label>
            </div>
          </div> -->
        </div>
        <div class="row">
          <div class="col-12">
            <div class="mb-3">
              <label for="corpus-description" class="form-label">{{ $t('modal-meta-description') }}</label>
              <textarea
                class="form-control"
                placeholder="Corpora description"
                v-model="corpusData.meta.corpusDescription"
                id="corpus-description"
                style="height: 100px"
              ></textarea>
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-12">
            <div class="mb-3">
              <label for="corpus-license" class="form-label">{{ $t('modal-meta-license') }}</label>
              <div class="row">
                <div class="col-3 mb-2" v-for="licence in licenses" :key="licence.name">
                  <div class="form-check">
                    <input
                      class="form-check-input form-check-inline"
                      type="radio"
                      v-model="corpusData.meta.license"
                      :id="licence.tag"
                      :value="licence.tag"
                      :selected="corpusData.meta.license === licence.tag"
                    >
                    <label class="form-check-label" :for="licence.tag" v-if="licence.tag == 'user-defined'">
                      {{ $t('modal-meta-user-defined') }}
                    </label>
                    <label class="form-check-label" :for="licence.tag" v-else>
                      <img :src="`/licenses/${licence.tag}.png`" :alt="licence.name" class="license-img" />
                      <a :href="licence.url" target="_blank">
                        <FontAwesomeIcon :icon="['fas', 'link']" />
                        {{ licence.name }}
                      </a>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="col-12" v-if="corpusData.meta.license == 'user-defined'">
            <div class="mb-3">
              <label for="corpus-description" class="form-label">{{ $t('modal-meta-user-license') }}</label>
              <textarea
                class="form-control"
                placeholder="User defined licence"
                v-model="userLicense"
                id="user-defined-licence"
                style="height: 100px"
              ></textarea>
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-12">
            <div class="mb-3">
              <label for="corpus-sample" class="form-label">{{ $t('modal-meta-sample') }}</label>
              <textarea
                class="form-control"
                placeholder="Sample DQD query"
                v-model="corpusData.meta.sample_query"
                id="corpus-sample"
                style="height: 300px"
              ></textarea>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="tab-pane fade pt-3"
      :class="{ active: activeMainTab === 'structure', show: activeMainTab === 'metadata' }" id="nav-structure"
      role="tabpanel" aria-labelledby="nav-structure-tab">
      <div id="corpus-structure-edit">
        <div v-for="(props, layer) in corpusData.layer" :key="`layer-${layer}`">
          <label :for="`layer-${layer}`" class="form-label layer">{{ layer }}</label>
          <input
            type="text"
            class="form-control"
            :id="`layer-${layer}`"
            v-model="props.description"
            :placeholder="$t('modal-structure-no-desc')"
          />
          <div v-for="(aprops, attribute) in getLayerAttributes(props.attributes)" :key="`attribute-${layer}-${attribute}`" class="attribute">
            <label :for="`attribute-${layer}-${attribute}`" class="form-label">{{ attribute }}</label>
            <input
              type="text"
              class="form-control"
              :id="`attribute-${layer}-${attribute}`"
              v-model="aprops.description"
              :placeholder="$t('modal-structure-no-desc')"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.license-img {
  height: 30px;
}
a {
  margin-left: 10px;
  text-decoration: none;
  color: #2a7f62;
  transition: all 0.3s;
}
a:hover {
  opacity: 0.8;
}
.form-label.layer {
  font-weight: bold;
}
.attribute {
  margin: 0.5em 0em 0.5em 1em
}
.group-selector {
  display: flex;
  align-items: center;
  min-width: 15em;
  position: absolute;
  right: 1em;
}
</style>

<script>
import { mapState } from "pinia";
import { useCorpusStore } from "@/stores/corpusStore";
import { getUserLocale } from "@/fluent";
import Utils from "@/utils";
import { useUserStore } from "@/stores/userStore";

export default {
  name: "CorpusMetdataEdit",
  props: ["corpus","allProjects"],
  data() {
    let corpusData = { ...this.corpus } || {};
    if (corpusData.meta && !corpusData.meta.language) {
      corpusData.meta.language = "und"; // Default to undefined language
    }
    let userLicense = "";
    try {
      userLicense = atob(this.corpus.meta.userLicense);
    } catch {
      userLicense = this.corpus.meta.userLicense || "";
    }
    if (corpusData.projects.length == 0)
      corpusData.projects.push(corpusData.project_id);
    const ownProjects = this.allProjects.filter(p=>corpusData.projects.includes(p.id));
    return {
      activeMainTab: "metadata",
      userLicense: userLicense,
      corpusData: corpusData,
      isSuperAdmin: useUserStore().isSuperAdmin,
      projects: ownProjects
    }
  },
  computed: {
    ...mapState(useCorpusStore, ["licenses", "languages"]),
    selectedLanguage: {
      get() {
        return this.languages.find(l => l.value === this.corpusData.meta.language)
      },
      set(val) {
        this.corpusData.meta.language = val.value
      }
    }
  },
  methods: {
    corpusDataType: Utils.corpusDataType,
    getUserLocale: getUserLocale,
    getLayerAttributes: (attributes) => {
      let ret = attributes;
      if ("meta" in (attributes || {}) && typeof(attributes.meta) != "string") {
        ret = Object.fromEntries(Object.entries(attributes).filter(v=>v[0] != "meta"));
        for (let [k,v] of Object.entries(attributes.meta))
          ret[k] = v;
      }
      return ret;
    }
  },
  watch: {
    userLicense() {
      this.corpusData.meta.userLicense = btoa(this.userLicense);
    },
    projects() {
      while (this.corpusData.projects.length)
        this.corpusData.projects.pop();
      this.corpusData.projects.push(...this.projects.map(p=>p.id));
      if (!this.corpusData.project_id || !this.projects.includes(this.corpusData.project_id))
        this.corpusData.project_id = this.projects[0];
      if (!this.corpusData.project || !this.projects.includes(this.corpusData.project))
        this.corpusData.project = this.projects[0];
    }
  },
}
</script>
