<template>
  <div class="row" id="corpus-details-modal">
    <div class="col-12 col-lg-5">
      <div class="title mb-0" v-if="hasAccessToCorpus(corpusModal, userData)">
        <span>{{ corpusModal.meta.name }}</span>
        <br>
        <a
          :href="appLinks['catchphrase']"
          target="_blank"
          class="btn btn-sm btn-primary me-1 btn-catchphrase"
          @click="openQueryWithCorpus(corpusModal, 'catchphrase')"
        >
          <FontAwesomeIcon :icon="['fas', 'font']" class="me-2" />
          <i>{{ $t('platform-catchphrase') }}</i>
        </a>

        <a
          :href="appLinks['soundscript']"
          target="_blank"
          class="btn btn-sm btn-primary me-1 btn-soundscript"
          @click="openQueryWithCorpus(corpusModal, 'soundscript')"
          v-if="['audio', 'video'].includes(corpusDataType(corpusModal))"
        >
          <FontAwesomeIcon :icon="['fas', 'music']" class="me-2" />
          <i>{{ $t('platform-soundscript') }}</i>
        </a>

        <a
          :href="appLinks['videoscope']"
          target="_blank"
          class="btn btn-sm btn-primary me-1 btn-videoscope"
          @click="openQueryWithCorpus(corpusModal, 'videoscope')"
          v-if="['video'].includes(corpusDataType(corpusModal))"
        >
          <FontAwesomeIcon :icon="['fas', 'video']" class="me-2" />
          <i>{{ $t('platform-videoscope') }}</i>
        </a>
      </div>
      <p class="authors mb-0" v-if="corpusModal.meta.authors">
        <em>{{ corpusModal.meta.authors }}</em>
      </p>
      <p class="description mt-3">
        {{ corpusModal.meta.corpusDescription }}
      </p>
      <p class="word-count mb-0">
        {{$t('modal-details-count')}}:
        <b>{{
          calculateSum(
            Object.entries(corpusModal.token_counts).filter(kv=>kv[0].endsWith("0")).map(kv=>kv[1])
          ).toLocaleString("de-DE")
        }}</b>
      </p>
      <p class="word-count mb-0">
        {{$t('modal-details-revison')}}: {{ corpusModal.meta.revision }}
      </p>
      <p class="word-count mb-0">
        {{$t('modal-details-url')}}:
        <a :href="getURLWithProtocol(corpusModal.meta.url)" target="_blank">{{
          corpusModal.meta.url
        }}</a>
      </p>
      <p class="word-count mb-0">
        {{$t('modal-details-description')}}: {{ corpusModal.description }}
      </p>
      <p class ="word-count mb-0" v-if="corpusModal.meta.language && !(corpusModal.partitions)">
        {{$t('modal-details-language')}}: {{ corpusModal.meta.language }}
      </p>
      <span v-if="corpusModal.partitions">
        <p class="word-count" v-if="corpusModal.partitions">
          {{$t('modal-details-partitions')}}: {{ corpusModal.partitions.values.join(", ") }}
        </p>
        <div class="" v-for="partition in corpusModal.partitions.values" :key="partition">
          <p class="text-bold">{{ partition.toUpperCase() }}</p>
          <p class="word-count">
            {{$t('modal-details-segments')}}:
            {{
              corpusModal.mapping.layer.Segment.partitions[
                partition
              ].prepared.columnHeaders.join(", ")
            }}
          </p>
          <!-- <p class="word-count">
            Segments:
            {{ corpusModal.mapping.layer.Segment.partitions[partition].prepared.columnHeaders.join(", ") }}
          </p> -->
        </div>
      </span>
      <p class="word-count mb-0 mt-2" v-if="license">
        {{ $t('modal-details-license') }}:
        <span v-if="license.tag == 'user-defined'">
          <b>{{ $t('modal-details-user-license') }}</b><br>
          {{ getUserLicense() }}
        </span>
        <span v-else>
          <a :href="license.url" target="_blank">
            <img :src="`/licenses/${license.tag}.png`" :alt="license.name" class="license-img me-1" />
            <FontAwesomeIcon :icon="['fas', 'link']" />
            {{ license.name }}
          </a>
        </span>
      </p>
    </div>
    <div class="col-12 col-lg-7">
      <!-- <CorpusGraphViewNew :corpus="corpusModal" /> -->
      <CorpusGraphView :corpus="corpusModal" v-if="showGraph" />
    </div>
  </div>
</template>

<style scoped>
  .description {
    font-size: 90%;
    height: 108px;
    overflow: hidden;
  }

  .word-count {
    font-size: 80%;
  }

  .license-img {
    width: 100px;
  }
</style>

<script>
  import { mapState } from "pinia";
  import { useCorpusStore } from "@/stores/corpusStore";
  import { useUserStore } from "@/stores/userStore";

  // import CorpusGraphViewNew from "@/components/CorpusGraphViewNew.vue";
  import CorpusGraphView from "@/components/CorpusGraphView.vue";

  import router from "@/router";
  import config from "@/config";
  import Utils from "@/utils";

  export default {
    name: "CorpusDetailsModal",
    props: ["corpusModal"],
    data: function () {
      return {
        showGraph: false,
        appLinks: config.appLinks,
        license: this.corpusModal.meta.license
          ? useCorpusStore().getLicenseByTag((this.corpusModal.meta.license))
          : null,
      }
    },
    methods: {
      getUserLicense() {
        if (this.corpusModal.meta.userLicense) {
          let license = "";
          try {
            license = atob(this.corpusModal.meta.userLicense);
          } catch {
            license = this.corpusModal.meta.userLicense;
          }
          return license;
        }
        return "";
      },
      corpusDataType: Utils.corpusDataType,
      getURLWithProtocol: Utils.getURLWithProtocol,
      hasAccessToCorpus: Utils.hasAccessToCorpus,
      calculateSum: Utils.calculateSum,
      openQueryWithCorpus(corpus) {
        if (this.hasAccessToCorpus(corpus, this.userData)) {
          router.push(`/query/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`);
        }
      },
    },
    computed: {
      ...mapState(useUserStore, ["userData"]),
    },
    components: {
      // CorpusGraphViewNew,
      CorpusGraphView,
    },
    mounted() {
      setTimeout(() => {
        this.showGraph = true;
      }, 500)
    },
  }
</script>
