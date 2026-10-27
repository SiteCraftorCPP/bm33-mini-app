export type HomeScreenStatus = 'unsupported' | 'unknown' | 'added' | 'missed'

export function homeScreenSupported(): boolean {
  const webApp = window.Telegram?.WebApp as { addToHomeScreen?: () => void } | undefined
  return typeof webApp?.addToHomeScreen === 'function'
}

export function requestAddToHomeScreen(): void {
  const webApp = window.Telegram?.WebApp as { addToHomeScreen?: () => void } | undefined
  webApp?.addToHomeScreen?.()
}

export function checkHomeScreenStatus(): Promise<HomeScreenStatus> {
  const webApp = window.Telegram?.WebApp as {
    checkHomeScreenStatus?: () => void
    onEvent?: (event: string, handler: (payload: { status?: string }) => void) => void
  } | undefined

  if (!webApp?.checkHomeScreenStatus || !webApp.onEvent) {
    return Promise.resolve('unsupported')
  }

  return new Promise((resolve) => {
    const timeout = window.setTimeout(() => resolve('unknown'), 2500)
    webApp.onEvent!('homeScreenChecked', (payload) => {
      window.clearTimeout(timeout)
      const status = payload.status
      if (status === 'added' || status === 'missed' || status === 'unsupported') {
        resolve(status)
      } else {
        resolve('unknown')
      }
    })
    webApp.checkHomeScreenStatus!()
  })
}
