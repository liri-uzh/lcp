import { defineStore } from "pinia";
import { config } from "@/config";

export const useWsStore = defineStore("wsData", {
  state: () => ({
    messages: [],
    socket: null,
    userId: null,
    roomId: null,
    messagesPlayer: [],
  }),
  getters: {},
  actions: {
    waitForConnection(callback, interval) {
      if (this.socket.readyState === 1) {
        callback();
      } else {
        setTimeout(() => {
          this.waitForConnection(callback, interval);
        }, interval);
      }
    },
    add(message) {
      this.messages.push(message)
    },
    clear() {
      this.messages = []
    },
    addMessageForPlayer(message) {
      this.messagesPlayer.push(message)
    },
    clearPlayer() {
      this.messagesPlayer = []
    },
    connectToRoom(socket, userId, roomId) {
      if (userId == null) {
        return
      }
      // console.log("USER", userId, "ROOM", roomId, "SOCKET", socket)
      this.socket = socket
      this.userId = userId
      this.roomId = roomId
      // console.log("Connect to WS room", this.socket, this.roomId, userId)
      // if (this.socket.readyState != 1){
      // console.log("Connect to WS")
      this.waitForConnection(() => {
        this.socket.sendObj({
          room: this.roomId,
          action: "joined",
          user: userId,
        });
        this.socket.onmessage = this.onSocketMessage;
        this.socket.onclose = (e) => {
          console.log('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
          setTimeout(() => {
            this.connectToRoom(this.socket, this.userId, this.roomId);
          }, 1000);
        };
        this.socket.onerror = (err) => {
          console.error('Socket encountered error: ', err.message, 'Closing socket');
          this.socket.close();
        };
        this.socket.onopen = () => {
          console.log('Socket opened');
        };
        // console.log("Connected to WS")

        // this.socket.addEventListener("close", (event) => {
        //   console.log("Server close", event)
        // });
      }, 500);
      // }
    },
    onSocketMessage(event) {
      let data = JSON.parse(event.data);
      // console.log("Rec1a", data)
      this.add(data)
    },
    sendWSMessage(data) {
      // console.log("WS-State", this.socket.readyState)
      // if (this.socket.readyState == 3) {
      //   // this.waitForConnection(() => {
      //     // this.connectToRoom(this.socket, this.userId, this.roomId);
      //   this.socket = new WebSocket('ws://localhost:9090/ws');
      //   // this.socket = new WebSocket(config.wsUrl);
      //   this.socket.onopen = () => {
      //     console.log('Socket opened');
      //     this.connectToRoom(this.socket, this.userId, this.roomId);
      //   };
      //   // }, 500)
      //   // console.log("AEMMMMM")
      // }
      // // console.log("Send")
      // this.socket.sendObj({
      //   room: this.roomId,
      //   user: this.userId,
      //   ...data,
      // });

      if (this.socket) {
        if (this.socket.readyState == 3) {
          this.socket = new WebSocket(config.wsUrl);
          this.socket.onopen = () => {
            this.connectToRoom(this.socket, this.userId, this.roomId);
          };
        }
        this.socket.sendObj({
          room: this.roomId,
          user: this.userId,
          ...data,
        });
      }
    },
  },
});
