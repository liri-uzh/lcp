<template>
  <div id="notifications">
    <div v-if="messages.length > 1" class="notification close-all">
      <span class="close-all-button" @click="removeAllMessages">Clear all</span>
    </div>
    <div
      class="alert notification"
      :class="`alert-${alertClass(message.type)}`"
      role="alert"
      v-for="(message, index) in messages"
      :key="index"
    >
      <span v-html="message.text" />
      <small class="close-button" @click="removeMessage(index)">
        <FontAwesomeIcon :icon="['fas', 'xmark']" />
      </small>
      <small class="countdown-text">{{ message.dismissCountDown }}</small>
    </div>
  </div>
</template>

<style scoped>
#notifications {
  width: 100%;
  margin: auto;
  position: fixed;
  bottom: 1em;
  text-align: center;
  z-index: 100000;
}

.countdown-text {
  position: absolute;
  top: 15px;
  right: 30px;
  text-align: right;
  width: 30px;
  user-select: none;
}

.close-button {
  position: absolute;
  top: 15px;
  right: 10px;
  cursor: pointer;
  user-select: none;
}
.close-button:hover {
  opacity: 1;
}

.notification {
  width: 50%;
  margin: auto;
  text-align: left;
  margin-top: 7px;
  position: relative;
}

.close-all {
  text-align: right;
}

.close-all-button {
  background-color: #2a7f62;
  text-transform: uppercase;
  color: #fff;
  font-size: 10px;
  border-radius: 3px;
  padding: 3px 5px;
  font-weight: bold;
  opacity: 0.6;
  cursor: pointer;
  transition: 0.3s all;
}
.close-all-button:hover {
  opacity: 1;
}

small {
  opacity: 0.4;
  margin-top: 3px;
}
</style>

<script>
import { mapState } from "pinia";
import { useNotificationStore } from "@/stores/notificationStore";

export default {
  name: "NotificationsView",
  data() {
    return {
      dismissSecs: 7,
      messages: [],
      timer: null,
    };
  },
  computed: {
    ...mapState(useNotificationStore, ["notifications"]),
  },
  watch: {
    notifications: {
      handler() {
        let _notifications = this.notifications;
        if (_notifications.length > 0) {
          _notifications.forEach((element) => {
            this.messages.push({
              ...element,
              show: true,
              dismissCountDown: element.timeout || this.dismissSecs,
            });
            this.startTimer();
          });
          useNotificationStore().clear();
        }
      },
      immediate: true,
      deep: true,
    },
  },
  methods: {
    startTimer() {
      this.clearTimer();
      this.timer = setInterval(() => this.countDownChanged(), 1000);
    },
    clearTimer() {
      if (this.timer) {
        clearTimeout(this.timer);
      }
    },
    alertClass(type) {
      let retval = "success";
      switch (type) {
        case "error":
          retval = "danger";
          break;
        case "warning":
          retval = "warning";
          break;
      }
      return retval;
    },
    countDownChanged() {
      this.messages.forEach((message) => {
        message.dismissCountDown--;
      });
      this.messages = this.messages.filter(
        (message) => message.dismissCountDown > 0
      );
      if (this.messages.length == 0) {
        this.clearTimer();
      }
    },
    removeMessage(index) {
      this.messages = this.messages.filter((message, idx) => index != idx);
      if (this.messages.length == 0) {
        this.clearTimer();
      }
    },
    removeAllMessages() {
      this.messages = [];
      this.clearTimer();
    },
  },
};
</script>
