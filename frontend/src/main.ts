import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/projects' },
    {
      path: '/projects',
      component: () => import('./views/ProjectListPage.vue'),
    },
    {
      path: '/projects/:id/agents',
      component: () => import('./views/AgentDesignPage.vue'),
    },
    {
      path: '/projects/:id/dimensions',
      component: () => import('./views/DimensionPage.vue'),
    },
    {
      path: '/projects/:id/edges',
      component: () => import('./views/EdgeDesignPage.vue'),
    },
    {
      path: '/projects/:id/events',
      component: () => import('./views/EventDesignPage.vue'),
    },
    {
      path: '/dashboard',
      component: () => import('./views/ResultDashboardPage.vue'),
    },
    {
      path: '/dashboard/:simId',
      component: () => import('./views/ResultDashboardPage.vue'),
    },
    {
      path: '/simulations/:simId/whatif',
      component: () => import('./views/WhatIfPage.vue'),
    },
  ],
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
