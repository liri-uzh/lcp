<template>
  <div class="spinner-placeholder" v-if="status == true || override">
    {{ $t('common-loading') }}
    <div class="loader quantum-spinner"></div>
  </div>
</template>

<style scoped>
.spinner-placeholder {
  text-align: center;
  font-size: 12px;
  margin: auto;
  background-color: rgba(93, 93, 93, 0.75);
  position: fixed;
  bottom: 0;
  right: 5%;
  padding: 6px 12px 6px 12px;
  border-radius: 5px 5px 0 0;
  color: #fff;
  transition: all 0.5s;
}

.spinner-placeholder .dot1,
.spinner-placeholder .dot2 {
  background-color: #fff;
}

.spinner-placeholder .spinner {
  margin-left: 5px;
}

.spinner {
  /* margin: 100px auto; */
  width: 40px;
  height: 40px;
  position: relative;
  text-align: center;

  -webkit-animation: rotate 2s infinite linear;
  animation: rotate 2s infinite linear;
}

.dot1,
.dot2 {
  width: 60%;
  height: 60%;
  display: inline-block;
  position: absolute;
  top: 0;
  background-color: #333;
  border-radius: 100%;

  -webkit-animation: bounce 2s infinite ease-in-out;
  animation: bounce 2s infinite ease-in-out;
}

.dot2 {
  top: auto;
  bottom: 0px;
  -webkit-animation-delay: -1s;
  animation-delay: -1s;
}

@-webkit-keyframes rotate {
  100% {
    -webkit-transform: rotate(360deg);
  }
}
@keyframes rotate {
  100% {
    transform: rotate(360deg);
    -webkit-transform: rotate(360deg);
  }
}

@-webkit-keyframes bounce {
  0%,
  100% {
    -webkit-transform: scale(0);
  }
  50% {
    -webkit-transform: scale(1);
  }
}

@keyframes bounce {
  0%,
  100% {
    transform: scale(0);
    -webkit-transform: scale(0);
  }
  50% {
    transform: scale(1);
    -webkit-transform: scale(1);
  }
}

/*
  The loaders use CSS custom properties (variables) to control the attributes of the loaders
  */
:root {
  --loader-width: 30px;
  --loader-height: 30px;
  --loader-color-primary: #fff;
  --loader-color-secondary: rgb(189, 189, 189);
  --line-width: 2px;
  --animation-duration: 2s;
  --loader-initial-scale: 0.1;
}
.loader,
.loader:before,
.loader:after {
  box-sizing: border-box;
  flex-grow: 0;
  flex-shrink: 0;
}
/*
  In order to get optimal results, please only change the
  variables above and don't change anything in the actual loader code
  */

@keyframes momentum {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(-360deg);
  }
}

.loader.quantum-spinner {
  --primary-circle-offset: calc(
    ((var(--loader-width, 30px) * 0.2) / 2) - var(--line-width, 2px)
  );
  --secondary-circle-offset: calc(
    ((var(--loader-width, 30px) * 0.4) / 2) - var(--line-width, 2px)
  ); /*- (var(--line-width,4px) * 2)*/
  position: relative;
  width: var(--loader-width, 30px);
  height: var(--loader-height, 30px);
  transform-origin: center center;
  border-radius: 50%;
  border: var(--line-width, 2px) solid rgba(0, 0, 0, 0);
  border-top-color: var(--loader-color-primary, #fff);
  animation: momentum var(--animation-duration, 1s) linear infinite;
  margin-left: 6px;
}

.quantum-spinner:before {
  content: "";
  position: absolute;
  transform-origin: center center;
  top: var(--primary-circle-offset, 10px);
  left: var(--primary-circle-offset, 10px);
  width: calc(var(--loader-width, 30px) * 0.8);
  height: calc(var(--loader-height, 30px) * 0.8);
  border-radius: 50%;
  border: var(--line-width, 2px) solid rgba(0, 0, 0, 0);
  border-top-color: var(--loader-color-primary, #fff);
  opacity: 0.7;
  filter: hue-rotate(3eg);
  animation: momentum calc(var(--animation-duration, 1s) * 2) linear infinite;
}

.quantum-spinner:after {
  content: "";
  position: absolute;
  top: var(--secondary-circle-offset, 20px);
  left: var(--secondary-circle-offset, 20px);
  width: calc(var(--loader-width, 30px) * 0.6);
  height: calc(var(--loader-height, 30px) * 0.6);
  border-radius: 50%;
  transform-origin: center center;
  border: var(--line-width, 2px) solid rgba(0, 0, 0, 0);
  border-top-color: var(--loader-color-primary, #fff);
  opacity: 0.3;
  filter: hue-rotate(6eg);
  animation: momentum var(--animation-duration, 1s) linear infinite;
}
</style>

<script>
import { mapState } from "pinia";
import { useLoadingStore } from "@/stores/loadingStore";

export default {
  name: "LoadingView",
  props: ["override"],
  computed: {
    ...mapState(useLoadingStore, ["status"]),
  },
};
</script>
