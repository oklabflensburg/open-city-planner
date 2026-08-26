import { defineStore } from 'pinia'

export const useExampleModuleStore = defineStore('example-module', () => {
  const count = ref(0)
  const increment = () => { count.value += 1 }
  return { count, increment }
})
