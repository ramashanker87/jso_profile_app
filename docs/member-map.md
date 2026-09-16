# Members map

Open Members and select **Map** beside the heading. Darker country shading
represents more active members, using bins 0, 1, 2–5, 6–15, 16–30 and 31+.
Click a populated country or its country-list button to filter the member cards
below. The List/Map selection is stored in the URL as `view=map`.

Counts cover all active members matching the current text search, before the
country filter and pagination. A member listed in two countries counts once in
each; the total-members summary still counts that member once. Personal edits
are included. Country names and recognized aliases take priority; an explicit
country name at the end of an address supplies a fallback. Addresses are not
sent to an external geocoder and street-level locations are not inferred.
Unrecognized locations remain listed as not mapped and can still be filtered.

Country outlines use the public-domain Natural Earth 5.1.2 1:50m country dataset:
https://github.com/nvkelso/natural-earth-vector/blob/v5.1.2/geojson/ne_50m_admin_0_countries.geojson
Terms: https://www.naturalearthdata.com/about/
Boundaries reflect Natural Earth's default depiction and are illustrative.

The generated map and country-name lookup are bundled with the frontend and
backend. There is no paid map API, map key, or new external browser dependency.
To regenerate, download the pinned GeoJSON and run
`python3 scripts/build-country-map.py /path/to/ne_50m_admin_0_countries.geojson`.
The map module loads only when Map is selected. Small countries also have
markers and country-list controls. Populated outlines support Enter/Space.
