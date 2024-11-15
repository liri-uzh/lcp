<template>
  <div id="app-content">
    <nav class="navbar navbar-expand-lg bg-liri mb-3 fixed-top">
      <div class="container">
        <a class="navbar-brand" href="/"><i>videoscope</i></a>
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
          </ul>
          <ul class="navbar-nav ms-auto">
            <li class="nav-item">
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
  name: "AppVideoscope",
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

/* videoscope colors */
nav.bg-liri {
  background-color: #622A7F;
}
* >>> .nav-tabs {
    --bs-nav-tabs-link-active-color: #fff;
    --bs-nav-tabs-link-active-bg: #622A7F;
    --bs-nav-tabs-link-active-border-color: #622A7F;
}
* >>> .nav-link {
    color: #622A7F;
}
* >>> .nav-link:hover {
    color: #4e1e66;
}
* >>> .navbar a:hover {
  color: #b390c5;
}
footer {
  background-color: #622A7F;
}
* >>> .alert-success {
  --bs-alert-bg: #ede7f0;
  --bs-alert-border-color: #e1d6e6;
}
* >>> .btn-primary {
  --bs-btn-bg: #622A7F;
  --bs-btn-border-color: #622A7F;
  --bs-btn-hover-bg: #7b4596;
  --bs-btn-hover-border-color: #7b4596;
  --bs-btn-active-bg: #54226d;
  --bs-btn-active-border-color: #54226d;
  --bs-btn-disabled-bg: #622A7F;
  --bs-btn-disabled-border-color: #622A7F;
}
* >>> .progress-bar {
  background-color: #622A7F;
}
* >>> span.action-button {
  background-color: #622A7F !important;
}
* >>> .page-link.active {
  background-color: #622A7F !important;
  border-color: #622A7F !important;
  color: #fff !important;
}
* >>> .page-link {
  color: #622A7F !important;
}
</style>
