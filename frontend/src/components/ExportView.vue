<template>
    <div
      id="exportMonitor"
      ref="export"
      :class="warn ? 'warn' : ''"
      @mouseenter="warn = false"
      v-if="notifs.length > 0">
        <div
            v-for="(notif, n) in notifs"
            class="notif"
            :key="`notif-${n}`"
        >
            {{`[${notif.when}] ${notif.msg}`}}
            <span
              v-if="notif.dl_info && notif.dl_info.status == 'ready'"
              @click="fetch(notif.dl_info)"
              class="download"
            >[ {{ $t('common-ready').toLowerCase() }} ]</span>
            <span v-else-if="notif.dl_info">[ {{ notif.dl_info.status }} ]</span>
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
        this.notifs = [{when: nowStr, msg: `Started exporting to ${data.format}`, dl_info: info}, ...this.notifs];
        this.warn = true;
      }
      if (data["action"] == "export_complete") {
        const info = {created_at: nowStr, status: "downloading", hash: data.hash};
        this.notifs = [{when: nowStr, msg: `Downloading ${data.format} export file`, dl_info: info}, ...this.notifs];
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
  display: flex;
  background-color: cornsilk;
  padding: 0.5em;
  border-radius: 0.5em;
  box-shadow: 1px 1px 8px black;
  visibility: hidden;
  flex-direction: column;
}
#exportMonitor:hover {
  visibility: visible;
}
span.download {
  cursor: pointer;
  text-decoration: underline;
}
#exportMonitor.warn::after {
  position: absolute;
  top: 0px;
  left: 1.5em;
  display: block;
  content: '';
  width: 0.75em;
  height: 0.75em;
  background-color: red;
  border-radius: 50%;
  visibility: visible;
}
</style>