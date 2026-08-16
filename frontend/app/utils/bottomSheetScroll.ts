import { nextTick } from 'vue'

export type BottomSheetContentKey = string | number | null

export function shouldResetBottomSheetScroll(
  open: boolean,
  wasOpen: boolean | undefined,
  contentKey: BottomSheetContentKey,
  previousContentKey: BottomSheetContentKey | undefined
) {
  return open && (!wasOpen || contentKey !== previousContentKey)
}

export async function resetBottomSheetScroll(
  getScroller: () => Pick<HTMLElement, 'scrollTo'> | null
) {
  await nextTick()
  getScroller()?.scrollTo({ top: 0, behavior: 'auto' })
}
