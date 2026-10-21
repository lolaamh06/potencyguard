# globe

- What lives here: `land-mask.png`, an equirectangular land mask (1024x512, grayscale, 255 = land, 0 = sea) used to place the dots of the night globe.
- Origin: Natural Earth 110m land (`ne_110m_land`), made by `scripts/make_land_mask.py`.
- Source page: https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-land/
- Downloaded from: https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson
- Date fetched: 2026-10-21
- Licence: public domain (Natural Earth terms of use: no permission needed, attribution appreciated).
- Only the mask is committed; the source download is not. The mask covers 33.2% of the pixels.
- The globe is a stylised picture, not a map: do not read borders or coastlines from it.
