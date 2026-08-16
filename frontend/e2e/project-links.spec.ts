import { expect, test } from '@playwright/test'

const repositoryUrl = 'https://github.com/oklabflensburg/open-city-planner'
const mastodonUrl = 'https://norden.social/@oklabflensburg'

for (const viewport of [
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'mobile', width: 390, height: 844 }
]) {
  test(`repository links are visible and safe on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.goto('/ueber-das-projekt')

    await expect(page.getByRole('heading', { name: 'Open Source' })).toBeVisible()
    const repositoryLink = page.locator('main').getByRole('link', { name: /Quellcode auf GitHub/ }).first()
    await expect(repositoryLink).toBeVisible()
    await expect(repositoryLink).toHaveAttribute('href', repositoryUrl)
    await expect(repositoryLink).toHaveAttribute('target', '_blank')
    await expect(repositoryLink).toHaveAttribute('rel', 'noopener noreferrer')

    const footerLink = page.locator('footer').getByRole('link', { name: /Quellcode auf GitHub/ })
    await footerLink.scrollIntoViewIfNeeded()
    await expect(footerLink).toBeVisible()
    await expect(footerLink).toHaveAttribute('href', repositoryUrl)

    const mastodonLink = page.locator('footer').getByRole('link', { name: /Mastodon.*@oklabflensburg@norden.social/ })
    await expect(mastodonLink).toBeVisible()
    await expect(mastodonLink).toHaveAttribute('href', mastodonUrl)
    await expect(mastodonLink).toHaveAttribute('target', '_blank')
    await expect(mastodonLink).toHaveAttribute('rel', 'me noopener noreferrer')
  })
}
