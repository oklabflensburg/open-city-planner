export type OsmTags = Record<string, string>

export type FormattedOsmTag = {
  label: string
  value: string
}

const keyTranslations: Record<string, string> = {
  amenity: 'Kategorie',
  building: 'Gebäude',
  shop: 'Geschäft',
  tourism: 'Tourismus',
  leisure: 'Freizeit',
  historic: 'Historisch',
  office: 'Büro',
  craft: 'Handwerk',
  healthcare: 'Gesundheit',
  religion: 'Religion',
  denomination: 'Konfession',
  cuisine: 'Küche',
  wheelchair: 'Barrierefreiheit',
  access: 'Zugang',
  surface: 'Oberfläche',
  operator: 'Betreiber',
  brand: 'Marke',
  opening_hours: 'Öffnungszeiten',
  service_times: 'Gottesdienstzeiten',
  website: 'Website',
  phone: 'Telefon',
  email: 'E-Mail',
  description: 'Beschreibung',
  natural: 'Naturmerkmal',
  public_transport: 'Öffentlicher Verkehr',
  railway: 'Bahnverkehr',
  parking: 'Parken',
  sport: 'Sport',
  club: 'Verein',
  level: 'Ebene',
  indoor: 'Innenbereich',
  ref: 'Referenz'
}

const valueTranslations: Record<string, Record<string, string>> = {
  amenity: {
    place_of_worship: 'Andachtsstätte', restaurant: 'Restaurant', cafe: 'Café', bar: 'Bar',
    pub: 'Kneipe', school: 'Schule', kindergarten: 'Kindergarten', library: 'Bibliothek',
    hospital: 'Krankenhaus', pharmacy: 'Apotheke', parking: 'Parkplatz', toilets: 'Toilette',
    bench: 'Sitzbank', drinking_water: 'Trinkwasser', community_centre: 'Gemeinschaftszentrum',
    townhall: 'Rathaus', bank: 'Bank', doctors: 'Arztpraxis', dentist: 'Zahnarztpraxis',
    fire_station: 'Feuerwache', police: 'Polizei', post_office: 'Postfiliale'
  },
  building: {
    church: 'Kirche', cathedral: 'Kathedrale', chapel: 'Kapelle', mosque: 'Moschee',
    synagogue: 'Synagoge', temple: 'Tempel', school: 'Schulgebäude', residential: 'Wohngebäude',
    commercial: 'Geschäftsgebäude', industrial: 'Industriegebäude', apartments: 'Mehrfamilienhaus',
    retail: 'Einzelhandelsgebäude', office: 'Bürogebäude', public: 'Öffentliches Gebäude',
    yes: 'Gebäude'
  },
  religion: {
    christian: 'Christentum', muslim: 'Islam', jewish: 'Judentum', buddhist: 'Buddhismus',
    hindu: 'Hinduismus', sikh: 'Sikhismus'
  },
  denomination: {
    protestant: 'Evangelisch', roman_catholic: 'Römisch-katholisch', catholic: 'Katholisch',
    lutheran: 'Lutherisch', reformed: 'Reformiert', orthodox: 'Orthodox', baptist: 'Baptistisch',
    methodist: 'Methodistisch'
  },
  shop: {
    clothes: 'Mode / Bekleidung', supermarket: 'Supermarkt', bakery: 'Bäckerei',
    shoes: 'Schuhgeschäft', department_store: 'Warenhaus', charity: 'Sozialkaufhaus',
    convenience: 'Lebensmittelgeschäft', books: 'Buchhandlung', florist: 'Blumengeschäft',
    hairdresser: 'Friseursalon', optician: 'Optikgeschäft', vacant: 'Leerstehendes Geschäft'
  },
  tourism: {
    hotel: 'Hotel', hostel: 'Hostel', guest_house: 'Pension', museum: 'Museum',
    attraction: 'Sehenswürdigkeit', information: 'Touristeninformation', viewpoint: 'Aussichtspunkt'
  },
  leisure: {
    park: 'Park', playground: 'Spielplatz', sports_centre: 'Sportzentrum', pitch: 'Sportplatz',
    swimming_pool: 'Schwimmbad', fitness_centre: 'Fitnessstudio', garden: 'Garten'
  },
  historic: {
    monument: 'Denkmal', memorial: 'Gedenkstätte', castle: 'Schloss oder Burg', ruins: 'Ruine',
    archaeological_site: 'Archäologische Stätte', church: 'Historische Kirche'
  },
  healthcare: {
    doctor: 'Arztpraxis', dentist: 'Zahnarztpraxis', pharmacy: 'Apotheke',
    physiotherapist: 'Physiotherapie', hospital: 'Krankenhaus', clinic: 'Klinik'
  },
  wheelchair: { yes: 'Ja', no: 'Nein', limited: 'Eingeschränkt', designated: 'Ausgewiesen' },
  access: {
    yes: 'Ja', no: 'Nein', private: 'Privat', public: 'Öffentlich', customers: 'Nur für Kunden',
    permissive: 'Geduldet', designated: 'Ausgewiesen', limited: 'Eingeschränkt'
  },
  surface: {
    paved: 'Befestigt', asphalt: 'Asphalt', concrete: 'Beton', paving_stones: 'Pflastersteine',
    unpaved: 'Unbefestigt', gravel: 'Schotter', grass: 'Rasen', ground: 'Naturboden'
  },
  office: {
    government: 'Behörde', company: 'Unternehmen', association: 'Verband',
    lawyer: 'Anwaltskanzlei', insurance: 'Versicherung', estate_agent: 'Immobilienbüro'
  },
  natural: {
    tree: 'Baum', wood: 'Wald', water: 'Gewässer', wetland: 'Feuchtgebiet',
    beach: 'Strand', grassland: 'Grünland'
  },
  indoor: { yes: 'Ja', no: 'Nein' }
}

