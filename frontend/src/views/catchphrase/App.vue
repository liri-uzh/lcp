<template>
  <div id="app-content">
    <nav class="navbar navbar-expand-lg bg-liri mb-3 fixed-top">
      <div class="container">
        <a class="navbar-brand" href="/">
          <FontAwesomeIcon :icon="['fas', 'house']" class="me-1" />
          {{ $t('platform-catchphrase') }}
        </a>
        <ul>
          <li><a :href="appLinks['soundscript']" class="nav-link">{{ $t('platform-soundscript') }}</a></li>
          <li><a :href="appLinks['videoscope']" class="nav-link">{{ $t('platform-videoscope') }}</a></li>
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
            <!-- <li class="nav-item">
              <router-link class="nav-link" to="/query-test">
                <FontAwesomeIcon :icon="['fas', 'circle-nodes']" class="me-1" />
                Query Test
              </router-link>
            </li> -->
          </ul>
          <ul class="navbar-nav ms-auto">
            <!-- <li>
              <multiselect v-model="language" @select="changeLanguage" :options="languageOptions" track-by="name" label="name" :searchable="false" :close-on-select="true" :show-labels="false" :allow-empty="false"
                 placeholder="English" aria-label="Select a language">
                </multiselect>
            </li> -->
            <li class="nav-item" v-if="debug">
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
                {{`${$t('platform-general-short')} ${$t('menu-home')}`}}
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
import Utils from "@/utils";
import { useNotificationStore } from "@/stores/notificationStore";

export default {
  name: "AppCatchphrase",
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
    useUserStore().fetchUserData().then(()=>{
      if (!this.userData.pending_invites) return;
      window.copyEmails = []
      for (let {title, corpus, emails} of Object.values(this.userData.pending_invites)) {
        useNotificationStore().add({
          text: `
            The following email addresses asked to be invited to the corpus ${corpus.name} in the group ${title}:<br>
            ${emails.join("<br>")}<br>
            <input type="button" value="Copy emails" onclick="copyEmails[${window.copyEmails.length}]()">
          `,
          type: "dark",
          timeout: 30
        });
        window.copyEmails.push(()=>Utils.copy(emails.join(", ")));
      }
    });
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
  background-color: #2a7f62;
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
</style>
