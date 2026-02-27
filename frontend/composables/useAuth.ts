// global user state + auth helpers used by pages and middleware
export interface User {
  id: string
  email: string
  name: string
  picture_url: string | null
}

export const useAuth = () => {
  const api = useApi()
  const user = useState<User | null>('user', () => null)

  // fetch the current user from the backend — returns null if not logged in
  const fetchMe = async (): Promise<User | null> => {
    try {
      const data = await api<User>('/api/v1/auth/me')
      user.value = data
      return data
    } catch {
      user.value = null
      return null
    }
  }

  // clear session on backend + wipe local state
  // always navigates home even if the server call fails — no point staying logged in locally
  const logout = async () => {
    try {
      await api('/api/v1/auth/logout', { method: 'POST' })
    } catch {
      console.warn('logout request failed — clearing local session anyway')
    }
    user.value = null
    await navigateTo('/')
  }

  return { user, fetchMe, logout }
}
