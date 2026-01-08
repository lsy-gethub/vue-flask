<script setup>
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const goHome = () => {
  router.push('/home')
}
</script>

<template>
  <div class="not-found-page">
    <div class="background-layer"></div>
    <div class="content-layer">
      <div class="content">
        <h1 class="title">404</h1>
        <p class="desc">抱歉，页面不存在或已被移动。</p>
        <p class="path">
          尝试访问：<span>{{ route.fullPath }}</span>
        </p>
        <div class="actions">
          <el-button type="primary" @click="goHome">返回首页</el-button>
          <el-button type="info" plain @click="router.push('/notification')">查看公告</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.not-found-page {
  position: relative;
  width: 100%;
  min-height: 100vh;

  .background-layer {
    position: absolute;
    inset: 0;
    z-index: -1;
    background: linear-gradient(135deg, #4bccef, #f47b2a);
  }

  .content-layer {
    position: relative;
    z-index: 1;
    width: 100%;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .content {
    text-align: center;
    color: #fff;
    padding: 120px 24px 40px 24px;

    .title {
      font-size: 120px;
      letter-spacing: 1rem;
      margin-bottom: 12px;
    }

    .desc {
      font-size: 20px;
      margin-bottom: 16px;
    }

    .path {
      font-size: 14px;
      color: rgba(255, 255, 255, 0.85);
      margin-bottom: 28px;

      span {
        font-family: 'NotoSerifItalic';
        word-break: break-all;
      }
    }

    .actions {
      display: flex;
      gap: 12px;
      justify-content: center;
    }
  }
}
</style>
