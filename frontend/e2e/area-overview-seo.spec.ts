import { expect, test } from '@playwright/test'

type StructuredEntity = {
  '@type'?: string
  numberOfItems?: number
  itemListElement?: Array<{ position: number, name: string, url: string }>
  mainEntity?: Array<{
    name: string
    acceptedAnswer: { text: string }
  }>
}

test('area overview renders dynamic FAQ, links and structured data in SSR HTML', async ({ page, request }) => {
  const apiResponse = await request.get('http://127.0.0.1:8010/api/v1/analysis-areas')
  expect(apiResponse.ok()).toBe(true)
  const areas = await apiResponse.json() as Array<{
    area_type: 'MUNICIPALITY' | 'DISTRICT' | 'QUARTER'
    name: string
    slug: string
  }>
  const districts = areas
    .filter(area => area.area_type === 'DISTRICT')
    .sort((left, right) => left.name.localeCompare(right.name, 'de'))
  const quarterCount = areas.filter(area => area.area_type === 'QUARTER').length

  const response = await request.get('/gebiete')
  expect(response.ok()).toBe(true)
  const html = await response.text()

  for (const value of [
    'Häufige Fragen zu Flensburgs Stadtteilen und Quartieren',
    'Wie viele Stadtteile hat Flensburg?',
    'Wie viele Quartiere hat Flensburg?',
    'BreadcrumbList',
    'CollectionPage',
    'ItemList',
    'FAQPage',
    '/dokumentation/methodik'
  ]) {
    expect(html).toContain(value)
  }
  expect(html).toContain(`${districts.length} Stadtteile`)
  expect(html).toContain(`${quarterCount} veröffentlichte Quartiere`)
  for (const district of districts) {
    expect(html).toContain(`/gebiete/${district.slug}`)
  }
  const structuredScripts = [...html.matchAll(
    /<script[^>]+type="application\/ld\+json"[^>]*>(.*?)<\/script>/gs
  )]
  const structuredData = structuredScripts.flatMap((match) => {
    const value = JSON.parse(match[1]!) as StructuredEntity | StructuredEntity[]
    return Array.isArray(value) ? value : [value]
  })
  const structuredTypes = structuredData.map(entity => entity['@type'])
  expect(structuredTypes).toEqual(expect.arrayContaining([
    'BreadcrumbList',
    'CollectionPage',
    'ItemList',
    'FAQPage'
  ]))
  const districtList = structuredData.find(entity => entity['@type'] === 'ItemList')
  expect(districtList?.numberOfItems).toBe(districts.length)
  expect(districtList?.itemListElement).toEqual(districts.map((district, index) => ({
    '@type': 'ListItem',
    position: index + 1,
    name: district.name,
    url: expect.stringMatching(new RegExp(`/gebiete/${district.slug}$`))
  })))

  await page.goto('/gebiete')
  const districtLinks = page.getByRole('list', { name: 'Alphabetische Liste der Stadtteile' }).getByRole('link')
  await expect(districtLinks).toHaveCount(districts.length)
  expect(await districtLinks.allTextContents()).toEqual(districts.map(area => area.name))
  const visibleQuestions = await page
    .locator('section[aria-labelledby="area-faq-heading"] article h3')
    .allTextContents()
  const faqPage = structuredData.find(entity => entity['@type'] === 'FAQPage')
  expect(faqPage?.mainEntity?.map(entity => entity.name)).toEqual(visibleQuestions)
  const districtAnswer = faqPage?.mainEntity?.find(
    entity => entity.name === 'Welche Stadtteile gehören zu Flensburg?'
  )?.acceptedAnswer.text
  for (const district of districts) expect(districtAnswer).toContain(district.name)
})

test('area overview stays responsive and social preview remains noindex', async ({ page, request }) => {
  const viewports = [
    { width: 320, height: 568 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1024, height: 768 },
    { width: 1280, height: 800 },
    { width: 1440, height: 900 }
  ]

  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await page.goto('/gebiete')
    await expect(page.getByRole('heading', {
      name: 'Häufige Fragen zu Flensburgs Stadtteilen und Quartieren'
    })).toBeVisible()
    const sizes = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth
    }))
    expect(sizes.content).toBeLessThanOrEqual(sizes.viewport)
  }

  const socialPreviewResponse = await request.get('/gebiete?social-preview=1')
  const socialPreviewHtml = await socialPreviewResponse.text()
  expect(socialPreviewHtml).toContain('noindex,nofollow')
})
