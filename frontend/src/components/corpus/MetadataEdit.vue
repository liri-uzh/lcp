<template>
  <!-- <div id="corpus-warning">
    <div class="row">
      <div class="col-12" style="font-style: italic;">
        {{ $t('modal-meta-warning-before') }} {{ getUserLocale().name }}{{ $t('modal-meta-warning-after') }}
      </div>
    </div>
  </div> -->
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
    <button class="nav-link" :class="{ active: activeMainTab === 'swissubase' }" id="nav-swissubase-tab"
      data-bs-toggle="tab" data-bs-target="#nav-swissubase" type="button" role="tab" aria-controls="nav-swissubase"
      aria-selected="false" @click="activeMainTab = 'swissubase'">
      {{ $t('modal-meta-swissubase') }}
    </button>
    <button
      class="nav-link ms-auto" :class="{ active: activeMainTab === 'group' }" id="nav-group-tab"
      data-bs-toggle="tab" data-bs-target="#nav-group" type="button" role="tab" aria-controls="nav-group"
      aria-selected="false" @click="activeMainTab = 'group'"
      v-if="isSuperAdmin"
    >
      {{ $t('modal-meta-group') }}
    </button>
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
              <input type="text" class="form-control" v-model="corpusData.meta.name" :disabled="isDisabled" id="corpus-name" maxlength="50" />
            </div>
          </div>
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-url" class="form-label">{{ $t('modal-meta-url') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.url" :disabled="isDisabled" id="corpus-url" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-12">
            <div class="mb-3">
              <label for="corpus-authors" class="form-label">{{ $t('modal-meta-authors') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.authors" :disabled="isDisabled" id="corpus-authors" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-institution" class="form-label">{{ $t('modal-meta-provider') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.institution" :disabled="isDisabled" id="corpus-institution" />
            </div>
          </div>
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-date" class="form-label">{{ $t('modal-meta-date') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.date" :disabled="isDisabled" id="corpus-date" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-language" class="form-label">{{ $t('modal-meta-language') }} </label>
              <multiselect
                v-model="selectedLanguage"
                :options="corpusLanguages"
                placeholder="Select language"
                :multiple="false"
                label="name"
                track-by="value"
                :disabled="isDisabled"
              ></multiselect>
            </div>
          </div>
          <!-- <div class="col-7">
            <div class="mb-3">
              <label for="corpus-license" class="form-label">{{ $t('modal-meta-data-type') }} <b>{{ corpusDataType(corpusData) }}</b></label>
            </div>
          </div> -->
          <div class="col-6">
            <div class="mb-3">
              <label for="corpus-revision" class="form-label">{{ $t('modal-meta-revision') }}</label>
              <input type="text" class="form-control" v-model="corpusData.meta.revision" :disabled="isDisabled" id="corpus-revision" />
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-12">
            <div class="mb-3">
              <label for="corpus-description" class="form-label">{{ $t('modal-meta-description') }}</label>
              <textarea
                class="form-control textarea-110"
                placeholder="Corpora description"
                v-model="corpusData.meta.corpusDescription"
                id="corpus-description"
                :disabled="isDisabled"
              ></textarea>
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col-12">
            <div class="mb-3">
              <label for="corpus-license" class="form-label">{{ $t('modal-meta-license') }}</label>
              <div class="row">
                <div class="col-3 mb-2" v-for="licence in corpusLicenses" :key="licence.name">
                  <div class="form-check">
                    <input
                      class="form-check-input form-check-inline"
                      type="radio"
                      v-model="corpusData.meta.license"
                      :disabled="isDisabled"
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
                class="form-control textarea-110"
                placeholder="User defined licence"
                v-model="userLicense"
                id="user-defined-licence"
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
      :class="{ active: activeMainTab === 'structure', show: activeMainTab === 'structure' }" id="nav-structure"
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
          <div
            v-for="(ainfo, aname) in getAttributes(props.attributes)"
            :key="`attribute-${layer}-${ainfo.isMeta ? 'meta-' : ''}${aname}`"
            class="attribute"
          >
            <label :for="`attribute-${layer}-${ainfo.isMeta ? 'meta-' : ''}${aname}`" class="form-label">{{ aname }}</label>
            <input
              type="text"
              class="form-control"
              :id="`attribute-${layer}-${ainfo.isMeta ? 'meta-' : ''}${aname}`"
              v-model="(ainfo.isMeta ? props.attributes.meta : props.attributes)[aname].description"
              :placeholder="$t('modal-structure-no-desc')"
            />
            <div
              v-for="(subainfo, subaname) in ainfo.sub"
              :key="`attribute-${ainfo.global ? 'global-'+ainfo.global : layer+'-'+aname}-${subaname}`"
              class="attribute"
            >
              <label :for="`attribute-${layer}-${aname}-${subaname}`" class="form-label">{{ subaname }}</label>
              <input
                type="text"
                class="form-control"
                :id="`attribute-${layer}-${aname}-${subaname}`"
                v-model="(ainfo.global ? corpus.globalAttributes[ainfo.global].keys : props.attributes[aname].keys)[subaname].description"
                :placeholder="$t('modal-structure-no-desc')"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
    <div
      class="tab-pane fade pt-3"
      :class="{ active: activeMainTab === 'swissubase', show: activeMainTab === 'swissubase' }"
      id="nav-swissubase"
      role="tabpanel"
      aria-labelledby="nav-swissubase-tab"
    >
      <div id="corpus-swissubase-edit" v-if="corpusData.meta.swissubase && corpusData.meta.swissubase.submittedOn">
        {{ $t('modal-swissubase-already-submitted') }}
        <strong>{{ corpusData.meta.swissubase.projectId }}</strong>.
      </div>
      <div id="corpus-swissubase-edit" v-else>
        <div class="row mt-2">
          <div class="col-12">
            <p class="mb-1">{{ $t('modal-swissubase-header-1') }}</p>
            <p class="text-bold">{{ $t('modal-swissubase-header-warning') }}</p>
          </div>
        </div>
        <div class="nav nav-tabs mt-2" id="nav-swissubase-tab" role="tablist">
          <button class="nav-link" :class="{ active: activeSwissUbaseTab === 'project' }" id="nav-swissubase-project-tab"
            data-bs-toggle="tab" data-bs-target="#nav-swissubase-project" type="button" role="tab" aria-controls="nav-swissubase-project"
            aria-selected="true" @click="activeSwissUbaseTab = 'project'">
            {{ $t('modal-swissubase-tab-project') }}
          </button>
          <button class="nav-link" :class="{ active: activeSwissUbaseTab === 'dataset' }" id="nav-swissubase-dataset-tab"
            data-bs-toggle="tab" data-bs-target="#nav-swissubase-dataset" type="button" role="tab" aria-controls="nav-swissubase-dataset"
            aria-selected="true" @click="activeSwissUbaseTab = 'dataset'">
            {{ $t('modal-swissubase-tab-dataset') }}
          </button>
          <button class="nav-link" :class="{ active: activeSwissUbaseTab === 'resource' }" id="nav-swissubase-resource-tab"
            data-bs-toggle="tab" data-bs-target="#nav-swissubase-resource" type="button" role="tab" aria-controls="nav-swissubase-resource"
            aria-selected="true" @click="activeSwissUbaseTab = 'resource'">
            {{ $t('modal-swissubase-tab-resource') }}
          </button>
        </div>

        <div class="tab-content mt-1 ms-2 me-4" id="nav-swissubase-tabContent">
          <div
            class="tab-pane fade pt-3"
            :class="{ active: activeSwissUbaseTab === 'project', show: activeSwissUbaseTab === 'project' }"
            id="nav-swissubase-project"
            role="tabpanel"
            aria-labelledby="nav-swissubase-project-tab"
          >
            <div class="row">
              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">
                    {{ $t('modal-swissubase-api-access-token') }}
                    <sup><FontAwesomeIcon :icon="['fas', 'circle']" class="circle-required" /></sup>
                  </label>
                  <textarea
                    class="form-control textarea-110"
                    v-model="corpusData.meta.swissubase.apiAccessToken"
                    id="swissubase-api-access-token"
                    placeholder="SWISSUBase API Access Token"
                  ></textarea>
                </div>
              </div>
              <div class="col-5">
                <div class="mb-3">
                  <label for="swissubase-project-id" class="form-label">
                    {{ $t('modal-swissubase-project-id') }}
                    <sup><FontAwesomeIcon :icon="['fas', 'circle']" class="circle-required" /></sup>
                  </label>
                  <input
                    type="text"
                    class="form-control"
                    v-model="corpusData.meta.swissubase.projectId"
                    id="swissubase-project-id"
                    placeholder="SWISSUBase Project ID"
                  />
                </div>
              </div>
            </div>

            <button type="button" class="btn btn-primary mb-1" @click="checkSWISSUbaseAPI" :disabled="!canCheckAPISWISSUbaseToken">
              {{ $t('modal-swissubase-verify-api-token') }}
            </button>
            <div v-if="checkAccessTokenResponse && checkAccessTokenResponse.status != 200" class="alert alert-danger">
              ERROR: {{ checkAccessTokenResponse.data.msg }}
            </div>
            <div v-else-if="checkAccessTokenResponse && checkAccessTokenResponse.hasProject == false" class="alert alert-danger">
              ERROR: {{ $t('modal-swissubase-invalid-project') }}
            </div>
            <div v-else-if="checkAccessTokenResponse && checkAccessTokenResponse.hasProject == true" class="alert alert-success">
              {{ $t('modal-swissubase-valid-project') }}
            </div>
          </div>

          <div
            class="tab-pane fade pt-3"
            :class="{ active: activeSwissUbaseTab === 'dataset', show: activeSwissUbaseTab === 'dataset' }"
            id="nav-swissubase-dataset"
            role="tabpanel"
            aria-labelledby="nav-swissubase-dataset-tab"
          >
            <div class="row">
              <div class="col-6">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">{{ $t('modal-swissubase-dataset-language') }}</label>
                  <select
                    class="form-select"
                    v-model="corpusData.meta.swissubase.datasetLanguage"
                    id="swissubase-dataset-language"
                  >
                    <option v-for="lang in swissUBaseLanguages" :key="lang.value" :value="lang.value">
                      {{ lang.name }}
                    </option>
                  </select>
                </div>
              </div>
              <div class="col-3">
                <div class="mb-3">
                  <label for="swissubase-request-doi" class="form-label">{{ $t('modal-swissubase-request-doi') }}</label>
                  <select
                    class="form-select"
                    v-model="corpusData.meta.swissubase.requestDoi"
                    id="swissubase-request-doi"
                  >
                    <option value="true">{{ $t('common-yes') }}</option>
                    <option value="false">{{ $t('common-no') }}</option>
                  </select>
                </div>
              </div>
              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">
                    {{ $t('modal-swissubase-dataset-title') }} ({{ currentTitleLang.toUpperCase() }})
                    <sup><FontAwesomeIcon :icon="['fas', 'circle']" class="circle-required" /></sup>
                  </label>
                  <div
                    class="btn-group float-end btn-group-sm ms-2"
                    role="group"
                    aria-label="Dataset Title Language"
                    style="margin-bottom: 5px;"
                  >
                    <button
                      type="button"
                      class="btn"
                      :class="currentTitleLang === 'en' ? 'btn-primary' : 'btn-light'"
                      @click="currentTitleLang = 'en'"
                    >EN</button>
                    <button
                      type="button"
                      class="btn"
                      :class="currentTitleLang === 'de' ? 'btn-primary' : 'btn-light'"
                      @click="currentTitleLang = 'de'"
                    >DE</button>
                    <button
                      type="button"
                      class="btn"
                      :class="currentTitleLang === 'fr' ? 'btn-primary' : 'btn-light'"
                      @click="currentTitleLang = 'fr'"
                    >FR</button>
                    <button
                      type="button"
                      class="btn"
                      :class="currentTitleLang === 'it' ? 'btn-primary' : 'btn-light'"
                      @click="currentTitleLang = 'it'"
                    >IT</button>
                  </div>
                  <input
                    type="text"
                    class="form-control"
                    v-model="corpusData.meta.swissubase.datasetTitle[currentTitleLang]"
                    id="swissubase-dataset-title"
                  />
                </div>
              </div>
              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">{{ $t('modal-swissubase-dataset-description') }}</label>
                  <textarea
                    class="form-control textarea-110"
                    :placeholder="`SWISSUbase ${$t('modal-swissubase-dataset-description')}`"
                    v-model="corpusData.meta.swissubase.datasetDescription"
                    id="swissubase-dataset-description"
                  ></textarea>
                </div>
              </div>
              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">{{ $t('modal-swissubase-dateset-documentation-remarks') }}</label>
                  <textarea
                    class="form-control textarea-110"
                    :placeholder="`SWISSUbase ${$t('modal-swissubase-dateset-documentation-remarks')}`"
                    v-model="corpusData.meta.swissubase.documentationRemarks"
                    id="swissubase-documentation-remarks"
                  ></textarea>
                </div>
              </div>
              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">
                    {{ $t('modal-swissubase-dataset-version-note') }}
                    <sup><FontAwesomeIcon :icon="['fas', 'circle']" class="circle-required" /></sup>
                  </label>
                  <textarea
                    class="form-control textarea-110"
                    :placeholder="`SWISSUbase ${$t('modal-swissubase-dataset-version-note')}`"
                    v-model="corpusData.meta.swissubase.versionNote"
                    id="swissubase-version-note"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>

          <div
            class="tab-pane fade pt-3"
            :class="{ active: activeSwissUbaseTab === 'resource', show: activeSwissUbaseTab === 'resource' }"
            id="nav-swissubase-resource"
            role="tabpanel"
            aria-labelledby="nav-swissubase-resource-tab"
          >
            <div class="row">
              <div class="col-6">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">{{ $t('modal-swissubase-resource-type') }}</label>
                  <select
                    class="form-select"
                    v-model="corpusData.meta.swissubase.resourceType"
                    id="swissubase-resource-type"
                  >
                    <option v-for="corpusType in corporaTypes" :key="corpusType.id" :value="corpusType.id">
                      {{ corpusType.name }}
                    </option>
                  </select>
                </div>
              </div>

              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">
                    {{ $t('modal-swissubase-resource-description') }}
                    <sup><FontAwesomeIcon :icon="['fas', 'circle']" class="circle-required" /></sup>
                  </label>
                  <textarea
                    class="form-control textarea-110"
                    :placeholder="`${$t('modal-swissubase-resource-description')}`"
                    v-model="corpusData.meta.swissubase.resourceDescription"
                    id="swissubase-resource-description"
                  ></textarea>
                </div>
              </div>

              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">
                    {{ $t('modal-swissubase-resource-keywords') }}
                    <sup><FontAwesomeIcon :icon="['fas', 'circle']" class="circle-required" /></sup>
                  </label>
                  <textarea
                    class="form-control textarea-110"
                    :placeholder="`${$t('modal-swissubase-resource-keywords')}`"
                    v-model="corpusData.meta.swissubase.keywords"
                    id="swissubase-resource-keywords"
                  ></textarea>
                </div>
              </div>

              <div class="col-12">
                <div class="mb-3">
                  <label for="corpus-name" class="form-label">{{ $t('modal-swissubase-resource-validation-information') }}</label>
                  <textarea
                    class="form-control textarea-110"
                    :placeholder="`${$t('modal-swissubase-resource-validation-information')}`"
                    v-model="corpusData.meta.swissubase.validationInformation"
                    id="swissubase-resource-validation-information"
                  ></textarea>
                </div>
              </div>
            </div>
          </div>
        </div>

        <hr>

        <div class="row mt-2">
          <div class="col-12">
            <p><small>
              <FontAwesomeIcon :icon="['fas', 'circle']" class="mb-1 circle-required" />
              {{ $t('common-mandatory-fields') }}</small>
            </p>
            <div class="form-check mb-3">
              <input
                class="form-check-input"
                v-model="SWISSUbaseSubmissionCheck"
                type="checkbox"
                id="swissubase-confirmation"
                :disabled="!SWISSUbaseSubmissionFieldsCheck"
              />
              <label class="form-check-label" for="swissubase-confirmation">
                {{ $t('modal-swissubase-confirm-text') }}
              </label>
              <div id="swissubase-confirmation-help" v-if="!SWISSUbaseSubmissionFieldsCheck" class="form-text">
                {{ $t('modal-swissubase-confirm-info') }}
              </div>
            </div>
            <button type="button" class="btn btn-primary" @click="submitSWISSUbase" :disabled="isSWISSUbaseSubmissionDisabled">
              {{ $t('modal-swissubase-submit-button') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div
      class="tab-pane fade pt-3"
      :class="{ active: activeMainTab === 'group', show: activeMainTab === 'group' }"
      id="nav-group"
      role="tabpanel" aria-labelledby="nav-group-tab"
      v-if="isSuperAdmin"
    >
      <div class="row">
        <div class="col-6">
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
.textarea-110 {
  height: 110px;
}
.circle-required {
  color: #ff6600;
  font-size: 6px;
}
#nav-group {
  margin-bottom: 5em;
}
</style>

<script>
import { mapState } from "pinia";
import { useCorpusStore } from "@/stores/corpusStore";
import { useSWISSUbaseStore } from "@/stores/swissubaseStore";
import { getUserLocale } from "@/fluent";
import Utils from "@/utils";
import { useUserStore } from "@/stores/userStore";

export default {
  name: "CorpusMetdataEdit",
  props: ["corpus", "allProjects"],
  data() {
    let corpusData = { ...this.corpus } || {};
    if (corpusData.meta && !corpusData.meta.language) {
      // Default to undefined language
      corpusData.meta.language = "und";
    }
    if (corpusData.meta && !corpusData.meta.swissubase) {
      // Initialize swissubase metadata if not present
      corpusData.meta.swissubase = {
        projectId: '',
        datasetTitle: {
          en: '',
          de: '',
          fr: '',
          it: '',
        },
        datasetLanguage: 'en',
        datasetDescription: '',
        documentationRemarks: '',
        versionNote: '',
        requestDoi: false,
        resourceDescription: '',
        resourceType: 1,
        validationInformation: '',
        keywords: '',
        apiAccessToken: '',
        licence: null,
      }
    }
    let userLicense = "";
    try {
      userLicense = atob(this.corpus.meta.userLicense);
    } catch {
      userLicense = this.corpus.meta.userLicense || "";
    }
    if (corpusData.projects.length == 0)
      corpusData.projects.push(corpusData.project_id);
    const ownProjects = this.allProjects ? this.allProjects.filter(p=>corpusData.projects.includes(p.id)) : [];
    return {
      activeMainTab: "metadata",
      activeSwissUbaseTab: "project",
      userLicense: userLicense,
      corpusData: corpusData,
      isSuperAdmin: useUserStore().isSuperAdmin,
      projects: ownProjects,
      SWISSUbaseSubmissionCheck: false,
      currentTitleLang: 'en', // Default language for dataset title
    }
  },
  computed: {
    ...mapState(useCorpusStore, {
      corpusLicenses: "licenses",
      corpusLanguages: "languages",
    }),
    ...mapState(useSWISSUbaseStore, {
      swissUBaseLicenses: "licenses",
      swissUBaseLanguages: "languages",
      corporaTypes: "corporaTypes",
      checkAccessTokenResponse: "checkAccessTokenResponse",
    }),
    selectedLanguage: {
      get() {
        return this.corpusLanguages.find(l => l.value === this.corpusData.meta.language)
      },
      set(val) {
        this.corpusData.meta.language = val.value
      }
    },
    SWISSUbaseSubmissionFieldsCheck() {
      return this.corpusData.meta.swissubase.apiAccessToken &&
             this.corpusData.meta.swissubase.projectId &&
             this.corpusData.meta.swissubase.datasetTitle &&
             this.corpusData.meta.swissubase.versionNote &&
             this.corpusData.meta.swissubase.resourceType &&
             this.corpusData.meta.swissubase.resourceDescription.length > 0 &&
             this.corpusData.meta.swissubase.keywords.length > 0 &&
             (this.checkAccessTokenResponse && this.checkAccessTokenResponse.status == 200);
    },
    isSWISSUbaseSubmissionDisabled() {
      return !(this.SWISSUbaseSubmissionCheck && this.SWISSUbaseSubmissionFieldsCheck == 1)
    },
    isDisabled (){
      return this.corpusData && this.corpusData.meta && this.corpusData.meta.swissubase && this.corpusData.meta.swissubase.submittedOn
    },
    canCheckAPISWISSUbaseToken() {
      return this.corpusData.meta.swissubase.apiAccessToken && this.corpusData.meta.swissubase.projectId;
    },
  },
  methods: {
    corpusDataType: Utils.corpusDataType,
    getUserLocale: getUserLocale,
    submitSWISSUbase() {
      this.corpusData.meta.swissubase.submittedOn = new Date().toISOString();
      this.$emit("submitSWISSUbase")
    },
    checkSWISSUbaseAPI() {
      useSWISSUbaseStore().checkAccessToken(
        this.corpusData.meta.swissubase.apiAccessToken,
        this.corpusData.meta.swissubase.projectId,
        this.corpusData.corpus_id
      )
    },
    subAttributes(attribute) {
      if (attribute.keys && attribute.keys instanceof Object)
        return attribute.keys;
      if (attribute.ref && this.corpus.globalAttributes && attribute.ref in this.corpus.globalAttributes)
        return this.corpus.globalAttributes[attribute.ref].keys || {};
      return {};
    },
    getAttributes(layerAttributes) {
      const ret = {};
      let meta = {};
      for (let [k,v] of Object.entries(layerAttributes || {})) {
        if (k == "meta" && typeof(v) != "string") {
          meta = v;
          continue;
        }
        ret[k] = {
          isMeta: 0,
          sub: this.subAttributes(v),
          global: (
            "ref" in v && v.ref in (this.corpus.globalAttributes || {})
            ? v.ref
            : ""
          )
        };
      }
      for (let [k,v] of Object.entries(meta))
        ret[k] = {isMeta: 1, sub: this.subAttributes(v), global: false};
      console.log("return getAttributes", JSON.parse(JSON.stringify(ret)));
      return ret;
    }
  },
  mounted() {
    useSWISSUbaseStore().clearCheckReponse()
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
