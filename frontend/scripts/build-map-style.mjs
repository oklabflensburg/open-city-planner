import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const source = 'versatiles-shortbread'
const kinds = values => ['in', ['get', 'kind'], ['literal', values]]
const name = ['coalesce', ['get', 'name_de'], ['get', 'name']]
const zoomWidth = (...stops) => ['interpolate', ['linear'], ['zoom'], ...stops.flat()]
const vectorLayer = (id, type, sourceLayer, options = {}) => ({
  id, type, source, 'source-layer': sourceLayer, ...options
})

const style = {
  version: 8,
  name: 'Stadtplanner Light',
  metadata: {
    'stadtplanner:purpose': 'Ruhige, performante Orientierungskarte für fachliche GIS-Overlays',
    'stadtplanner:schema': 'Shortbread 1.1',
    'stadtplanner:generatedBy': 'frontend/scripts/build-map-style.mjs'
  },
  glyphs: 'https://tiles.versatiles.org/assets/glyphs/{fontstack}/{range}.pbf',
  sources: {
    [source]: {
      type: 'vector',
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      tiles: ['https://tiles.versatiles.org/tiles/osm/{z}/{x}/{y}'],
      scheme: 'xyz',
      bounds: [-180, -85.0511287798066, 180, 85.0511287798066],
      minzoom: 0,
      maxzoom: 14
    }
  },
  layers: [
    { id: 'background', type: 'background', paint: { 'background-color': '#f7f5ef' } },
    vectorLayer('ocean', 'fill', 'ocean', {
      paint: { 'fill-color': '#d9e9ef' }
    }),
    vectorLayer('land-use', 'fill', 'land', {
      paint: {
        'fill-color': ['match', ['get', 'kind'],
          ['forest', 'wood', 'scrub'], '#dce9d7',
          ['park', 'garden', 'grass', 'grassland', 'meadow', 'recreation_ground', 'village_green', 'golf_course'], '#e5efdf',
          ['farmland', 'farmyard', 'orchard', 'vineyard', 'plant_nursery', 'greenhouse_horticulture'], '#f2efe1',
          ['cemetery', 'grave_yard'], '#e3ebe0',
          ['commercial', 'retail'], '#f2ece8',
          ['industrial', 'railway', 'landfill', 'quarry'], '#eceae6',
          ['residential'], '#f1eee8',
          ['beach', 'sand'], '#f2ead5',
          '#f3f1eb'],
        'fill-opacity': 0.74
      }
    }),
    vectorLayer('water', 'fill', 'water_polygons', {
      paint: { 'fill-color': '#d9e9ef' }
    }),
    vectorLayer('civic-sites', 'fill', 'sites', {
      minzoom: 12,
      filter: kinds(['university', 'college', 'school', 'hospital']),
      paint: {
        'fill-color': ['match', ['get', 'kind'], ['hospital'], '#eee5e4', '#e9e9df'],
        'fill-opacity': 0.72,
        'fill-outline-color': '#dedbd3'
      }
    }),
    vectorLayer('parking-sites', 'fill', 'sites', {
      minzoom: 16,
      filter: kinds(['parking', 'bicycle_parking']),
      paint: { 'fill-color': '#eceff0', 'fill-opacity': 0.6 }
    }),
    vectorLayer('piers', 'fill', 'pier_polygons', {
      minzoom: 13,
      paint: { 'fill-color': '#e8e4dc' }
    }),
    vectorLayer('pedestrian-areas', 'fill', 'street_polygons', {
      minzoom: 15,
      paint: { 'fill-color': '#eeeae1', 'fill-opacity': 0.8 }
    }),
    vectorLayer('buildings', 'fill', 'buildings', {
      minzoom: 15,
      paint: { 'fill-color': '#e8e4dc', 'fill-outline-color': '#dcd7cd', 'fill-opacity': 0.88 }
    }),
    vectorLayer('waterways', 'line', 'water_lines', {
      filter: kinds(['river', 'canal']),
      paint: { 'line-color': '#b8d8e3', 'line-width': zoomWidth([8, 0.7], [15, 2.2]) }
    }),
    vectorLayer('minor-waterways', 'line', 'water_lines', {
      minzoom: 15,
      filter: kinds(['stream', 'ditch']),
      paint: { 'line-color': '#c5dee7', 'line-width': zoomWidth([15, 0.7], [19, 1.5]) }
    }),
    vectorLayer('administrative-boundaries', 'line', 'boundaries', {
      filter: ['all', ['in', ['get', 'admin_level'], ['literal', [2, 4]]], ['!=', ['get', 'maritime'], true], ['!=', ['get', 'disputed'], true]],
      paint: {
        'line-color': '#9aa5ad',
        'line-opacity': ['match', ['get', 'admin_level'], 2, 0.55, 0.32],
        'line-width': ['match', ['get', 'admin_level'], 2, 1.1, 0.7],
        'line-dasharray': [3, 2]
      }
    }),
    vectorLayer('ferries', 'line', 'ferries', {
      minzoom: 9,
      paint: { 'line-color': '#94bac8', 'line-opacity': 0.7, 'line-width': 1, 'line-dasharray': [3, 3] }
    }),
    vectorLayer('rail', 'line', 'streets', {
      minzoom: 9,
      filter: kinds(['rail', 'light_rail']),
      paint: { 'line-color': '#aaa8a2', 'line-opacity': 0.72, 'line-width': zoomWidth([9, 0.7], [17, 1.5]), 'line-dasharray': [3, 2] }
    }),
    vectorLayer('major-roads-casing', 'line', 'streets', {
      filter: kinds(['motorway', 'trunk', 'primary']),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#d8d2c7', 'line-width': zoomWidth([7, 1.8], [12, 3.6], [17, 10.5], [19, 18]) }
    }),
    vectorLayer('major-roads', 'line', 'streets', {
      filter: kinds(['motorway', 'trunk', 'primary']),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['match', ['get', 'kind'], ['motorway', 'trunk'], '#f6ebd5', '#fffaf0'],
        'line-width': zoomWidth([7, 1.1], [12, 2.7], [17, 8.2], [19, 14.8])
      }
    }),
    vectorLayer('secondary-roads', 'line', 'streets', {
      minzoom: 10,
      filter: kinds(['secondary', 'tertiary']),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#fbfaf7', 'line-width': zoomWidth([10, 0.8], [15, 3.1], [19, 9.5]) }
    }),
    vectorLayer('local-roads', 'line', 'streets', {
      minzoom: 13,
      filter: kinds(['residential', 'unclassified', 'living_street', 'service', 'pedestrian']),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#fdfcf9', 'line-width': zoomWidth([13, 0.65], [16, 2.1], [19, 7]) }
    }),
    vectorLayer('paths', 'line', 'streets', {
      minzoom: 16,
      filter: kinds(['track', 'path', 'footway', 'steps', 'busway', 'bus_guideway']),
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#d2cec5', 'line-opacity': 0.75, 'line-width': zoomWidth([16, 0.6], [19, 1.5]), 'line-dasharray': [2, 1.5] }
    }),
    vectorLayer('major-road-labels', 'symbol', 'street_labels', {
      minzoom: 11,
      filter: kinds(['motorway', 'trunk', 'primary', 'secondary', 'tertiary']),
      layout: {
        'symbol-placement': 'line', 'symbol-spacing': 450, 'text-field': name,
        'text-font': ['noto_sans_regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 11, 10, 17, 12.5]
      },
      paint: { 'text-color': '#59636a', 'text-halo-color': '#f7f5ef', 'text-halo-width': 1.2 }
    }),
    vectorLayer('local-road-labels', 'symbol', 'street_labels', {
      minzoom: 16,
      filter: kinds(['residential', 'unclassified', 'living_street', 'pedestrian']),
      layout: {
        'symbol-placement': 'line', 'symbol-spacing': 350, 'text-field': name,
        'text-font': ['noto_sans_regular'], 'text-size': 11
      },
      paint: { 'text-color': '#68747b', 'text-halo-color': '#f7f5ef', 'text-halo-width': 1.1 }
    }),
    vectorLayer('place-labels', 'symbol', 'place_labels', {
      minzoom: 5,
      filter: kinds(['capital', 'state_capital', 'city', 'town', 'village']),
      layout: {
        'text-field': name, 'text-font': ['noto_sans_bold'],
        'text-size': ['interpolate', ['linear'], ['zoom'], 5, 12, 12, 16, 17, 18],
        'text-variable-anchor': ['top', 'bottom', 'left', 'right'], 'text-radial-offset': 0.4
      },
      paint: { 'text-color': '#46515a', 'text-halo-color': '#f7f5ef', 'text-halo-width': 1.4 }
    }),
    vectorLayer('district-labels', 'symbol', 'place_labels', {
      minzoom: 12,
      filter: kinds(['suburb', 'quarter']),
      layout: { 'text-field': name, 'text-font': ['noto_sans_regular'], 'text-size': 12, 'text-letter-spacing': 0.08 },
      paint: { 'text-color': '#778087', 'text-halo-color': '#f7f5ef', 'text-halo-width': 1.2, 'text-opacity': 0.75 }
    }),
    vectorLayer('important-site-labels', 'symbol', 'sites', {
      minzoom: 15,
      filter: kinds(['university', 'college', 'hospital']),
      layout: {
        'text-field': name, 'text-font': ['noto_sans_regular'], 'text-size': 10.5,
        'text-variable-anchor': ['top', 'bottom'], 'text-radial-offset': 0.45
      },
      paint: { 'text-color': '#66727a', 'text-halo-color': '#f7f5ef', 'text-halo-width': 1.1 }
    })
  ]
}

const output = fileURLToPath(new URL('../public/map-styles/stadtplanner-light.json', import.meta.url))
await mkdir(fileURLToPath(new URL('../public/map-styles/', import.meta.url)), { recursive: true })
await writeFile(output, `${JSON.stringify(style, null, 2)}\n`)
console.log(`Generated ${style.name}: ${style.layers.length} layers -> ${output}`)
