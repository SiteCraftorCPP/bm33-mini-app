export type HomeScreenStatus = 'unsupported' | 'unknown' | 'added' | 'missed'

const DONE_KEY = 'ches_home_screen_done'

type WebAppHome = {
  addToHomeScreen?: () => void
  checkHomeScreenStatus?: () => void
  onEvent?: (event: string, handler: (payload: { status?: string }) => void) => void
}

function webApp(): WebAppHome | undefined {
  return window.Telegram?.WebApp as WebAppHome | undefined
}

export function homeScreenSupported(): boolean {
  return typeof webApp()?.addToHomeScreen === 'function'
}

export function requestAddToHomeScreen(): void {
  webApp()?.addToHomeScreen?.()
}

export function bindHomeScreenEvents(): void {
  const app = webApp()
  if (!app?.onEvent) return
  app.onEvent('homeScreenAdded', () => {
    localStorage.setItem(DONE_KEY, '1')
  })
}

export function checkHomeScreenStatus(): Promise<HomeScreenStatus> {
  const app = webApp()
  if (!app?.checkHomeScreenStatus || !app.onEvent) {
    return Promise.resolve('unsupported')
  }

  return new Promise((resolve) => {
    const timeout = window.setTimeout(() => resolve('unknown'), 2500)
    app.onEvent!('homeScreenChecked', (payload) => {
      window.clearTimeout(timeout)
      const status = payload.status
      if (status === 'added' || status === 'missed' || status === 'unsupported') {
        if (status === 'added') localStorage.setItem(DONE_KEY, '1')
        resolve(status)
      } else {
        resolve('unknown')
      }
    })
    app.checkHomeScreenStatus!()
  })
}

/** @deprecated use HomeScreenInstallBar — auto-prompt скрывал кнопку после первого раза */
export function maybePromptHomeScreen(): void {
  return
}