const generalValues: Record<string, string> = {
  yes: 'Ja', no: 'Nein', private: 'Privat', public: 'Öffentlich', customers: 'Nur für Kunden',
  permissive: 'Geduldet', designated: 'Ausgewiesen', limited: 'Eingeschränkt', unknown: 'Unbekannt'
}

const verbatimValueKeys = new Set([
  'name', 'name:de', 'official_name', 'alt_name', 'operator', 'brand',
  'addr:street', 'addr:city', 'addr:housenumber', 'addr:postcode',
  'opening_hours', 'service_times', 'website', 'contact:website', 'email', 'contact:email',
  'phone', 'contact:phone', 'wikidata', 'wikipedia', 'description', 'ref'
])

const categoryKeys = [
  'shop', 'amenity', 'office', 'craft', 'tourism', 'historic', 'leisure',
  'healthcare', 'building', 'natural', 'public_transport', 'railway'
] as const

const worshipBuildings = new Set(['church', 'cathedral', 'chapel', 'mosque', 'synagogue', 'temple'])

export function humanizeOsmToken(value: string): string {
  const readable = value.trim().replaceAll('_', ' ').replaceAll(':', ' ')
  return readable ? readable.charAt(0).toLocaleUpperCase('de-DE') + readable.slice(1) : ''
}

export function translateOsmKey(key: string): string {
  return keyTranslations[key] || humanizeOsmToken(key)
}

export function translateOsmValue(
  key: string,
  value: string | null | undefined,
  tags: OsmTags = {}
): string {
  if (value == null || value.trim() === '') return ''
  const raw = value.trim()
  if (verbatimValueKeys.has(key)) return raw
  const worshipBuilding = tags.building
  if (key === 'amenity' && raw === 'place_of_worship' && worshipBuilding && worshipBuildings.has(worshipBuilding)) {
    return valueTranslations.building?.[worshipBuilding] || humanizeOsmToken(worshipBuilding)
  }
  return raw.split(';').map((part) => {
    const normalized = part.trim()
    return valueTranslations[key]?.[normalized] || generalValues[normalized] || humanizeOsmToken(normalized)
  }).join(', ')
}

export function formatOsmTag(
  key: string,
  value: string | null | undefined,
  tags: OsmTags = {}
): FormattedOsmTag | null {
  const translated = translateOsmValue(key, value, tags)
  return translated ? { label: translateOsmKey(key), value: translated } : null
}

export function localizedOsmName(tags: OsmTags, fallback?: string | null): string | null {
  return tags['name:de']?.trim() || tags.name?.trim() || fallback?.trim() || null
}

export function formatOsmCategory(tags: OsmTags): FormattedOsmTag {
  const key = categoryKeys.find(candidate => tags[candidate]?.trim())
  if (!key) return { label: 'Kategorie', value: 'Nicht kategorisiert' }
  return { label: 'Kategorie', value: translateOsmValue(key, tags[key], tags) }
}

export const osmDetailKeys = [
  'religion', 'denomination', 'cuisine', 'wheelchair', 'access', 'surface',
  'healthcare', 'historic', 'service_times'
] as const
