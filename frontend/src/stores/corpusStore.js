import { defineStore } from "pinia";
import { getUserLocale } from "@/fluent";
import httpApi from "@/httpApi";
import { t } from '@/i18n';

export const useCorpusStore = defineStore("corpusData", {
  state: () => ({
    queryData: null,
    corpora: [],
    licenses: [
      {tag: "cc-by", name: "CC-BY", url: "https://creativecommons.org/licenses/by/4.0/"},
      {tag: "cc-by-sa", name: "CC-BY-SA", url: "https://creativecommons.org/licenses/by-sa/4.0/"},
      {tag: "cc-by-nc", name: "CC-BY-NC", url: "https://creativecommons.org/licenses/by-nc/4.0/"},
      {tag: "cc-by-nc-sa", name: "CC-BY-NC-SA", url: "https://creativecommons.org/licenses/by-nc-sa/4.0/"},
      {tag: "cc-by-nd", name: "CC-BY-ND", url: "https://creativecommons.org/licenses/by-nd/4.0/"},
      {tag: "cc-by-nc-nd", name: "CC-BY-NC-ND", url: "https://creativecommons.org/licenses/by-nc-nd/4.0/"},
      {tag: "cc-zero", name: "CC-0", url: "https://creativecommons.org/publicdomain/zero/1.0/"},
      {tag: "user-defined", name: "User defined", url: null}
    ],
    languages: [
      { value: "und", name: t('modal-meta-lg-undefined') },
      { value: "en", name: t('modal-meta-lg-english') },
      { value: "de", name: t('modal-meta-lg-german') },
      { value: "fr", name: t('modal-meta-lg-french') },
      { value: "it", name: t('modal-meta-lg-italian') },
      { value: "es", name: t('modal-meta-lg-spanish') },
      { value: "gs", name: t('modal-meta-lg-swiss-german') },
      { value: "rm", name: t('modal-meta-lg-romansh') },
    ],
  }),
  getters: {
    getLicenseByTag: (state) => {
      return (tag) => {
        return state.licenses.find(license => license.tag === tag) || {url: ""}
      }
    },
  },
  actions: {
    async fetchQuery(data) {
      let response = await httpApi.post(`/query`, data)
      this.queryData = await response.data;
      return this.queryData
    },
    saveQuery(data) {
      httpApi.post(`/store`, data).then((response) => {
        return response.data;
      });
    },
    deleteQuery(user_id, room_id, query_id) {
      httpApi.delete(`/user/${user_id}/room/${room_id}/query/${query_id}`).then((response) => {
        return response.data;
      });
    },
    fetchQueries(data) {
      return httpApi.post(`/fetch`, data).then((response) => {
        this.fetchedQueries = response.data;
        return response.data;
      });
    },
    updateMeta(data) {
      const lg = getUserLocale().value;
      const toSend = {lg: lg, metadata: data.metadata, descriptions: data.descriptions}
      httpApi.put(`/corpora/${data.corpusId}/meta/update`, toSend).then((response) => {
        return response.data;
      });
    },
    fetchCorpora() {
      httpApi.post(`/corpora`).then((response) => {
        this.corporaJson = response.data;
        delete this.corporaJson.config["-1"];
        const lg = getUserLocale().value;
        this.corpora = Object.keys(this.corporaJson.config).map(corpusId => {
          let corpus = this.corporaJson.config[corpusId]
          corpus.meta['id'] = corpusId
          for (let [k,v] of Object.entries(corpus.meta)) {
            if (typeof(v) == "string" || !(v instanceof Object))
              continue;
            if (lg in v && typeof(v[lg]) == "string")
              corpus.meta[k] = v[lg];
            else if ("en" in v && typeof(v.en) == "string")
              corpus.meta[k] = v.en;
          }
          for (let [layer, props] of Object.entries(corpus.layer)) {
            for (let [k,v] of Object.entries(props.attributes || {})) {
              if (k == "meta" && v instanceof Object) {
                for (let [mk,mv] of Object.entries(v)) {
                  if (!mv.description || typeof(mv.description) == "string" || !(mv.description instanceof Object))
                    continue;
                  if (lg in mv.description && typeof(mv.description[lg]) == "string")
                    corpus.layer[layer].attributes.meta[mk].description = mv.description[lg];
                  else if ("en" in mv.description && typeof(mv.description.en) == "string")
                    corpus.layer[layer].attributes.meta[mk].description = mv.description.en;
                }
              }
              else {
                if (!v.description || typeof(v.description) == "string" || !(v.description instanceof Object))
                  continue;
                if (lg in v.description && typeof(v.description[lg]) == "string")
                  corpus.layer[layer].attributes[k].description = v.description[lg];
                else if ("en" in v.description && typeof(v.description.en) == "string")
                  corpus.layer[layer].attributes[k].description = v.description.en;
              }
            }
          }
          return corpus
        })
      });
    },
    fetchDocuments(data) {
      httpApi.post(`/document_ids/${data.corpora_id}`, data).then((response) => {
        return response.data;
      });
    },
    fetchDocument(data) {
      httpApi.post(`/document/${data.doc_id}`, data).then((response) => {
        return response.data;
      });
    },
    async fetchExport(info) {
      const ampsInfo = Object.entries(info).map(([k,v])=>encodeURIComponent(k)+"="+encodeURIComponent(v)).join("&")
      let url = `${httpApi.getUri()}/download_export?${ampsInfo}`;
      const a = document.createElement("A");
      a.target = "_blank";
      a.href = url;
      a.download = "results";
      document.body.append(a);
      a.click();
      a.remove();
    }
  },
});
