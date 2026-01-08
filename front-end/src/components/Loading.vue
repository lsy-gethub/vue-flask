<template>
  <div id="loading" :class="loadingClass">
    <svg viewBox='0 0 50 50'>
      <circle r='25' cx='25' cy='25'></circle>
    </svg>
    <p>LOADING</p>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'

// 状态：'hidden-bottom' | 'visible' | 'hidden-top'
// 初始为 'visible'，用于首次加载时的动画
const position = ref('visible')
const noTransition = ref(false)

const loadingClass = computed(() => ({
  'loading-hidden-bottom': position.value === 'hidden-bottom',
  'loading-visible': position.value === 'visible',
  'loading-hidden-top': position.value === 'hidden-top',
  'no-transition': noTransition.value,
}))

const startLoading = (next, checkLoadingCallback) => {
  position.value = 'visible'
  setTimeout(() => {
    if (next) next()
    if (checkLoadingCallback) checkLoadingCallback()
  }, 1000)
}

// 上浮进入动画：从底部滑入覆盖屏幕
const slideUpEnter = async () => {
  // 先禁用过渡动画，确保初始位置正确
  noTransition.value = true
  position.value = 'hidden-bottom'
  
  await nextTick()
  
  // 恢复过渡动画
  setTimeout(() => {
    noTransition.value = false
    // 触发上浮进入动画
    position.value = 'visible'
  }, 50)
}

// 上浮离开动画：向上滑出屏幕
const slideUpLeave = () => {
  position.value = 'hidden-top'
}

// 兼容旧接口
const startTransparentLoading = slideUpEnter
const finishLoading = slideUpLeave

defineExpose({
  startLoading,
  startTransparentLoading,
  finishLoading,
  slideUpEnter,
  slideUpLeave,
})
</script>

<style scoped>
#loading {
  position: fixed;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  top: 0;
  left: 0;
  width: 100%;
  height: 100vh;
  background-color: #f7f7f7;
  z-index: 100000000;
  transition: transform 1s ease;
  pointer-events: auto;
}

#loading.no-transition {
  transition: none !important;
}

/* 隐藏在屏幕下方 */
#loading.loading-hidden-bottom {
  transform: translateY(100%);
  pointer-events: none;
}

/* 显示在屏幕上 */
#loading.loading-visible {
  transform: translateY(0);
  pointer-events: auto;
}

/* 隐藏在屏幕上方（上浮离开） */
#loading.loading-hidden-top {
  transform: translateY(-100%);
  pointer-events: none;
}

#loading svg {
  width: 5rem;
  margin-bottom: 2rem;
  overflow: visible;
  transition: 0.3s ease;
}

#loading svg circle {
  fill: none;
  stroke: #171717;
  stroke-width: 12;
  stroke-dasharray: 160;
  stroke-dashoffset: 160;
  transform-origin: center;
  animation: circle_rotate 3s ease-in infinite;
}

@keyframes circle_rotate {
  0% {
    transform: rotate(0deg);
    stroke-dashoffset: 160;
  }
  100% {
    transform: rotate(360deg);
    stroke-dashoffset: -160;
  }
}

#loading p {
  font-family: sans-serif;
  font-size: 2rem;
  color: #171717;
  font-weight: 900;
  transition: 0.3s ease;
}

.loading-hidden-bottom svg,
.loading-hidden-bottom p,
.loading-hidden-top svg,
.loading-hidden-top p {
  opacity: 0;
}
</style>