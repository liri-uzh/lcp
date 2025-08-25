import { defineStore } from "pinia";
import httpApi from "@/httpApi";


export const useProjectStore = defineStore("projectData", {
  state: () => ({
  }),
  getters: {},
  actions: {
    async createApiKey(projectId) {
      let url = `/project/${projectId}/api/create`
      let response = await httpApi.post(url)
      this.queryData = await response.data;
      return this.queryData
    },
    async revokeApiKey(projectId, apiKeyId) {
      let url = `/project/${projectId}/api/${apiKeyId}/revoke`
      let response = await httpApi.post(url)
      this.queryData = await response.data;
      return this.queryData
    },
    async create(data) {
      let url = `/project`
      let response = await httpApi.post(url, data)
      this.queryData = await response.data;
      return this.queryData
    },
    async update(data) {
      let url = `/project/${data.id}`
      let response = await httpApi.post(url, data)
      this.queryData = await response.data;
      return this.queryData
    },
    async inviteUsers(projectId, emails, inviteByLink) {
      let url = `/project/${projectId}/users/invite`
      let response = await httpApi.post(url, {emails: emails, byLink: inviteByLink})
      this.queryData = await response.data;
      return this.queryData
    },
    async removeInvitation(projectId, invitationId) {
      let url = `/project/${projectId}/users/invitation/${invitationId}`
      let response = await httpApi.delete(url)
      let data = await response.data;
      return data
    },
    async getUsers(projectId) {
      let url = `/project/${projectId}/users`
      let response = await httpApi.get(url)
      let data = await response.data;
      return data
    },
    async updateUser(projectId, userId, data) {
      let url = `/project/${projectId}/user/${userId}/update`
      let response = await httpApi.post(url, data)
      return await response.data;
    },
  },
});
