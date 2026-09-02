<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <nav class="topbar" aria-label="主导航">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">比</span>
        <span><strong>国补比价</strong><small>个人本地工具</small></span>
      </RouterLink>
      <div class="nav-links">
        <RouterLink to="/">比价工作台</RouterLink>
        <RouterLink to="/history">历史价格</RouterLink>
        <RouterLink to="/settings">设置</RouterLink>
      </div>
    </nav>
    <RouterView />
    <footer>所有价格均需以平台结算页为准 · 工具不保存账号、密码或 Cookie</footer>
  </div>
</template>
