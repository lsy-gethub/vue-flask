<!-- ==================== 欢迎页面组件 ==================== -->
<!-- 
  WelcomeView.vue - 系统欢迎页面
  
  功能概述：
  1. 显示欢迎标题和开始按钮
  2. 背景三角形动画效果
  3. 文字逐字浮现动画
  4. 点击按钮跳转到主页面
-->
<script setup>
// ==================== Vue 相关导入 ====================
import { ref, onMounted, onActivated, nextTick, inject } from 'vue'
import { ElButton } from 'element-plus'
import router from '@/router'

// 从 App.vue 注入的方法（用于过渡动画）
const startTransparentTransition = inject('startTransparentTransition', () => {})

// ==================== 状态定义 ====================
// 三角形装饰数组
const triangles = ref([])
// 按钮加载状态
const loading = ref(false)
// 控制文字是否显示
const showText = ref(false)
// 控制文字是否正在退出（模糊消失）
const textExiting = ref(false)

/**
 * 处理开始按钮点击
 * 触发文字消失动画，然后跳转到主页面
 */
const handleStart = () => {
  if (loading.value) return
  loading.value = true

  // 触发文字消失动画
  textExiting.value = true

  // 同时触发 Loading 上浮动画
  startTransparentTransition()

  // 等待 800ms 后跳转
  setTimeout(() => {
    router.push({ name: 'main' })
  }, 800)
}

/**
 * 创建背景三角形装饰
 * 生成随机位置、大小、动画参数的三角形数组
 */
const createTriangles = () => {
  const count = 40
  const arr = []
  for (let i = 0; i < count; i += 1) {
    arr.push({
      id: i,
      x: Math.random() * 100,           // X 位置（百分比）
      y: Math.random() * 100,           // Y 位置（百分比）
      size: 20 + Math.random() * 80,    // 大小（像素）
      duration: 4 + Math.random() * 6,  // 动画持续时间（秒）
      delay: Math.random() * 5,         // 动画延迟（秒）
      opacity: 0.15 + Math.random() * 0.4,  // 不透明度
      rotate: Math.random() * 360,      // 初始旋转角度
    })
  }
  triangles.value = arr
}

// ==================== 生命周期钩子 ====================
/**
 * 组件挂载时
 * 创建三角形装饰，延迟显示文字
 */
onMounted(() => {
  createTriangles()
  // 等待 Loading 组件的遮罩动画（1s）结束后，触发文字浮现
  setTimeout(() => {
    showText.value = true
  }, 1000)
})

/**
 * 组件激活时（keep-alive）
 * 重置状态，重新触发动画
 */
onActivated(() => {
  loading.value = false
  textExiting.value = false
  // 重新触发文字浮现
  showText.value = false
  nextTick(() => {
    setTimeout(() => {
      showText.value = true
    }, 100)
  })
})
</script>

<template>
  <!-- 主容器 -->
  <div class="container">
    <!-- 背景层：三角形动画 -->
    <div class="bg-layer">
      <div
        v-for="t in triangles"
        :key="t.id"
        class="triangle"
        :style="{
          left: `${t.x}%`,
          top: `${t.y}%`,
          '--size': `${t.size}px`,
          '--duration': `${t.duration}s`,
          '--delay': `${t.delay}s`,
          '--opacity': t.opacity,
          '--base-rotate': `${t.rotate}deg`,
        }"
      ></div>
    </div>
    
    <!-- 内容层：标题和按钮 -->
    <div class="content">
      <!-- 欢迎标题：逐字动画 -->
      <h2 :class="{ 'enter-active': showText, 'exit-active': textExiting }">
        <span>欢</span>
        <span>迎</span>
        <span>使</span>
        <span>用</span>
        <span>本</span>
        <span>电</span>
        <span>力</span>
        <span>模</span>
        <span>拟</span>
        <span>系</span>
        <span>统</span>
      </h2>
      
      <!-- 开始按钮 -->
      <ElButton
        class="start-button"
        type="primary"
        :loading="loading"
        :class="{ 'visible': showText, 'hidden': textExiting }"
        @click="handleStart"
      >
        <template #loading>
          <span class="custom-loading"></span>
        </template>
        开始使用
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
/* ==================== 基础样式重置 ==================== */
* {
  margin: 0;
  padding: 0;
}

/* ==================== 主容器 ==================== */
.container {
  position: fixed;
  inset: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  background-color: #000;
}

/* ==================== 背景层 ==================== */
.bg-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

