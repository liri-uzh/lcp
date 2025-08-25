<template>
  <div class="project-new">
    <div class="container">
      <div class="row">
        <div class="col-12">
          <div class="mb-3">
            <label for="url" class="form-label">{{ $t('modal-project-title') }}</label>
            <input type="text" class="form-control" v-model="model.title" id="title" aria-describedby="titleHelp"
              maxlength="50" />
            <div id="titleHelp" v-if="titleState == false" class="form-text text-danger pre-line">
              {{ $t('modal-project-title-error') }}
            </div>
            <div id="titleHelp" v-if="titleWithTheSameNameExistsState == true" class="form-text text-danger">
              {{ $t('modal-project-title-unique-error') }}
            </div>
          </div>
        </div>
        <div class="col-12 col-lg-4">
          <div class="mb-3">
            <label for="content" class="form-label">{{ $t('modal-project-start-date') }}</label>
            <DatePicker v-model:value="model.startDate" id="startDate" class="d-block" />
            <div id="urlHelp" v-if="startDateState == false" class="form-text text-danger">
              {{ $t('modal-project-start-date-error') }}
            </div>
          </div>
        </div>
        <div class="col-12 col-lg-4">
          <div class="mb-3">
            <label for="content" class="form-label">{{ $t('modal-project-end-date') }}</label>
            <DatePicker v-model:value="model.finishDate" id="finishDate" :disabled-date="disabledBeforeToday"
              class="d-block" />
            <div id="urlHelp" v-if="finishDateState == false" class="form-text text-danger">
              {{ $t('modal-project-end-date-error') }}
            </div>
          </div>
        </div>
        <div class="col-12">
          <div class="mb-3">
            <label for="description" class="form-label">{{ $t('modal-project-description') }}</label>
            <textarea class="form-control" :placeholder="$t('modal-project-description-placeholder')"
              v-model="model.description" id="description" style="height: 100px"></textarea>
          </div>
        </div>
        <div class="col-12">
          <!-- <button class="btn btn-outline-secondary" type="button" id="publicButton" @click="makeDataPublic">
            Request to make Data Public
          </button> -->
          <!-- <label class="form-label me-2">Visibility:</label>
          <div class="form-check form-check-inline">
            <input class="form-check-input" type="radio" name="inlineRadioOptions" id="visibility-private" value="private"
              v-model="model.additionalData.visibility" checked>
            <label class="form-check-label" for="visibility-private">Private</label>
          </div>
          <div class="form-check form-check-inline">
            <input class="form-check-input" type="radio" name="inlineRadioOptions" id="visibility-semipublic" value="semipublic"
              v-model="model.additionalData.visibility">
            <label class="form-check-label" for="visibility-semipublic">Semi-public</label>
          </div>
          <div class="form-check form-check-inline">
            <input class="form-check-input" type="radio" name="inlineRadioOptions" id="visibility-public" value="public"
              v-model="model.additionalData.visibility">
            <label class="form-check-label" for="visibility-public">Public</label>
          </div> -->
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped></style>

<script>
import { mapState } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useProjectStore } from "@/stores/projectStore";

export default {
  name: 'ProjectNewView',
  data() {
    const today = new Date();
    let oneYear = new Date();
    oneYear.setYear(today.getFullYear() + 1);
    return {
      model: {
        title: '',
        startDate: today,
        finishDate: oneYear,
        description: '',
        additionalData: {
          visibility: 'private',
        }
      },
      titleState: null,
      startDateState: null,
      finishDateState: null,
      titleWithTheSameNameExistsState: null,
    };
  },
  computed: {
    ...mapState(useUserStore, ["userData"]),
  },
  methods: {
    disabledBeforeToday(date) {
      return (
        date < this.model.startDate ||
        date > new Date(new Date().getTime() + 4 * 365 * 24 * 3600 * 1000)
      );
    },
    async validate() {
      this.titleState = this.model.title.trim().replace(/\s\s+/g, ' ').length >= 7;
      this.startDateState = this.model.startDate ? true : false;
      this.finishDateState = this.model.finishDate ? true : false;

      if (this.titleState) {
        await useProjectStore().checkTitle(this.model.title).then((data) => {
          this.titleWithTheSameNameExistsState = data.exists;
        });
      }

      let validated =
        this.titleState &&
        this.titleWithTheSameNameExistsState != true &&
        this.startDateState &&
        this.finishDateState;
      this.$emit('updated', validated, this.model);
      return validated;
    },
  },
  updated() {
    this.validate();
  },
};
</script>
