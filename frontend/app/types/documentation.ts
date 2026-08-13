export type DocumentationAudience = 'public' | 'login' | 'verwaltung'

export type DocumentationBlock =
  | { type: 'paragraph', text: string }
  | { type: 'list', items: string[], ordered?: boolean }
  | { type: 'steps', items: Array<{ title: string, text: string }> }
  | { type: 'callout', variant: 'info' | 'tip' | 'warning' | 'important', title: string, text: string }
  | { type: 'code', code: string, language?: string }
  | { type: 'image', src: string, alt: string, caption?: string }
  | { type: 'links', items: Array<{ label: string, to: string, description?: string }> }
  | { type: 'table', headers: string[], rows: string[][] }

export interface DocumentationSection {
  id: string
  title: string
  audience?: DocumentationAudience
  blocks: DocumentationBlock[]
}

export interface DocumentationPage {
  slug: string
  title: string
  navTitle: string
  description: string
  group: string
  keywords: string[]
  audience: DocumentationAudience
  sections: DocumentationSection[]
}

export interface DocumentationSearchResult {
  page: DocumentationPage
  section?: DocumentationSection
  excerpt: string
  score: number
}
