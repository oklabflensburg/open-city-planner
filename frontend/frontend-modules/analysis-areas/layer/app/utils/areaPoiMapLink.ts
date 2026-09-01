export function areaPoiMapLink(areaSlug: string, category: string) {
  return { path: '/karte', query: { gebiet: areaSlug, poi: category } }
}
