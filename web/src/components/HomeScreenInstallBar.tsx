import { PlusSquare } from 'lucide-react'

import { useHomeScreenInstall } from '../useHomeScreenInstall'

export function HomeScreenInstallBar() {
  const { state, install } = useHomeScreenInstall()

  if (state !== 'show') return null

  return (
    <section className="home-install" aria-label="Ярлык на главный экран">
      <button type="button" className="home-install__button" onClick={install}>
        <span className="home-install__icon" aria-hidden>
          <PlusSquare size={22} />
        </span>
        <span className="home-install__copy">
          <strong>Добавить на главный экран</strong>
          <small>Telegram покажет системный диалог «Создать ярлык»</small>
        </span>
      </button>
    </section>
  )
}
