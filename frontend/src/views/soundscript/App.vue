<template>
  <div id="app-content">
    <nav class="navbar navbar-expand-lg bg-liri mb-3 fixed-top">
      <div class="container">
        <a class="navbar-brand" href="/"><i>soundscript</i></a>
        <button
          class="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarNav"
          aria-controls="navbarNav"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
          <ul class="navbar-nav">
            <li class="nav-item">
              <router-link class="nav-link" to="/">
                <FontAwesomeIcon :icon="['fas', 'house']" class="me-1" />
                Home
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/query">
                <FontAwesomeIcon
                  :icon="['fas', 'magnifying-glass']"
                  class="me-1"
                />
                Query
              </router-link>
            </li>
            <li class="nav-item">
              <a href="https://lcp.linguistik.uzh.ch/manual" target="_blank" class="nav-link">
                <FontAwesomeIcon
                  :icon="['fas', 'circle-question']"
                  class="me-1"
                />
                Manual
              </a>
            </li>
            <!-- <li class="nav-item">
              <router-link class="nav-link" to="/query-test">
                <FontAwesomeIcon :icon="['fas', 'circle-nodes']" class="me-1" />
                Query Test
              </router-link>
            </li> -->
            <!-- <li class="nav-item">
              <router-link class="nav-link" to="/player">
                <FontAwesomeIcon
                  :icon="['fas', 'video']"
                  class="me-1"
                />
                Player
              </router-link>
            </li> -->
          </ul>
          <ul class="navbar-nav ms-auto">
            <li class="nav-item" v-if="debug">
              <span class="nav-link version-number">
                #{{ appVersion }}
              </span>
            </li>
            <li class="nav-item">
              <a :href="appLinks['lcphome']" target="_blank" class="nav-link">
                <FontAwesomeIcon :icon="['fas', 'database']" class="me-2" />
                LCP Home
              </a>
            </li>
            <li class="nav-item">
              <a
                v-if="userData && userData.user && userData.user.displayName"
                class="nav-link"
                href="/Shibboleth.sso/Logout"
              >
                <FontAwesomeIcon :icon="['fas', 'power-off']" class="me-1" />
                Logout
                <small>({{ userData.user.displayName }})</small>
              </a>
              <a class="nav-link" href="/login" v-else>
                <FontAwesomeIcon :icon="['fas', 'user']" class="me-1" />
                Login
              </a>
            </li>
          </ul>
        </div>
      </div>
    </nav>
    <router-view class="app-content-box" />
    <FooterView />
    <NotificationView />
    <LoadingView />
    <div class="beta-flag">BETA</div>
  </div>
</template>

<script>
import { mapState } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useCorpusStore } from "@/stores/corpusStore";
import { useWsStore } from "@/stores/wsStore";

import LoadingView from "@/components/LoadingView.vue";
import FooterView from "@/components/FooterView.vue";
import NotificationView from "@/components/NotificationView.vue";
import config from "@/config";

export default {
  name: "AppSoundscript",
  data() {
    return {
      appVersion: process.env.GIT_HASH,
      appLinks: config.appLinks,
    }
  },
  mounted() {
    document.title = config.appName;
    useUserStore().fetchUserData();
    useCorpusStore().fetchCorpora();
  },
  unmounted() {
    useWsStore().sendLeft();
  },
  methods: {
    addActionClass(e) {
      e.currentTarget.querySelector(".nav-link").classList.add("active");
    },
  },
  components: {
    LoadingView,
    NotificationView,
    FooterView,
  },
  computed: {
    ...mapState(useUserStore, ["userData", "roomId", "debug"]),
  },
  watch: {
    userData() {
      useWsStore().connectToRoom(this.$socket, this.userData.user.id, this.roomId)
    },
  },
};
</script>

<style scoped>
.version-number {
  font-size: 80% !important;
  opacity: 0.75;
  margin-top: 2px;
}
/* soundscript colors */
nav.bg-liri {
  background-color: #0059be;
}
* >>> .nav-tabs {
    --bs-nav-tabs-link-active-color: #fff;
    --bs-nav-tabs-link-active-bg: #0059be;
    --bs-nav-tabs-link-active-border-color: #0059be;
}
* >>> .nav-link {
    color: #0059be;
}
* >>> .nav-link:hover {
    color: #00489a;
}
* >>> .navbar a:hover {
  color: #8fa4bd;
}
footer {
  background-color: #0059be;
}
* >>> .alert-success {
  --bs-alert-bg: #e8eff8;
  --bs-alert-border-color: #d7e2f0;
}

* >>> .btn-primary {
  --bs-btn-bg: #0059be;
  --bs-btn-border-color: #0059be;
  --bs-btn-hover-bg: #0152af;
  --bs-btn-hover-border-color: #0152af;
  --bs-btn-active-bg: #00489a;
  --bs-btn-active-border-color: #00489a;
  --bs-btn-disabled-bg: #0059be;
  --bs-btn-disabled-border-color: #0059be;
}
* >>> .progress-bar {
  background-color: #0059be;
}
* >>> span.action-button {
  background-color: #0059be !important;
}
* >>> .page-link.active {
  background-color: #0059be !important;
  border-color: #0059be !important;
  color: #fff !important;
}
* >>> .page-link {
  color: #0059be !important;
}
</style>
