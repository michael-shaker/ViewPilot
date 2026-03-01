// shared revenue visibility state — used across dashboard, video, and autopsy pages
// useState keeps it in sync across components without prop drilling
export const useRevenue = () => {
  const showRevenue = useState<boolean>('showRevenue', () => false)

  const toggleRevenue = () => {
    showRevenue.value = !showRevenue.value
    localStorage.setItem('vp_show_revenue', String(showRevenue.value))
  }

  return { showRevenue, toggleRevenue }
}
