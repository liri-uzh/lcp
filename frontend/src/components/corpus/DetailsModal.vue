<template>
  <div class="row" id="corpus-details-modal">
    <div class="col-5">
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
          <i>catchphrase</i>
        </a>

        <a
          :href="appLinks['soundscript']"
          target="_blank"
          class="btn btn-sm btn-primary me-1 btn-soundscript"
          @click="openQueryWithCorpus(corpusModal, 'soundscript')"
          v-if="['audio', 'video'].includes(corpusDataType(corpusModal))"
        >
          <FontAwesomeIcon :icon="['fas', 'music']" class="me-2" />
          <i>soundscript</i>
        </a>

        <a
          :href="appLinks['videoscope']"
          target="_blank"
          class="btn btn-sm btn-primary me-1 btn-videoscope"
          @click="openQueryWithCorpus(corpusModal, 'videoscope')"
          v-if="['video'].includes(corpusDataType(corpusModal))"
        >
          <FontAwesomeIcon :icon="['fas', 'video']" class="me-2" />
          <i>videoscope</i>
        </a>
      </div>
      <!-- <p class="author mb-0" v-if="corpusModal.meta.author">
        {{ corpusModal.meta.author }}
      </p> -->
      <p class="description mt-3">
        {{ corpusModal.meta.corpusDescription }}
      </p>
      <p class="word-count mb-0">
        Word count:
        <b>{{
          calculateSum(
            Object.values(corpusModal.token_counts)
          ).toLocaleString("de-DE")
        }}</b>
      </p>
      <p class="word-count mb-0">
        Revison: {{ corpusModal.meta.revision }}
      </p>
      <p class="word-count mb-0">
        URL:
        <a :href="getURLWithProtocol(corpusModal.meta.url)" target="_blank">{{
          corpusModal.meta.url
        }}</a>
      </p>
      <p class="word-count mb-0">
        Description: {{ corpusModal.description }}
      </p>
      <span v-if="corpusModal.partitions">
        <p class="word-count" v-if="corpusModal.partitions">
          Partitions: {{ corpusModal.partitions.values.join(", ") }}
        </p>
        <div class="" v-for="partition in corpusModal.partitions.values" :key="partition">
          <p class="text-bold">{{ partition.toUpperCase() }}</p>
          <p class="word-count">
            Segments:
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
      <p class="word-count mb-0" v-if="licence">
        License:
        <span v-if="licence.tag == 'user-defined'">
          User defined: {{ corpusModal.meta.userLicense }}
        </span>
        <span v-else>
          <a :href="licence.url" target="_blank">
            <img :src="`/licenses/${licence.tag}.png`" :alt="licence.name" class="license-img me-1" />
            <FontAwesomeIcon :icon="['fas', 'link']" />
            {{ licence.name }}
          </a>
        </span>
      </p>
    </div>
    <div class="col-7">
      <!-- <CorpusGraphViewNew :corpus="corpusModal" /> -->
      <CorpusGraphView :corpus="corpusModal" v-if="showGraph" />
    </div>
  </div>
</template>

<style>
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
        licence: this.corpusModal.meta.license
          ? useCorpusStore().getLicenseByTag((this.corpusModal.meta.license))
          : null,
      }
    },
    methods: {
      corpusDataType: Utils.corpusDataType,
      getURLWithProtocol: Utils.getURLWithProtocol,
      hasAccessToCorpus: Utils.hasAccessToCorpus,
      calculateSum: Utils.calculateSum,
      openQueryWithCorpus(corpus, type) {
        if (this.hasAccessToCorpus(corpus, this.userData)) {
          if (type == "videoscope") {
            router.push(`/player/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`);
          } else {
            router.push(`/query/${corpus.meta.id}/${Utils.slugify(corpus.shortname)}`);
          }
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
