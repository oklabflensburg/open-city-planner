const poiCategoryLabels: Readonly<Record<string, string>> = {
  restaurant: 'Restaurants',
  cafe: 'Cafés',
  fast_food: 'Schnellrestaurants',
  bar: 'Bars',
  pub: 'Kneipen',
  ice_cream: 'Eisdielen',
  supermarket: 'Supermärkte',
  convenience: 'Lebensmittelgeschäfte',
  bakery: 'Bäckereien',
  butcher: 'Metzgereien',
  greengrocer: 'Obst- und Gemüseläden',
  beverages: 'Getränkemärkte',
  school: 'Schulen',
  kindergarten: 'Kindertagesstätten',
  college: 'Hochschulen',
  university: 'Universitäten',
  library: 'Bibliotheken',
  hospital: 'Krankenhäuser',
  clinic: 'Kliniken',
  doctors: 'Arztpraxen',
  dentist: 'Zahnarztpraxen',
  pharmacy: 'Apotheken',
  theatre: 'Theater',
  cinema: 'Kinos',
  arts_centre: 'Kulturzentren',
  museum: 'Museen',
  gallery: 'Galerien',
  bank: 'Banken',
  atm: 'Geldautomaten',
  townhall: 'Rathäuser',
  courthouse: 'Gerichte',
  police: 'Polizeidienststellen',
  post_office: 'Postfilialen',
  hotel: 'Hotels',
  hostel: 'Hostels',
  guest_house: 'Pensionen',
  park: 'Parks',
  playground: 'Spielplätze',
  sports_centre: 'Sportzentren',
  pitch: 'Sportplätze',
  swimming_pool: 'Schwimmbäder',
  fitness_centre: 'Fitnessstudios',
  garden: 'Gärten',
  attraction: 'Sehenswürdigkeiten',
  information: 'Touristeninformationen',
  viewpoint: 'Aussichtspunkte',
  clothes: 'Modegeschäfte',
  shoes: 'Schuhgeschäfte',
  department_store: 'Warenhäuser',
  books: 'Buchhandlungen',
  florist: 'Blumengeschäfte',
  hairdresser: 'Friseursalons',
  optician: 'Optikgeschäfte'
}

export function getPoiCategoryLabel(category: string | null | undefined) {
  const key = category?.trim()
  if (!key) return 'Sonstige Orte und Einrichtungen'
  const known = poiCategoryLabels[key]
  if (known) return known
  const readable = key.replace(/[_:-]+/g, ' ').replace(/\s+/g, ' ')
  return readable.charAt(0).toLocaleUpperCase('de-DE') + readable.slice(1)
}

export function isPoiCategoryToken(category: unknown): category is string {
  return typeof category === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$/.test(category)
}

export function poiFromQuery(value: unknown): string | null {
  return isPoiCategoryToken(value) ? value : null
}

export function withPoiQuery(url: URL, poi: string | null): URL {
  const next = new URL(url)
  next.searchParams.delete('poi')
  if (poi) next.searchParams.set('poi', poi)
  return next
}

export function withoutPoiQuery<T extends Record<string, unknown>>(query: T) {
  const result = { ...query }
  delete result.poi
  return result
}
