// runs once on the client when the app first loads
// reads the saved preference from localStorage so the toggle remembers its last state
export default defineNuxtPlugin(() => {
  const { showRevenue } = useRevenue()
  const stored = localStorage.getItem('vp_show_revenue')
  if (stored !== null) showRevenue.value = stored === 'true'
})
