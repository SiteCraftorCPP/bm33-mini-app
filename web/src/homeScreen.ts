export type HomeScreenStatus = 'unsupported' | 'unknown' | 'added' | 'missed'

const DONE_KEY = 'ches_home_screen_done'

type WebAppHome = {
  addToHomeScreen?: () => void
  checkHomeScreenStatus?: (callback?: (status: string) => void) => void
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
    syncHomeScreenDoneFlag('added')
  })
}

export function isHomeScreenMarkedAdded(): boolean {
  return localStorage.getItem(DONE_KEY) === '1'
}

function normalizeHomeScreenStatus(raw: string | undefined): HomeScreenStatus {
  if (raw === 'added' || raw === 'missed' || raw === 'unsupported' || raw === 'unknown') {
    return raw
  }
  return 'unknown'
}

function syncHomeScreenDoneFlag(status: HomeScreenStatus): void {
  if (status === 'added') {
    localStorage.setItem(DONE_KEY, '1')
    return
  }
  if (status === 'missed') {
    localStorage.removeItem(DONE_KEY)
  }
}

export function shouldShowHomeScreenInstall(status: HomeScreenStatus): boolean {
  return status === 'missed' || status === 'unknown'
}

export function checkHomeScreenStatus(): Promise<HomeScreenStatus> {
  const app = webApp()
  if (!app?.checkHomeScreenStatus) {
    return Promise.resolve(homeScreenSupported() ? 'unknown' : 'unsupported')
  }

  return new Promise((resolve) => {
    let settled = false
    const finish = (raw: string | undefined) => {
      if (settled) return
      settled = true
      window.clearTimeout(timeout)
      const status = normalizeHomeScreenStatus(raw)
      syncHomeScreenDoneFlag(status)
      resolve(status)
    }

    const timeout = window.setTimeout(() => finish('unknown'), 2500)

    if (app.onEvent) {
      app.onEvent('homeScreenChecked', (payload) => {
        finish(payload.status)
      })
    }

    const checker = app.checkHomeScreenStatus!
    try {
      if (checker.length >= 1) {
        checker((status: string) => finish(status))
      } else {
        checker()
      }
    } catch {
      finish('unknown')
    }
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
