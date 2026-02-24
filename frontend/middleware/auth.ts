// runs before any protected page loads — redirects to login if not logged in
export default defineNuxtRouteMiddleware(async () => {
  const { fetchMe } = useAuth()
  const user = await fetchMe()
  if (!user) {
    return navigateTo('/')
  }
})
