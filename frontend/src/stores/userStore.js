import { defineStore } from "pinia";
import httpApi from "@/httpApi";
import Utils from '@/utils';

// Get roomId from localStorage
let roomId = localStorage.getItem("roomId");
if (!roomId) {
  roomId = Utils.uuidv4()
  localStorage.setItem("roomId", roomId);
}
roomId = Utils.uuidv4()

export const useUserStore = defineStore("userData", {
  state: () => ({
    userData: {
      publicProfiles: {},
      subscription: {subscriptions: []},
      termsOfUse: {},
      user: {},
    },
    roomId: roomId,
    projects: [],
    dataFetched: false,
    debug: false,
    _ready: null,
  }),
  getters: {
    isSuperAdmin() {
      return this.userData.user.superAdmin == true;
    }
  },
  actions: {
    async fetchUserData() {
      return httpApi.get(`/settings`).then((r) => {
        this.userData = {
          publicProfiles: {},
          subscription: {subscriptions: []},
          termsOfUse: {},
          user: {},
          ...(r.data || {})
        };
        this.debug = r.data.debug
        if (this.userData.publicProfiles.length) {
          this.projects = this.userData.publicProfiles
        }
        this.userData.subscription.subscriptions.forEach(subscription => {
          subscription.profiles.forEach(profile => {
            this.projects.push(profile)
          })
        })

        // Terms of use
        if (this.userData.termsOfUse.needToAccept === true) {
          window.location.href = this.userData.termsOfUse.url;
        }

        // When no user, generate random id
        if (this.userData.user.id === undefined) {
          this.userData.user = {"id": Utils.uuidv4(), "anon": true}
        }
        this.dataFetched = true
      });
    },
    async checkLoaded () {
      if (this.dataFetched) return
      if (!this._ready) this._ready = this.fetchUserData().finally(() => (this._ready = null))
      return this._ready
    },
  },
});
