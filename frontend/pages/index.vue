<script setup lang="ts">
// if already logged in, skip straight to the dashboard
const { fetchMe } = useAuth()
const config = useRuntimeConfig()

onMounted(async () => {
  const user = await fetchMe()
  if (user) await navigateTo('/dashboard')
})

const signIn = () => {
  window.location.href = `${config.public.apiBase}/api/v1/auth/google`
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center">
    <div class="w-full max-w-sm rounded-2xl bg-gray-900 p-10 shadow-xl text-center">
      <h1 class="text-3xl font-bold tracking-tight text-white mb-1">ViewPilot</h1>
      <p class="text-gray-400 text-sm mb-8">YouTube creator intelligence</p>

      <button
        @click="signIn"
        class="w-full flex items-center justify-center gap-3 rounded-lg bg-white px-5 py-3 text-gray-900 font-medium hover:bg-gray-100 transition"
      >
        <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" class="h-5 w-5" alt="Google" />
        Sign in with Google
      </button>
    </div>
  </div>
</template>
