<template>
  <div class="app-shell">
    <nav class="topnav">
      <router-link to="/projects" class="brand">GlobeEdge</router-link>
      <div class="nav-links">
        <router-link to="/projects">Projects</router-link>
        <router-link to="/dashboard">Dashboard</router-link>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.topnav {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 0 24px;
  height: 48px;
  background: var(--card-bg, #1f2937);
  border-bottom: 1px solid var(--border, #374151);
}
.brand {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  text-decoration: none;
  font-family: 'IBM Plex Sans', sans-serif;
  letter-spacing: -0.02em;
}
.nav-links {
  display: flex;
  gap: 20px;
}
.nav-links a {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.nav-links a:hover,
.nav-links a.router-link-active {
  color: var(--text-primary);
  border-bottom-color: #3b82f6;
}
.main-content {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
}
</style>
