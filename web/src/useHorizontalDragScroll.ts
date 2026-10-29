import { useCallback, useRef } from 'react'

/** Горизонтальный скролл зажатием ЛКМ + колёсико над полосой (desktop). */
export function useHorizontalDragScroll<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const drag = useRef({ active: false, startX: 0, scrollLeft: 0, moved: false })

  const onMouseDown = useCallback((event: React.MouseEvent) => {
    if (event.button !== 0) return
    const el = ref.current
    if (!el) return
    drag.current = {
      active: true,
      startX: event.pageX,
      scrollLeft: el.scrollLeft,
      moved: false,
    }
  }, [])

  const onMouseMove = useCallback((event: React.MouseEvent) => {
    if (!drag.current.active) return
    const el = ref.current
    if (!el) return
    const walk = event.pageX - drag.current.startX
    if (Math.abs(walk) > 4) drag.current.moved = true
    el.scrollLeft = drag.current.scrollLeft - walk
  }, [])

  const endDrag = useCallback(() => {
    drag.current.active = false
  }, [])

  const onClickCapture = useCallback((event: React.MouseEvent) => {
    if (drag.current.moved) {
      event.preventDefault()
      event.stopPropagation()
      drag.current.moved = false
    }
  }, [])

  const onWheel = useCallback((event: React.WheelEvent) => {
    const el = ref.current
    if (!el) return
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return
    el.scrollLeft += event.deltaY
    event.preventDefault()
  }, [])

  return {
    ref,
    dragScrollProps: {
      onMouseDown,
      onMouseMove,
      onMouseUp: endDrag,
      onMouseLeave: endDrag,
      onClickCapture,
      onWheel,
      className: 'horizontal-drag-scroll',
    },
  }
}
