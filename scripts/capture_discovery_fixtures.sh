#!/usr/bin/env bash
# Captures live responses from confirmed CON29 data sources.
# See docs/CON29_BUILD_HANDOFF.md section 3. Run from the repo root.
set -u

OUT=tests/fixtures/discovery
mkdir -p "$OUT"
: > "$OUT/MANIFEST.tsv"

B=https://maps2.bristol.gov.uk/server2/rest/services/ext
G="geometry=-2.604062,51.452073&geometryType=esriGeometryPoint&inSR=4326"
F="outFields=*&returnGeometry=false&f=json"
PIP="$G&spatialRel=esriSpatialRelIntersects&$F"
BUF="$G&distance=50&units=esriSRUnit_Meter&spatialRel=esriSpatialRelIntersects&$F"

grab () {
  curl -s "$1" -o "$OUT/$2"
  printf '%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$2" "$1" >> "$OUT/MANIFEST.tsv"
  printf '  %s\n' "$2"
}

echo "Service metadata"
grab "$B?f=json"                                       bristol_catalogue_ext.json
grab "$B/ODP_Datasets/MapServer?f=json"                bristol_meta_odp.json
grab "$B/ll_environment_and_planning/MapServer?f=json" bristol_meta_ll_env_planning.json
grab "$B/ll_transport/MapServer?f=json"                bristol_meta_ll_transport.json
grab "$B/Map/MapServer/0?f=json"                       bristol_meta_adopted_highway_layer0.json
grab "$B/pollution/MapServer?f=json"                   bristol_meta_pollution_NOT_3_13.json

echo "Confirmed sources, point-in-polygon"
grab "$B/ll_environment_and_planning/MapServer/2/query?$PIP" bristol_planning_applications_pip.json
grab "$B/ODP_Datasets/MapServer/5/query?$PIP"                bristol_conservation_area_pip.json
grab "$B/ODP_Datasets/MapServer/4/query?$PIP"                bristol_conservation_area_docs_pip.json
grab "$B/Map/MapServer/0/query?$PIP"                         bristol_adopted_highway_pip.json

echo "DEF-05 regression pair, buffer is WRONG for these"
grab "$B/ll_environment_and_planning/MapServer/2/query?$BUF" bristol_planning_applications_buffer50_WRONG.json
grab "$B/ODP_Datasets/MapServer/4/query?$BUF"                bristol_conservation_area_docs_buffer50_WRONG.json

echo "Rights of way, buffer is CORRECT here"
grab "$B/ll_transport/MapServer/0/query?$PIP"  bristol_rights_of_way_pip.json
grab "$B/ll_transport/MapServer/0/query?$BUF"  bristol_rights_of_way_buffer50.json
grab "$B/ll_transport/MapServer/55/query?$BUF" bristol_lsg_designations_buffer50.json

echo "Captured but not yet analysed, WP-04 targets"
for L in 0 1 2 3 6 7; do
  grab "$B/ODP_Datasets/MapServer/$L/query?$PIP" "bristol_UNANALYSED_odp_layer$L.json"
done
grab "$B/ll_environment_and_planning/MapServer/9/query?$PIP" bristol_UNANALYSED_article4.json

echo "National"
grab "https://www.planning.data.gov.uk/entity/1735567.json" \
     national_brownfield_entity_1735567.json
grab "https://www.planning.data.gov.uk/entity.json?dataset=planning-application&organisation_entity=66&limit=5" \
     national_planning_application_bristol_EMPTY.json
grab "https://www.planning.data.gov.uk/entity.json?dataset=planning-application&organisation_entity=163&limit=5" \
     national_planning_application_hackney_EMPTY.json

echo "Access governance evidence, see handoff section 4"
curl -s  https://pa.bristol.gov.uk/robots.txt                        > "$OUT/governance_robots_pa_bristol.txt"
curl -s  https://developmentandhousing.hackney.gov.uk/robots.txt     > "$OUT/governance_robots_devhousing_hackney.txt"
curl -s  https://www.bristol.gov.uk/robots.txt                       > "$OUT/governance_robots_www_bristol.txt"
curl -s  https://www.hackney.gov.uk/robots.txt                       > "$OUT/governance_robots_www_hackney.txt"
curl -sI https://developmentandhousing.hackney.gov.uk/planning/index.html \
                                                                     > "$OUT/governance_hackney_waf_challenge_headers.txt"

echo
echo "Done. $(wc -l < "$OUT/MANIFEST.tsv") captures logged to $OUT/MANIFEST.tsv"
