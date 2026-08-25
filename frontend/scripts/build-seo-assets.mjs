import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const publicDirectory = fileURLToPath(new URL('../public/', import.meta.url))
const logo = await readFile(new URL('../public/branding/ok-lab-flensburg-email.png', import.meta.url))

await Promise.all([
  writeSquareIcon('favicon-96x96.png', 96, 8),
  writeSquareIcon('apple-touch-icon.png', 180, 16),
  writeSquareIcon('web-app-manifest-192x192.png', 192, 18),
  writeSquareIcon('web-app-manifest-512x512.png', 512, 48),
  writeSocialCard()
])

async function writeSquareIcon(filename, size, padding) {
  const renderedLogo = await sharp(logo)
    .resize(size - (padding * 2), size - (padding * 2), { fit: 'inside' })
    .png()
    .toBuffer()

  await sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: '#ffffff'
    }
  })
    .composite([{ input: renderedLogo, gravity: 'centre' }])
    .png({ compressionLevel: 9 })
    .toFile(`${publicDirectory}${filename}`)
}

async function writeSocialCard() {
  const renderedLogo = await sharp(logo)
    .resize(250, 300, { fit: 'inside' })
    .png()
    .toBuffer()
  const card = Buffer.from(`
    <svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
      <rect width="1200" height="630" fill="#f8fafc"/>
      <rect width="28" height="630" fill="#154d73"/>
      <circle cx="180" cy="315" r="160" fill="#ffffff" stroke="#dbe5ec" stroke-width="4"/>
      <text x="430" y="205" fill="#154d73" font-family="sans-serif" font-size="26" font-weight="700" letter-spacing="3">OPEN CITY PLANNER</text>
      <text x="430" y="290" fill="#0f172a" font-family="sans-serif" font-size="72" font-weight="800">Stadtplaner</text>
      <text x="430" y="355" fill="#475569" font-family="sans-serif" font-size="31">Offene Stadtentwicklung</text>
      <text x="430" y="398" fill="#475569" font-family="sans-serif" font-size="31">und Standortdaten für Flensburg</text>
      <line x1="430" y1="445" x2="1080" y2="445" stroke="#cbd5e1" stroke-width="3"/>
      <text x="430" y="505" fill="#154d73" font-family="sans-serif" font-size="27" font-weight="700">OK Lab Flensburg</text>
    </svg>
  `)

  await sharp(card)
    .composite([{ input: renderedLogo, left: 55, top: 165 }])
    .png({ compressionLevel: 9 })
    .toFile(`${publicDirectory}branding/stadtplaner-social-card.png`)
}
