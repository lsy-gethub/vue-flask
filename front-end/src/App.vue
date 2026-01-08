<script setup>
import { ref, onMounted, provide } from 'vue'
import { useRouter } from 'vue-router'
import Loading from '@/components/Loading.vue'

const loadingRef = ref(null)
const router = useRouter()

// 提供给子组件调用的方法：Loading 上浮进入
const startTransparentTransition = () => {
  loadingRef.value?.slideUpEnter()
}

// 通过 provide 提供给所有子组件
provide('startTransparentTransition', startTransparentTransition)

onMounted(() => {
  router.isReady().then(() => {
    setTimeout(() => {
      loadingRef.value?.slideUpLeave()
    }, 50)
  })

  router.beforeEach((to, from, next) => {
    if (!loadingRef.value) return next()

    // 从欢迎页到主页时，跳过 startLoading（动画已由 WelcomeView 触发）
    if (from.name === 'home' && to.name === 'main') {
      next()
      // 跳转后触发 Loading 上浮离开动画
      setTimeout(() => {
        loadingRef.value?.slideUpLeave()
      }, 100)
      return
    }

    // 从主页返回欢迎页时，显示 Loading 上浮进入动画
    if (from.name === 'main' && to.name === 'home') {
      loadingRef.value?.slideUpEnter()
      // 等待动画完成后跳转
      setTimeout(() => {
        next()
        // 跳转后触发 Loading 上浮离开
        setTimeout(() => {
          loadingRef.value?.slideUpLeave()
        }, 100)
      }, 800)
      return
    }

    loadingRef.value.startLoading(next)
  })
})
</script>

<template>
  <Loading ref="loadingRef" />
  <RouterView v-slot="{ Component }">
    <keep-alive>
      <component :is="Component" />
    </keep-alive>
  </RouterView>
</template>

<style scoped lang="scss">
/* 全局禁用滚动条 */
html, body {
  overflow: hidden !important;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

html::-webkit-scrollbar,
body::-webkit-scrollbar {
  display: none !important;
  width: 0 !important;
  height: 0 !important;
}
</style>