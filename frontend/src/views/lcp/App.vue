<template>
  <div id="app-content">
    <nav class="navbar navbar-expand-lg bg-liri mb-3 fixed-top">
      <div class="container">
        <a class="navbar-brand" href="/">{{ $t('platform-general-short') }}</a>
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
                {{ $t('menu-home') }}
              </router-link>
            </li>
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
            <!-- <li class="nav-item">
              <router-link class="nav-link" to="/query-test">
                <FontAwesomeIcon :icon="['fas', 'circle-nodes']" class="me-1" />
                Query Test
              </router-link>
            </li> -->
          </ul>
          <ul class="navbar-nav ms-auto">
            <!-- <li>
              <multiselect
                v-model="language"
                @select="changeLanguage"
                :options="languageOptions"
                track-by="name"
                label="name"
                :searchable="false"
                :close-on-select="true"
                :show-labels="false"
                :allow-empty="false"
                placeholder="English"
                aria-label="Select a language"
                >
                </multiselect>
            </li> -->
            <li class="nav-item" v-if="debug">
              <span class="nav-link version-number">
                #{{ appVersion }}
              </span>
            </li>
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
            <li class="nav-item">
              <router-link
                v-if="userData && userData.user && userData.user.displayName"
                class="nav-link"
                to="/user"
              >
                <FontAwesomeIcon :icon="['fas', 'user']" class="me-1" />
              </router-link>
            </li>
          </ul>
        </div>
      </div>
    </nav>
    <router-view />
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
import { changeLocale, getUserLocale, availableLanguages } from "@/fluent";

import LoadingView from "@/components/LoadingView.vue";
import FooterView from "@/components/FooterView.vue";
import NotificationView from "@/components/NotificationView.vue";
import config from "@/config";

export default {
  name: "AppLCP",
  data() {
    console.log("Application version:", process.env.GIT_HASH)
    return {
      appVersion: process.env.GIT_HASH,
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
    }
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
  .navbar{
    max-width: 100vw;
  }

  .version-number {
    font-size: 80% !important;
    opacity: 0.75;
    margin-top: 2px;
  }
</style>
