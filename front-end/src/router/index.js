import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, from, savedPosition) {
    // 如果有保存的位置（比如浏览器前进后退），则返回保存的位置
    if (savedPosition) {
      return savedPosition
    }
    // 否则滚动到页面顶部
    return { top: 0 }
  },
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/home', name: 'home', component: () => import('@/views/WelcomeView.vue') },
    { path: '/main', name: 'main', component: () => import('@/views/MainView.vue') },
    {
      path: '/404',
      name: 'not-found',
      component: () => import('@/views/NotFound.vue')
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/404'
    }
  ]
})

export default router
