// wraps $fetch so every api call automatically goes to the right backend url
// and sends the session cookie along with it
export const useApi = () => {
  const config = useRuntimeConfig()

  return <T>(path: string, options: Record<string, unknown> = {}) =>
    $fetch<T>(`${config.public.apiBase}${path}`, {
      credentials: 'include',
      ...options,
    })
}
