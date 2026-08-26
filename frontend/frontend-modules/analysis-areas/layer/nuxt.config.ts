import { fileURLToPath } from 'node:url'

export default defineNuxtConfig({
  components: [{
    path: fileURLToPath(new URL('./app/components', import.meta.url)),
    pathPrefix: false,
    global: true
  }]
})
