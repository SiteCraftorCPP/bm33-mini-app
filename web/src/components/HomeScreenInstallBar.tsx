import { PlusSquare } from 'lucide-react'

import { useHomeScreenInstall } from '../useHomeScreenInstall'

export function HomeScreenInstallBar() {
  const { state, install } = useHomeScreenInstall()

  if (state !== 'show') return null

  return (
    <button
      type="button"
      className="home-install-chip"
      onClick={install}
      aria-label="Добавить магазин на главный экран"
      title="Создать ярлык на рабочем столе"
    >
      <PlusSquare size={15} strokeWidth={2.25} />
      <span>Ярлык</span>
    </button>
  )
}