/* 三角形装饰 */
.triangle {
  position: absolute;
  width: 0;
  height: 0;
  border-left: calc(var(--size) / 2) solid transparent;
  border-right: calc(var(--size) / 2) solid transparent;
  border-bottom: var(--size) solid rgba(255, 255, 255, 0.5);
  opacity: var(--opacity);
  animation:
    floatTriangle var(--duration) ease-in-out infinite alternate,
    blinkTriangle calc(var(--duration) / 2) ease-in-out infinite alternate;
  animation-delay: var(--delay);
}

/* 三角形内部镂空效果 */
.triangle::after {
  content: '';
  position: absolute;
  left: calc(-1 * var(--size) / 2 + 3px);
  top: 4px;
  width: 0;
  height: 0;
  border-left: calc(var(--size) / 2 - 3px) solid transparent;
  border-right: calc(var(--size) / 2 - 3px) solid transparent;
  border-bottom: calc(var(--size) - 6px) solid #000;
}

/* ==================== 内容层 ==================== */
.content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 56px;
}

/* ==================== 标题样式 ==================== */
h2 {
  display: flex;
  font-size: clamp(36px, 8vmin, 130px);
  color: #fff;
  text-align: center;
  text-transform: uppercase;
}

h2 span {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.8s ease-out, transform 0.8s ease-out, filter 0.8s ease-out;
}

/* 进场动画：Loading 消失后逐个浮现 */
h2.enter-active span {
  opacity: 1;
  transform: translateY(0);
}

/* 离场动画：点击开始后快速模糊消失 */
h2.exit-active span {
  filter: blur(20px);
  opacity: 0;
  transform: scale(2);
  transition-duration: 0.3s; /* 加快消失速度 */
}

/* 依次延迟：进场动画 */
h2 span:nth-child(1) { transition-delay: 0.1s; }
h2 span:nth-child(2) { transition-delay: 0.2s; }
h2 span:nth-child(3) { transition-delay: 0.3s; }
h2 span:nth-child(4) { transition-delay: 0.4s; }
h2 span:nth-child(5) { transition-delay: 0.5s; }
h2 span:nth-child(6) { transition-delay: 0.6s; }
h2 span:nth-child(7) { transition-delay: 0.7s; }
h2 span:nth-child(8) { transition-delay: 0.8s; }
h2 span:nth-child(9) { transition-delay: 0.9s; }
h2 span:nth-child(10) { transition-delay: 1.0s; }
h2 span:nth-child(11) { transition-delay: 1.1s; }

/* 依次延迟：离场动画（反向） */
h2.exit-active span:nth-child(1) { transition-delay: 0s; }
h2.exit-active span:nth-child(2) { transition-delay: 0.03s; }
h2.exit-active span:nth-child(3) { transition-delay: 0.06s; }
h2.exit-active span:nth-child(4) { transition-delay: 0.09s; }
h2.exit-active span:nth-child(5) { transition-delay: 0.12s; }
h2.exit-active span:nth-child(6) { transition-delay: 0.15s; }
h2.exit-active span:nth-child(7) { transition-delay: 0.18s; }
h2.exit-active span:nth-child(8) { transition-delay: 0.21s; }
h2.exit-active span:nth-child(9) { transition-delay: 0.24s; }
h2.exit-active span:nth-child(10) { transition-delay: 0.27s; }
h2.exit-active span:nth-child(11) { transition-delay: 0.3s; }

/* ==================== 动画关键帧 ==================== */
@keyframes floatTriangle {
  from {
    transform: translate3d(0, 0, 0) rotate(var(--base-rotate));
  }
  to {
    transform: translate3d(20px, -15px, 0) rotate(calc(var(--base-rotate) + 12deg));
  }
}

@keyframes blinkTriangle {
  from {
    opacity: 0.1;
  }
  to {
    opacity: 0.6;
  }
}

/* ==================== 按钮样式 ==================== */
.start-button {
  margin-top: 40px;
  font-size: 1.2rem;
  padding: 24px 48px;
  border-radius: 50px;
  transition: all 0.3s;
  opacity: 0;
  transform: translateY(20px);
}

/* 按钮显示状态 */
.start-button.visible {
  opacity: 1;
  transform: translateY(0);
  transition-delay: 1.2s; /* 等文字差不多出完了再出按钮 */
}

/* 按钮隐藏状态 */
.start-button.hidden {
  opacity: 0;
  transform: scale(0.8);
  transition-duration: 0.4s;
  transition-delay: 0s;
}

/* 自定义加载动画 */
.custom-loading {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #ffffff;
  animation: custom-spin 0.8s linear infinite;
}

@keyframes custom-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
