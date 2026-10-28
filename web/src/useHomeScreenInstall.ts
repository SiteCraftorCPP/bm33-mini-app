import { useEffect, useState } from 'react'

import {
  checkHomeScreenStatus,
  installHomeScreenShortcut,
  isHomeScreenMarkedAdded,
  isTelegramMiniApp,
} from './homeScreen'

export type HomeScreenInstallState = 'loading' | 'hidden' | 'show'

export function useHomeScreenInstall(): {
  state: HomeScreenInstallState
  install: () => void
} {
  const [state, setState] = useState<HomeScreenInstallState>('loading')

  useEffect(() => {
    const sync = () => {
      if (!isTelegramMiniApp()) {
        setState('hidden')
        return
      }
      if (isHomeScreenMarkedAdded()) {
        setState('hidden')
        return
      }
      void checkHomeScreenStatus().then((status) => {
        setState(status === 'added' ? 'hidden' : 'show')
      })
    }

    sync()
    const app = window.Telegram?.WebApp as { onEvent?: (event: string, handler: () => void) => void } | undefined
    app?.onEvent?.('homeScreenAdded', () => setState('hidden'))

    const retry = window.setTimeout(sync, 800)
    return () => window.clearTimeout(retry)
  }, [])

  return {
    state,
    install: installHomeScreenShortcut,
  }
}
