import { useEffect, useState } from 'react'

import {
  checkHomeScreenStatus,
  installHomeScreenShortcut,
  isTelegramMiniApp,
  shouldShowHomeScreenInstall,
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
      void checkHomeScreenStatus().then((status) => {
        setState(shouldShowHomeScreenInstall(status) ? 'show' : 'hidden')
      })
    }

    sync()
    const app = window.Telegram?.WebApp as
      | {
          onEvent?: (
            event: string,
            handler: (payload?: { status?: string }) => void,
          ) => void
        }
      | undefined
    app?.onEvent?.('homeScreenAdded', () => setState('hidden'))
    app?.onEvent?.('homeScreenChecked', (payload) => {
      const status = payload?.status
      if (status === 'added') setState('hidden')
      else if (status === 'missed' || status === 'unknown') setState('show')
      else if (status === 'unsupported') setState('hidden')
    })

    const onVisible = () => {
      if (document.visibilityState === 'visible') sync()
    }
    document.addEventListener('visibilitychange', onVisible)

    const retry = window.setTimeout(sync, 800)
    return () => {
      window.clearTimeout(retry)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  return {
    state,
    install: installHomeScreenShortcut,
  }
}
