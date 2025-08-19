<template>
  <div class="project-edit">
    <div class="container">
      <div class="row">
        <div class="col-12">
          <nav class="tabsnav">
            <div class="nav nav-tabs tabs-list" id="nav-tab" ref="tabslist" role="tablist">
              <button
                class="nav-link"
                :class="currentTab == 'metadata' ? 'active' : ''"
                id="nav-edit-metadata-tab"
                data-bs-toggle="tab"
                data-bs-target="#nav-edit-metadata"
                type="button"
                role="tab"
                ref="navEditMetadataTab"
                aria-controls="nav-edit-metadata"
                aria-selected="true"
                @click="currentTab = 'metadata'"
              >
                {{ $t('modal-project-tab-metadata') }}
              </button>
              <button
                class="nav-link"
                :class="currentTab == 'permissions' ? 'active' : ''"
                id="nav-edit-permissions-tab"
                data-bs-toggle="tab"
                data-bs-target="#nav-edit-permissions"
                type="button"
                role="tab"
                aria-controls="nav-edit-permissions"
                aria-selected="true"
                @click="currentTab = 'permissions'"
              >
                {{ $t('modal-project-tab-permissions') }}
              </button>
              <button
                class="nav-link"
                :class="currentTab == 'api' ? 'active' : ''"
                id="nav-edit-api-tab"
                data-bs-toggle="tab"
                data-bs-target="#nav-edit-api"
                type="button"
                role="tab"
                aria-controls="nav-edit-api"
                aria-selected="true"
                @click="currentTab = 'api'"
              >
                {{ $t('modal-project-tab-api') }}
              </button>
            </div>
          </nav>
          <div class="tab-content pt-3" id="nav-tabContent">
            <div class="tab-pane fade active show" id="nav-edit-metadata" role="tabpanel">
              <div class="row">
                <div class="col-12">
                  <div class="mb-3">
                    <label for="url" class="form-label">{{ $t('modal-project-title') }}</label>
                    <input type="text" class="form-control" v-model="currentProject.title" id="title"
                      aria-describedby="titleHelp" maxlength="50" />
                    <div id="titleHelp" v-if="titleState == false" class="form-text text-danger pre-line">
                      {{ $t('modal-project-title-error') }}
                    </div>
                  </div>
                </div>
                <div class="col-4">
                  <div class="mb-3">
                    <label for="content" class="form-label">{{ $t('modal-project-start-date') }}</label>
                    <DatePicker v-model:value="currentProject.startDate" id="startDate" class="d-block" />
                    <div id="urlHelp" v-if="startDateState == false" class="form-text text-danger">
                      {{ $t('modal-project-start-date-error') }}
                    </div>
                  </div>
                </div>
                <div class="col-4">
                  <div class="mb-3">
                    <label for="content" class="form-label">{{ $t('modal-project-end-date') }}</label>
                    <DatePicker v-model:value="currentProject.finishDate" id="finishDate"
                      :disabled-date="disabledBeforeToday" class="d-block" />
                  </div>
                </div>
                <div class="col-12">
                  <div class="mb-3">
                    <label for="description" class="form-label">{{ $t('modal-project-description') }}</label>
                    <textarea class="form-control" :placeholder="$t('modal-project-description-placeholder')"
                      v-model="currentProject.description" id="description" style="height: 100px"></textarea>
                  </div>
                </div>
                <div class="col-12" v-if="isSuperAdmin">
                  <label class="form-label me-2">Visibility (super-admin):</label>
                  <div class="form-check form-check-inline">
                    <input class="form-check-input" type="radio" checked name="inlineRadioOptions"
                      :id="`visibility-private-${currentProject.id}`" value="private" v-model="visibility">
                    <label class="form-check-label" :for="`visibility-private-${currentProject.id}`">Private</label>
                  </div>
                  <div class="form-check form-check-inline">
                    <input class="form-check-input" type="radio" name="inlineRadioOptions"
                      :id="`visibility-semipublic-${currentProject.id}`" value="semipublic" v-model="visibility">
                    <label class="form-check-label" :for="`visibility-semipublic-${currentProject.id}`">Semi-public</label>
                  </div>
                  <div class="form-check form-check-inline">
                    <input class="form-check-input" type="radio" name="inlineRadioOptions"
                      :id="`visibility-public-${currentProject.id}`" value="public" v-model="visibility">
                    <label class="form-check-label" :for="`visibility-public-${currentProject.id}`">Public</label>
                  </div>
                </div>
                <div class="col-12" v-else>
                  <button class="btn btn-outline-secondary" type="button" id="publicButton" @click="makeDataPublic">
                    {{ $t('modal-project-data-request-public') }}
                  </button>
                </div>
              </div>
            </div>
            <div class="tab-pane fade" id="nav-edit-permissions" role="tabpanel">
              <div class="alert alert-dark" role="alert">
                <h4>{{ $t('common-user', {count: 2}) }}</h4>
                <table class="table">
                  <thead>
                    <tr>
                      <th scope="col">{{ $t('common-name') }}</th>
                      <th scope="col">{{ $t('common-email') }}</th>
                      <th scope="col">{{ $t('common-admin') }}</th>
                      <th scope="col">{{ $t('common-active') }}</th>
                    </tr>
                  </thead>
                  <tbody v-if="users">
                    <tr v-for="user in sortByEmail(users.registred)" :key="user.id">
                      <td v-html="user.displayName"></td>
                      <td>
                        <span v-html="user.email"></span>
                        <div
                          v-if="user.invitedFromEmail && user.email != user.invitedFromEmail"
                          class="small-text"
                        >
                          {{ $t("modal-project-invitation", { email: user.invitedFromEmail}) }}
                        </div>
                      </td>
                      <td>
                        <div class="form-check form-switch">
                          <input
                            class="form-check-input"
                            type="checkbox"
                            :disabled="user.id == lamaUserId"
                            :checked="user.isAdmin"
                            @click="updateUser(user.id, { admin: !user.isAdmin })"
                          />
                        </div>
                      </td>
                      <td>
                        <div class="form-check form-switch">
                          <input
                            class="form-check-input"
                            type="checkbox"
                            :disabled="user.id == lamaUserId"
                            :checked="user.isActive"
                            @click="updateUser(user.id, { active: !user.isActive })"
                          />
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="alert alert-dark" role="alert">
                <h4>{{ $t('modal-project-invited') }}</h4>
                <table class="table">
                  <thead>
                    <tr>
                      <th scope="col">{{ $t('common-email') }}</th>
                      <th scope="col">{{ $t('common-invited') }}</th>
                      <th scope="col">{{ $t('common-active') }}</th>
                    </tr>
                  </thead>
                  <tbody v-if="users">
                    <tr v-for="invitation in users.invited" :key="invitation.id">
                        <td v-html="invitation.email"></td>
                        <td v-html="formatDate(invitation.addedOn)"></td>
                        <td>
                          <button
                            class="btn btn-sm btn-danger ms-1 mb-1"
                            @click="removeInvitation(invitation.id)"
                          >
                            <FontAwesomeIcon :icon="['fas', 'trash']" />
                            {{ $t('common-remove') }}
                          </button>
                        </td>
                      </tr>
                  </tbody>
                </table>
              </div>

              <div class="mt-5 mb-2">
                <label for="email" class="form-label">{{ $t('modal-project-invite') }}</label>
                <div class="input-group mb-1">
                  <input type="text" v-model="inviteEmails" class="form-control"
                    :placeholder="$t('modal-project-invite-placeholder')" />
                  <button class="btn btn-outline-secondary" type="button" id="inviteButton" @click="inviteUsers">
                    {{ $t('common-invite') }}
                  </button>
                </div>
                <small id="inviteHelp" class="form-text text-muted">{{ $t('modal-project-invite-help') }}</small>
              </div>
            </div>
            <div class="tab-pane fade" id="nav-edit-api" role="tabpanel">
              <span v-if="currentProject.api">
                <div class="mb-3">
                  <label for="url" class="form-label">{{ $t('common-key') }}</label>
                  <div class="input-group">
                    <input type="text" class="form-control" id="api-key" disabled :value="currentProject.api.key" />
                    <button class="btn btn-outline-primary" type="button" @click="copyToClipboard(currentProject.api.key, 'API Key')">
                      <FontAwesomeIcon :icon="['fas', 'copy']" />
                    </button>
                  </div>
                </div>

                <div class="mb-3">
                  <label for="secret" class="form-label">{{ $t('common-secret') }}</label>
                  <div class="input-group">
                    <input type="text" class="form-control" id="secret-key" disabled :value="currentProject.api.secret
                      ? currentProject.api.secret
                      : currentProject.api.secretPart.replace(
                        '_',
                        '*********************************************************'
                      )
                    " />
                    <button
                      class="btn btn-outline-primary"
                      type="button"
                      :disabled="!currentProject.api.secret"
                      @click="copyToClipboard(currentProject.api.secret, 'API Secret')
                    ">
                      <FontAwesomeIcon :icon="['fas', 'copy']" />
                    </button>
                  </div>
                  <div id="secretHelp" v-if="currentProject.api.secret" class="form-text text-danger">
                    <b>{{ $t('common-help-1') }}</b><br />{{ $t('common-help-2') }}
                  </div>
                </div>
                <div class="mb-3">
                  <label for="issued-on" class="form-label">{{ $t('modal-project-issued') }}</label>
                  <input type="text" class="form-control" id="issued-on" disabled
                    :value="formatDate(currentProject.api.addedOn)" />
                </div>
                <button type="button" class="btn btn-danger btn-sm mt-3 mb-3"
                  @click="APIKeyRevoke(currentProject.id, currentProject.api.id)">
                  <FontAwesomeIcon :icon="['fas', 'trash']" class="me-1" />
                  {{ $t('modal-project-revoke-key') }}
                </button>
              </span>
              <div v-else class="text-center">
                <button type="button" class="btn btn-primary" @click="APIKeyCreate(currentProject.id)">
                  <FontAwesomeIcon :icon="['fas', 'circle-plus']" class="me-1" />
                  {{ $t('modal-project-create-key') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.alert table th,
.alert table td {
  background: transparent;
  border-color: #c4c4c4;
}
</style>

<script>
import Utils from "@/utils";
import { useUserStore } from "@/stores/userStore";
import { useProjectStore } from "@/stores/projectStore";
import { useNotificationStore } from "@/stores/notificationStore";

export default {
  name: 'ProjectEditView',
  props: ["project"],
  data() {
    let currentProject = { ...this.project };
    currentProject.startDate = new Date(currentProject.startDate)
    if (currentProject.finishDate) {
      currentProject.finishDate = new Date(currentProject.finishDate)
    }

    return {
      currentTab: "metadata",
      currentProject: currentProject,
      titleState: false,
      startDateState: this.project.startDate ? true : false,
      visibility: this.project.additionalData && this.project.additionalData.visibility ? this.project.additionalData.visibility : "private",
      inviteEmails: '',
      users: [],
      lamaUserId: null,
      isSuperAdmin: useUserStore().isSuperAdmin
    };
  },
  mounted() {
    this.loadUsers();
    this.lamaUserId = useUserStore().userData.user.id;
  },
  watch: {
    visibility() {
      if (this.currentProject.additionalData == undefined) {
        this.currentProject.additionalData = {}
      }
      this.currentProject.additionalData['visibility'] = this.visibility
      this.currentProject.additionalData.public = this.visibility == "public";
    }
  },
  methods: {
    updateUser(userId, data) {
      useProjectStore().updateUser(this.currentProject.id, userId, {
        projectId: this.currentProject.id,
        userId: userId,
        ...data
      }).then(() => {
        this.loadUsers()
      });
    },
    removeInvitation(invitationId) {
      useProjectStore().removeInvitation(this.currentProject.id, invitationId).then(() => {
        this.loadUsers()
      });
    },
    sortByEmail(list) {
      return list ? list.sort((a, b) => a.email.localeCompare(b.email)) : [];
    },
    loadUsers() {
      useProjectStore().getUsers(this.currentProject.id).then((data) => {
        this.users = data;
      })
    },
    makeDataPublic() {
      console.log("makeDataPublic", this.isSuperAdmin);
    },
    copyToClipboard(text, name) {
      Utils.copyToClipboard(text);
      useNotificationStore().add({
        type: "success",
        text: `${name} has been copied to clipboard`,
      });
    },
    formatDate: Utils.formatDate,
    async APIKeyRevoke(projectId, apiKeyId) {
      let retval = await useProjectStore().revokeApiKey(projectId, apiKeyId);
      if (retval.result == "ok") {
        this.currentProject.api = null;
        useUserStore().fetchUserData();
        useNotificationStore().add({
          type: "success",
          text: "The API key is successfully revoked",
        });
      }
    },
    async APIKeyCreate(projectId) {
      let retval = await useProjectStore().createApiKey(projectId);
      if (retval.result == "ok") {
        this.currentProject.api = retval.api;
        useUserStore().fetchUserData();
        // useNotificationStore().add({
        //   type: "success",
        //   text: `The API key is successfully created. Safely store your secret key. It will be shown just this time: <b>${retval.api.secret}</b>`,
        //   timeout: 120,
        // });
      }
    },
    async inviteUsers() {
      let emails = this.inviteEmails.split(",").map((email) => email.trim()).filter(email => Utils.validateEmail(email));
      useProjectStore().inviteUsers(this.currentProject.id, emails).then(() => {
        this.loadUsers()
        this.inviteEmails = '';
      });
    },
    validate() {
      this.titleState = this.currentProject.title.trim().replace(/\s\s+/g, ' ').length >= 7;
      this.startDateState = this.currentProject.startDate ? true : false;
      // this.finishDateState = this.model.finishDate ? true : false;
      let validated = this.titleState && this.startDateState;
      this.$emit('updated', validated, this.currentProject);
      return validated;
    },
    disabledBeforeToday(date) {
      return (
        date < this.currentProject.startDate ||
        date > new Date(new Date().getTime() + 4 * 365 * 24 * 3600 * 1000)
      );
    },
  },
  updated() {
    this.validate();
  },
};
</script>
