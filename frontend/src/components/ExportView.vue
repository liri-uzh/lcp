<template>

	<div
		id="exportMonitor"
		ref="export"
		@mouseenter="warn = false"
		v-if="notifs.filter(n=>n.warn).length > 0"
	>
        <div
            v-for="(notif, n) in notifs.filter(n=>n.warn)"
            class="notif"
            :key="`notif-${n}`"
        >
            {{`[${notif.when}] ${notif.msg}`}}
            <span
              v-if="notif.dl_info && notif.dl_info.status == 'ready'"
              @click="fetch(notif.dl_info)"
              class="download"
            >
              [ {{ $t('common-ready').toLowerCase() }} ]
            </span>
            <span v-else-if="notif.dl_info">[ {{ notif.dl_info.status }} ]</span>
        </div>
    </div>
    <div v-if="warn" class="warn"></div>

    <div class="modal fade" id="exportsModal" tabindex="-1" aria-labelledby="exportsModalLabel"
      aria-hidden="true" ref="vuemodaldetails">
      <div class="modal-dialog modal-full">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="exportsModalLabel">
              {{ $t('common-export') }}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body text-start">
            <table class="fit-page">
              <tr>
                <th>Last update</th>
                <th>Message</th>
                <th>Status</th>
              </tr>
              <tr
                  v-for="(notif, n) in notifs"
                  class="notif"
                  :key="`notif-${n}`"
              >
                  <td>{{notif.when}}</td>
                  <td>{{notif.msg}}</td>
                  <td
                    v-if="notif.dl_info && notif.dl_info.status == 'ready'"
                    @click="fetch(notif.dl_info)"
                    class="download"
                  >
                    <a href="_blank">{{ $t('common-ready').toLowerCase() }}</a>
                  </td>
                  <td v-else-if="notif.dl_info">{{ notif.dl_info.status }}</td>
              </tr>
            </table>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('common-close') }}
            </button>
          </div>
        </div>
      </div>
    </div>

</template>

<script>
import { mapState } from "pinia";
// // import { useUserStore } from "@/stores/userStore";
import { useCorpusStore } from "@/stores/corpusStore";
import { useWsStore } from "@/stores/wsStore";

export default {
  name: "ExportView",
  data() {
    return {
        notifs: [],
        warn: false
    }
  },
  props: [],
  methods: {
    fetch(info) {
      useCorpusStore().fetchExport(info);
    },
    onSocketMessage(data) {
      const nowStr = new Date().toLocaleString();
      if (data["action"] == "started_export") {
        const info = {created_at: nowStr, status: "exporting", hash: data.hash};
        this.notifs = [{when: nowStr, msg: `Started exporting to ${data.format}`, dl_info: info, warn: true}, ...this.notifs];
        this.warn = true;
      }
      if (data["action"] == "export_complete") {
        const info = {created_at: nowStr, status: "downloading", hash: data.hash};
        this.notifs = [{when: nowStr, msg: `Downloading ${data.format} export file`, dl_info: info, warn: true}, ...this.notifs];
        this.warn = true;
      }
      if (data["action"] == "export_notifs") {
        const n_notifs = this.notifs.length;
        const _notifs = [...this.notifs];
        for (let [
          hash,
          corpus_id, // eslint-disable-line no-unused-vars
          status,
          msg, // eslint-disable-line no-unused-vars
          uid, // eslint-disable-line no-unused-vars
          format,
          offset,
          requested,
          delivered,
          filename,
          created_at, // eslint-disable-line no-unused-vars
          modified_at
        ] of data.exports) {
          const d = new Date(modified_at).toLocaleString();
          const info = {
            hash: hash,
            format: format,
            offset: offset,
            requested: requested,
            delivered: delivered,
            status: status,
            created_at: created_at
          };
          const obj = {when: d, msg: `Exported ${filename}`, dl_info: info};
          const json_obj = JSON.stringify(obj);
          if (_notifs.map(n=>JSON.stringify(n)).includes(json_obj))
            continue
          if (n_notifs > 0) {
            obj.warn = true;
            this.warn = true;
          }
          _notifs.push(obj);
        }
        this.notifs = _notifs;
        if (n_notifs > 0 && this.notifs.length != n_notifs)
          this.warn = true;
      }
      this.notifs = this.notifs
        .sort((a,b)=>new Date(b.dl_info.created_at) > new Date(a.dl_info.created_at))
        .filter((n,i,a) => !a.slice(0,i).find(x=>x.dl_info.hash == n.dl_info.hash));
    }
  },
  computed: {
    ...mapState(useWsStore, ["messages"]),
  },
  watch: {
    messages: {
      handler() {
        let _messages = this.messages;
        if (_messages.length > 0) {
          _messages.forEach(message => this.onSocketMessage(message))
        }
      },
      immediate: true,
      deep: true,
    },
  },
  mounted() {
    // pass
  },
  beforeUnmount() {
    // pass
  }
}
</script>

<style scoped>
#exportMonitor {
  position: absolute;
  display: none;
  background-color: cornsilk;
  padding: 0.5em;
  border-radius: 0.5em;
  box-shadow: 1px 1px 8px black;
  flex-direction: column;
}
.export:hover #exportMonitor {
  display: flex !important;
}
span.download {
  cursor: pointer;
  text-decoration: underline;
}
#exportMonitor + .warn {
  position: absolute;
  display: block;
  width: 0.75em;
  height: 0.75em;
  background-color: red;
  border-radius: 50%;
  transform: translateX(1em);
}
table.fit-page {
  max-height: 80vh;
  overflow-y: scroll;
}
</style>