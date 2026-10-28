import { useEffect, useState } from 'react'

import {
  checkHomeScreenStatus,
  homeScreenSupported,
  requestAddToHomeScreen,
} from './homeScreen'

export type HomeScreenInstallState = 'loading' | 'hidden' | 'show'

export function useHomeScreenInstall(): {
  state: HomeScreenInstallState
  install: () => void
} {
  const [state, setState] = useState<HomeScreenInstallState>('loading')

  useEffect(() => {
    if (!homeScreenSupported()) {
      setState('hidden')
      return
    }

    let cancelled = false
    const hide = () => {
      if (!cancelled) setState('hidden')
    }

    const app = window.Telegram?.WebApp as { onEvent?: (event: string, handler: () => void) => void } | undefined
    app?.onEvent?.('homeScreenAdded', hide)

    void checkHomeScreenStatus().then((status) => {
      if (cancelled) return
      setState(status === 'added' ? 'hidden' : 'show')
    })

    return () => {
      cancelled = true
    }
  }, [])

  return {
    state,
    install: () => {
      requestAddToHomeScreen()
      window.Telegram?.WebApp.HapticFeedback?.impactOccurred('light')
    },
  }
}
