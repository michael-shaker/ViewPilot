export default defineNuxtConfig({
  css: ['~/assets/css/main.css'],

  postcss: {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  },

  runtimeConfig: {
    public: {
      // the backend api url — override in production via NUXT_PUBLIC_API_BASE env var
      apiBase: 'http://localhost:8000',
    },
  },

  compatibilityDate: '2024-11-01',
})
