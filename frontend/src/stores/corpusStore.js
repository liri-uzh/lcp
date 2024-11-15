import { defineStore } from "pinia";
import httpApi from "@/httpApi";

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
  }),
  getters: {
    getLicenseByTag: (state) => {
      return (tag) => {
        return state.licenses.find(license => license.tag === tag)
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
    fetchQueries(data) {
      httpApi.post(`/fetch`, data).then((response) => {
        this.fetchedQueries = response.data;
        return response.data;
      });
    },
    updateMeta(data) {
      httpApi.put(`/corpora/${data.corpusId}/meta/update`, data.metadata).then((response) => {
        return response.data;
      });
    },
    fetchCorpora() {
      httpApi.post(`/corpora`).then((response) => {
        this.corporaJson = response.data;
        delete this.corporaJson.config["-1"]
        this.corpora = Object.keys(this.corporaJson.config).map(corpusId => {
          let corpus = this.corporaJson.config[corpusId]
          corpus.meta['id'] = corpusId
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
    async fetchExport(schema_path, fn) {
      let url = `${httpApi.getUri()}/download_export/${schema_path}/${fn}`;
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
