<template>
  <div id="app-content">
    <nav class="navbar navbar-expand-lg bg-liri mb-3 fixed-top">
      <div class="container">
        <a class="navbar-brand" href="/">
          <FontAwesomeIcon :icon="['fas', 'house']" class="me-1" />
          {{ $t('platform-videoscope') }}
        </a>
        <ul>
          <li><a :href="appLinks['catchphrase']" class="nav-link">{{ $t('platform-catchphrase') }}</a></li>
          <li><a :href="appLinks['soundscript']" class="nav-link">{{ $t('platform-soundscript') }}</a></li>
        </ul>
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
            <!-- <li class="nav-item">
              <router-link class="nav-link" to="/">
                <FontAwesomeIcon :icon="['fas', 'house']" class="me-1" />
                {{ $t('menu-home') }}
              </router-link>
            </li> -->
            <!-- <li class="nav-item">
              <router-link class="nav-link" to="/query">
                <FontAwesomeIcon
                  :icon="['fas', 'magnifying-glass']"
                  class="me-1"
                />
                {{ $t('menu-query') }}
              </router-link>
            </li> -->
            <li class="nav-item">
              <a href="https://lcp.linguistik.uzh.ch/manual" target="_blank" class="nav-link">
                <FontAwesomeIcon
                  :icon="['fas', 'circle-question']"
                  class="me-1"
                />
                {{ $t('menu-manual') }}
              </a>
            </li>
          </ul>
          <ul class="navbar-nav ms-auto">
            <!-- <li>
              <multiselect v-model="language" @select="changeLanguage" :options="languageOptions" track-by="name" label="name" :searchable="false" :close-on-select="true" :show-labels="false" :allow-empty="false"
                 placeholder="English" aria-label="Select a language">
                </multiselect>
            </li> -->
            <li class="nav-item">
              <span class="nav-link version-number">
                #{{ appVersion }}
              </span>
            </li>
            <li class="nav-item export" :title="$t('common-export')">
              <!-- <FontAwesomeIcon :icon="['fas', 'gauge']" class="me-2" /> -->
               <a class="nav-link" @click="openExportsModal">
                <FontAwesomeIcon :icon="['fas', 'download']" class="me-2" />
               </a>
              <ExportView />
            </li>
            <!-- <li class="nav-item">
              <a :href="appLinks['lcphome']" target="_blank" class="nav-link">
                <FontAwesomeIcon :icon="['fas', 'database']" class="me-2" />
                {{ `${$t('platform-general-short')} ${$t('menu-home')}` }}
              </a>
            </li> -->
            <li class="nav-item">
              <a
                v-if="userData && userData.user && userData.user.displayName"
                class="nav-link"
                href="/Shibboleth.sso/Logout"
              >
                <FontAwesomeIcon :icon="['fas', 'power-off']" class="me-1" />
                {{ $t('common-logout') }}
                <small>({{ userData.user.displayName }})</small>
              </a>
              <a class="nav-link" href="/login" v-else>
                <FontAwesomeIcon :icon="['fas', 'user']" class="me-1" />
                {{ $t('common-login') }}
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
import { Modal } from "bootstrap";
import { useUserStore } from "@/stores/userStore";
import { useCorpusStore } from "@/stores/corpusStore";
import { useWsStore } from "@/stores/wsStore";
import { changeLocale, getUserLocale, availableLanguages } from "@/fluent";

import ExportView from "@/components/ExportView.vue";
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
      language: getUserLocale(),
      languageOptions: availableLanguages,
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
    changeLanguage(selectedOption){
      changeLocale(selectedOption);

      // This is necessary in order to correctly load the language bundle
      if (this.$route.path === '/') {
        // Reload the page if already on the homepage
        this.$router.go();
      } else {
        // Otherwise, navigate to the homepage
        this.$router.push('/');
      }
    },
    openExportsModal() {
      let modal = new Modal(document.getElementById('exportsModal'));
      modal.show();
      setTimeout(
        ()=>document.getElementById("app-content").append(document.getElementById('exportsModal')),
        50
      );
    },
  },
  components: {
    ExportView,
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
.navbar-brand {
  font-style: italic;
}
a.navbar-brand + ul {
  display: none;
  position: absolute;
  padding: 0.5em;
  transform: translate(0.5em, 3em);
  color: white;
  background-color: #622A7F;
  list-style: none;
}
a.navbar-brand:hover + ul, a.navbar-brand + ul:hover {
  display: block;
}
a.navbar-brand + ul li a {
  color: white;
  text-decoration: none;
}
a.navbar-brand + ul li a:hover {
  font-weight: bold;
}
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
