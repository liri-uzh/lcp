import { createRouter, createWebHistory } from "vue-router";
import config from "@/config";
import HomeViewBase from "../views/HomeView.vue";
import HomeViewLCP from "../views/lcp/HomeView.vue";

// import { useUserStore } from "@/stores/userStore";

const routes = [
  {
    path: "/",
    name: "home",
    component: config.appType == "lcp" ? HomeViewLCP : HomeViewBase,
    meta: {
      requiresAuth: false,
    },
  },
  {
    name: "player",
    path: "/player",
    alias: "/player/:id/:name/",
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () =>
      import("../views/PlayerView.vue"),
    meta: {
      requiresAuth: true,
    },
  },
  {
    name: "query",
    path: "/query",
    alias: "/query/:id/:name/",
    component: () =>
      // import("../views/QueryView.vue"),
      import("../views/QueryViewV2.vue"),
    meta: {
      requiresAuth: true,
    },
  },
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

// router.beforeEach((to, from, next) => {
//   if (to.matched.some((record) => record.meta.requiresAuth)) {
//     // console.log("A", useUserStore().dataFetched, Object.keys(useUserStore().userData.user).length == 0)
//     if (useUserStore().dataFetched && Object.keys(useUserStore().userData.user).length == 0) {
//       window.location.replace("/login");
//       // console.log("Redirect")
//     }
//     else {
//       next()
//     }
//   }
//   else {
//     next()
//   }
// })

export default router;
