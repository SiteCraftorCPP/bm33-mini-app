export type HomeScreenStatus = 'unsupported' | 'unknown' | 'added' | 'missed'

const DONE_KEY = 'ches_home_screen_done'

type WebAppHome = {
  addToHomeScreen?: () => void
  checkHomeScreenStatus?: () => void
  onEvent?: (event: string, handler: (payload: { status?: string }) => void) => void
  initData?: string
  platform?: string
  showAlert?: (message: string, callback?: () => void) => void
}

function webApp(): WebAppHome | undefined {
  return window.Telegram?.WebApp as WebAppHome | undefined
}

/** Открыто внутри Telegram Mini App (не браузер с ches-hockey.ru). */
export function isTelegramMiniApp(): boolean {
  const app = webApp()
  if (!app) return false
  return Boolean(app.initData?.length)
}

export function homeScreenSupported(): boolean {
  return typeof webApp()?.addToHomeScreen === 'function'
}

export function requestAddToHomeScreen(): boolean {
  const fn = webApp()?.addToHomeScreen
  if (typeof fn !== 'function') return false
  fn()
  return true
}

export function bindHomeScreenEvents(): void {
  const app = webApp()
  if (!app?.onEvent) return
  app.onEvent('homeScreenAdded', () => {
    localStorage.setItem(DONE_KEY, '1')
  })
}

export function isHomeScreenMarkedAdded(): boolean {
  return localStorage.getItem(DONE_KEY) === '1'
}

export function checkHomeScreenStatus(): Promise<HomeScreenStatus> {
  const app = webApp()
  if (!app?.checkHomeScreenStatus || !app.onEvent) {
    return Promise.resolve('missed')
  }

  return new Promise((resolve) => {
    const timeout = window.setTimeout(() => resolve('missed'), 2500)
    app.onEvent!('homeScreenChecked', (payload) => {
      window.clearTimeout(timeout)
      const status = payload.status
      if (status === 'added' || status === 'missed' || status === 'unsupported') {
        if (status === 'added') localStorage.setItem(DONE_KEY, '1')
        resolve(status === 'unsupported' ? 'missed' : status)
      } else {
        resolve('missed')
      }
    })
    app.checkHomeScreenStatus!()
  })
}

export function maybePromptHomeScreen(): void {
  return
}

export function installHomeScreenShortcut(): void {
  if (requestAddToHomeScreen()) {
    window.Telegram?.WebApp.HapticFeedback?.impactOccurred('light')
    return
  }
  const app = webApp()
  const platform = app?.platform ?? ''
  if (platform === 'android' || platform === 'ios') {
    app?.showAlert?.(
      'Не удалось открыть установку ярлыка. Обновите Telegram до последней версии или используйте меню ⋮ → «Создать ярлык».',
    )
  } else {
    app?.showAlert?.('Ярлык на главный экран доступен в мобильном Telegram (Android / iPhone).')
  }
}
