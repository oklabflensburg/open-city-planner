import { documentationPages } from '~/config/documentation'
import type { DocumentationBlock, DocumentationPage, DocumentationSearchResult } from '~/types/documentation'

export function documentationPath(page: DocumentationPage) {
  return page.slug ? `/dokumentation/${page.slug}` : '/dokumentation'
}

export function findDocumentationPage(slug: string | undefined) {
  return documentationPages.find(page => page.slug === (slug || ''))
}

export function getDocumentationNeighbors(page: DocumentationPage) {
  const index = documentationPages.findIndex(candidate => candidate.slug === page.slug)
  return {
    previous: index > 0 ? documentationPages[index - 1] : undefined,
    next: index >= 0 && index < documentationPages.length - 1 ? documentationPages[index + 1] : undefined
  }
}

export function getDocumentationGroups() {
  const groups = new Map<string, DocumentationPage[]>()
  for (const page of documentationPages) {
    const pages = groups.get(page.group) || []
    pages.push(page)
    groups.set(page.group, pages)
  }
  return Array.from(groups, ([label, pages]) => ({ label, pages }))
}

export function searchDocumentation(rawQuery: string): DocumentationSearchResult[] {
  const terms = normalize(rawQuery).split(' ').filter(Boolean)
  if (!terms.length) return []

  const results: DocumentationSearchResult[] = []
  for (const page of documentationPages) {
    const pageText = normalize([page.title, page.navTitle, page.description, ...page.keywords].join(' '))
    const pageScore = matchScore(pageText, terms) * 4
    if (pageScore) {
      results.push({ page, excerpt: page.description, score: pageScore })
    }

    for (const section of page.sections) {
      const sectionText = normalize([section.title, ...section.blocks.map(blockText)].join(' '))
      const score = matchScore(sectionText, terms)
      if (score) {
        results.push({ page, section, excerpt: excerptFor(section.blocks), score: score + pageScore })
      }
    }
  }

  return results
    .sort((left, right) => right.score - left.score || left.page.title.localeCompare(right.page.title, 'de'))
    .filter((result, index, all) => all.findIndex(candidate => candidate.page.slug === result.page.slug && candidate.section?.id === result.section?.id) === index)
    .slice(0, 10)
}

function matchScore(text: string, terms: string[]) {
  if (!terms.every(term => text.includes(term))) return 0
  return terms.reduce((score, term) => score + text.split(term).length - 1, 0)
}

function normalize(value: string) {
  return value
    .toLocaleLowerCase('de')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function blockText(block: DocumentationBlock) {
  if (block.type === 'paragraph') return block.text
  if (block.type === 'list') return block.items.join(' ')
  if (block.type === 'steps') return block.items.flatMap(item => [item.title, item.text]).join(' ')
  if (block.type === 'callout') return `${block.title} ${block.text}`
  if (block.type === 'code') return block.code
  if (block.type === 'image') return `${block.alt} ${block.caption || ''}`
  if (block.type === 'links') return block.items.flatMap(item => [item.label, item.description || '']).join(' ')
  return [...block.headers, ...block.rows.flat()].join(' ')
}

function excerptFor(blocks: DocumentationBlock[]) {
  const text = blocks.map(blockText).find(Boolean) || ''
  return text.length > 170 ? `${text.slice(0, 167).trim()}…` : text
}
