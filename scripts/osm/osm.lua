-- Stadtplaner osm2pgsql Flex output.
--
-- The table in osm_import is deliberately an internal staging contract. The
-- application continues to read public.osm_features, which is populated by
-- backend/app/cli/postprocess_osm.py after a complete import/update chunk.

local output_schema = os.getenv('OSM_OUTPUT_SCHEMA') or 'osm_import'

-- This coarse pre-filter prevents the official planet stream from creating
-- output rows for the rest of the world. The exact DE-SH boundary check is
-- performed transactionally in PostGIS during post-processing.
local west = tonumber(os.getenv('OSM_BBOX_WEST') or '7.5')
local south = tonumber(os.getenv('OSM_BBOX_SOUTH') or '53.3')
local east = tonumber(os.getenv('OSM_BBOX_EAST') or '11.6')
local north = tonumber(os.getenv('OSM_BBOX_NORTH') or '55.2')

local features = osm2pgsql.define_table({
    name = 'osm_features_stage',
    schema = output_schema,
    ids = {
        type = 'any',
        id_column = 'osm_id',
        type_column = 'osm_type',
        create_index = 'primary_key',
    },
    columns = {
        { column = 'tags', type = 'jsonb', not_null = true },
        { column = 'geometry', type = 'geometry', projection = 4326, not_null = true },
    },
})

local function bbox_overlaps_region(object)
    local min_lon, min_lat, max_lon, max_lat = object:get_bbox()
    if min_lon == nil then
        return false
    end
    return max_lon >= west and min_lon <= east and max_lat >= south and min_lat <= north
end

local function is_relevant(tags)
    return tags.shop ~= nil
        or tags.amenity ~= nil
        or tags.office ~= nil
        or tags.craft ~= nil
        or tags.tourism ~= nil
        or tags.leisure ~= nil
        or tags.historic ~= nil
        or tags.building ~= nil
        or tags.landuse ~= nil
        or tags.natural ~= nil
        or tags.public_transport ~= nil
        or tags.railway ~= nil
        or tags.healthcare ~= nil
        or tags.sport ~= nil
        or tags.club ~= nil
        or tags.parking ~= nil
        or tags.place ~= nil
        or tags.boundary == 'administrative'
        or tags.highway == 'bus_stop'
        or tags['disused:shop'] ~= nil
        or tags['abandoned:shop'] ~= nil
end

function osm2pgsql.process_node(object)
    if not is_relevant(object.tags) or not bbox_overlaps_region(object) then
        return
    end
    features:insert({ tags = object.tags, geometry = object:as_point() })
end

function osm2pgsql.process_way(object)
    if not object.is_closed or not is_relevant(object.tags) or not bbox_overlaps_region(object) then
        return
    end
    features:insert({ tags = object.tags, geometry = object:as_polygon() })
end

function osm2pgsql.process_relation(object)
    if (object.tags.type ~= 'multipolygon' and object.tags.type ~= 'boundary')
        or not is_relevant(object.tags)
        or not bbox_overlaps_region(object) then
        return
    end
    features:insert({ tags = object.tags, geometry = object:as_multipolygon() })
end
