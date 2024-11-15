<template>
  <div id="corpus-metadata-edit">
    <div class="row">
      <div class="col-6">
        <div class="mb-3">
          <label for="corpus-name" class="form-label">Name</label>
          <input type="text" class="form-control" v-model="corpusData.meta.name" id="corpus-name" maxlength="50" />
        </div>
      </div>
      <div class="col-6">
        <div class="mb-3">
          <label for="corpus-source" class="form-label">Source</label>
          <input type="text" class="form-control" v-model="corpusData.meta.source" id="corpus-source" />
        </div>
      </div>
    </div>
    <div class="row">
      <div class="col-12">
        <div class="mb-3">
          <label for="corpus-authors" class="form-label">Authors</label>
          <input type="text" class="form-control" v-model="corpusData.meta.authors" id="corpus-authors" />
        </div>
      </div>
    </div>
    <div class="row">
      <div class="col-6">
        <div class="mb-3">
          <label for="corpus-institution" class="form-label">Provider/Institution</label>
          <input type="text" class="form-control" v-model="corpusData.meta.institution" id="corpus-institution" />
        </div>
      </div>
      <div class="col-6">
        <div class="mb-3">
          <label for="corpus-revision" class="form-label">Revision</label>
          <input type="text" class="form-control" v-model="corpusData.meta.revision" id="corpus-revision" />
        </div>
      </div>
    </div>
    <div class="row">
      <div class="col-7">
        <div class="mb-3">
          <label for="corpus-license" class="form-label">Data type: <b>{{ corpusDataType(corpusData) }}</b></label>
        </div>
      </div>
    </div>
    <div class="row">
      <div class="col-12">
        <div class="mb-3">
          <label for="corpus-description" class="form-label">Description</label>
          <textarea class="form-control" placeholder="Corpora description" v-model="corpusData.meta.corpusDescription"
            id="corpus-description" style="height: 100px"></textarea>
        </div>
      </div>
    </div>
    <div class="row">
      <div class="col-12">
        <div class="mb-3">
          <label for="corpus-license" class="form-label">License</label>
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
                  User defined
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
          <label for="corpus-description" class="form-label">User defined licence</label>
          <textarea class="form-control" placeholder="User defined licence" v-model="userLicense"
            id="user-defined-licence" style="height: 100px"></textarea>
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
</style>

<script>
import { mapState } from "pinia";
import { useCorpusStore } from "@/stores/corpusStore";
import Utils from "@/utils";

export default {
  name: "CorpusMetdataEdit",
  props: ["corpus"],
  data() {
    return {
      userLicense: this.corpus.meta && this.corpus.meta.userLicense ? atob(this.corpus.meta.userLicense) : "",
      corpusData: { ...this.corpus },
    }
  },
  computed: {
    ...mapState(useCorpusStore, ["licenses"]),
  },
  methods: {
    corpusDataType: Utils.corpusDataType,
  },
  watch: {
    userLicense() {
      this.corpusData.meta.userLicense = btoa(this.userLicense);
    },
  },
}
</script>
