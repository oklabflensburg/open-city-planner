export function useExampleModuleGreeting(count: Ref<number>) {
  return computed(() => count.value === 1
    ? 'Der gemeinsame Pinia-Store wurde einmal aktualisiert.'
    : `Der gemeinsame Pinia-Store wurde ${count.value} Mal aktualisiert.`)
}
