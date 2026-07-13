// eBike Routes — public site.
// Plain ES6+, no framework/bundler. Leaflet + Leaflet.markercluster are vendored in lib/.
// Data contract (frozen, see CLAUDE.md): routes.json -> { generated, routes: [
//   { slug, file, name, date, distance_km, elevation_m, pin: [lat,lng], bbox } ] }

(function () {
  'use strict';

  // ---- Config / API key resolution (CLAUDE.md "Secrets") ----------------
  // Dev override (config.local.js, gitignored) wins over the committed prod
  // key in config.js. Never hard-code a key here.
  var PLACEHOLDER_KEYS = ['PROD_KEY_PENDING_DEPLOY', 'YOUR_MAPY_DEV_KEY_HERE'];

  function resolveMapyKey() {
    var local = window.APP_CONFIG_LOCAL && window.APP_CONFIG_LOCAL.mapyKey;
    var prod = window.APP_CONFIG && window.APP_CONFIG.mapyKey;
    return local || prod || '';
  }

  function isUsableKey(key) {
    return !!key && PLACEHOLDER_KEYS.indexOf(key) === -1;
  }

  // ---- Constants ----------------------------------------------------------
  var CZECHIA_CENTER = [49.8, 15.5];
  var CZECHIA_ZOOM = 7;

  // Desktop only: touch devices have no hover, so pin tooltips + hover visuals
  // are gated on this (same desktop/touch split as the header stat labels).
  var canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  // Brand map pin. A divIcon (real DOM) rather than the stock <img> marker so
  // the hover scale is pure CSS and the selected state is a class swap — a
  // stock icon can't be scaled without fighting Leaflet's inline positioning
  // transform. The outer div carries that transform; the inner .route-pin__dot
  // is what CSS scales, so there's no conflict.
  function routePinIcon(selected) {
    return L.divIcon({
      className: 'route-pin' + (selected ? ' is-selected' : ''),
      html: '<span class="route-pin__dot"></span>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });
  }

  // ---- Map init -------------------------------------------------------------
  // maxZoom/minZoom are set here (not just on the tile layer) because
  // fitBounds()/setView() need a zoom bound from *somewhere* — without a
  // tile layer (keyless case, banner shown) Leaflet has no layer to infer
  // one from and throws "Map has no maxZoom specified".
  var map = L.map('map', { zoomControl: true, minZoom: 0, maxZoom: 19 }).setView(CZECHIA_CENTER, CZECHIA_ZOOM);

  // Mapy copyright text is mandatory attribution (CLAUDE.md "Mapy
  // attribution") independent of whether a tile layer actually gets added —
  // the placeholder-key case (no tiles, banner shown) must still show it,
  // not just the bare Leaflet credit. Added directly on the attribution
  // control so it's unconditional; the tile layer below also declares it
  // via its own `attribution` option, which is a harmless no-op duplicate
  // (Leaflet's AttributionControl dedupes by text).
  map.attributionControl.addAttribution('<a href="https://api.mapy.com/copyright" target="_blank">&copy; Seznam.cz a.s. a další</a>');

  var mapyKey = resolveMapyKey();
  if (isUsableKey(mapyKey)) {
    L.tileLayer('https://api.mapy.com/v1/maptiles/outdoor/256/{z}/{x}/{y}?apikey=' + encodeURIComponent(mapyKey), {
      minZoom: 0,
      maxZoom: 19,
      attribution: '<a href="https://api.mapy.com/copyright" target="_blank">&copy; Seznam.cz a.s. a další</a>',
    }).addTo(map);
  } else {
    showKeyBanner();
  }

  // Mapy logo control — mandatory attribution alongside the copyright text
  // above. Added unconditionally (even keyless) per CLAUDE.md.
  var MapyLogoControl = L.Control.extend({
    options: { position: 'bottomleft' },
    onAdd: function () {
      var container = L.DomUtil.create('div', 'mapy-logo-control');
      var link = L.DomUtil.create('a', '', container);
      link.href = 'https://mapy.com/';
      link.target = '_blank';
      link.rel = 'noopener';
      var img = L.DomUtil.create('img', '', link);
      img.src = 'lib/mapy/logo.svg';
      img.alt = 'Mapy.com';
      L.DomEvent.disableClickPropagation(container);
      return container;
    },
  });
  map.addControl(new MapyLogoControl());

  function showKeyBanner() {
    var banner = document.getElementById('key-banner');
    banner.hidden = false;
  }
  document.getElementById('key-banner-close').addEventListener('click', function () {
    document.getElementById('key-banner').hidden = true;
  });

  // ---- GPX parsing (whitelist emitter -> ~30-line reader, no plugin) -------
  // Our pipeline only ever emits <trk><trkseg><trkpt lat lon><ele>. Use
  // getElementsByTagNameNS with a wildcard namespace so the GPX default
  // namespace (present or absent) never breaks the lookup.
  function parseGpxLatLngs(xmlText) {
    var doc = new DOMParser().parseFromString(xmlText, 'application/xml');
    if (doc.getElementsByTagName('parsererror').length) {
      throw new Error('GPX parse error');
    }
    var trkpts = doc.getElementsByTagNameNS('*', 'trkpt');
    var latlngs = [];
    for (var i = 0; i < trkpts.length; i++) {
      var el = trkpts[i];
      var lat = parseFloat(el.getAttribute('lat'));
      var lon = parseFloat(el.getAttribute('lon'));
      if (!isNaN(lat) && !isNaN(lon)) {
        latlngs.push([lat, lon]);
      }
    }
    return latlngs;
  }

  // ---- State ----------------------------------------------------------------
  var routesBySlug = Object.create(null);
  var markersBySlug = Object.create(null);
  var selectedMarker = null; // the pin currently drawn in the selected (red) state
  // disableClusteringAtZoom 13 (= maxZoom 19 − 6): rides that start near each
  // other (same trailhead, privacy-jittered pins a few hundred metres apart)
  // must separate well before max zoom — with the default behaviour they only
  // split around z16. Below z13 the default 80px radius keeps the
  // country-level view tidy. spiderfyOnMaxZoom is moot once clusters can't
  // exist at max zoom, so it's off per the markercluster docs.
  var clusterGroup = L.markerClusterGroup({
    chunkedLoading: true,
    disableClusteringAtZoom: 13,
    spiderfyOnMaxZoom: false,
  });
  var currentPolyline = null;
  var currentSlug = null;
  var selectionToken = 0; // guards against out-of-order async responses on rapid clicks

  // Highlight one pin (red, against the orange rest pins) and revert the previous.
  // setIcon (not a DOM class toggle) so the state survives markercluster
  // rebuilding icons on zoom, and applies whenever the marker is next rendered.
  function setSelectedMarker(slug) {
    if (selectedMarker) {
      selectedMarker.setIcon(routePinIcon(false));
      selectedMarker = null;
    }
    var marker = slug && markersBySlug[slug];
    if (marker) {
      marker.setIcon(routePinIcon(true));
      selectedMarker = marker;
    }
  }

  map.addLayer(clusterGroup);

  // ---- Status note (routes.json missing/empty/unreachable, GPX errors) ------
  function showNote(text) {
    var note = document.getElementById('status-note');
    note.textContent = text;
    note.hidden = false;
  }
  function hideNote() {
    document.getElementById('status-note').hidden = true;
  }

  // ---- Fit-all-pins default view ---------------------------------------------
  function fitAll() {
    var slugs = Object.keys(routesBySlug);
    if (slugs.length === 0) {
      map.setView(CZECHIA_CENTER, CZECHIA_ZOOM);
      showNote('No routes yet.');
      return;
    }
    hideNote();
    map.fitBounds(clusterGroup.getBounds().pad(0.1));
  }

  // ---- Selected-route sidebar -----------------------------------------------
  // The selected route's name, distance, elevation, and GPX download live in a
  // right-side panel (bottom sheet on mobile). The date is never shown on the
  // page — it lives only in the #slug permalink. Opening/closing the sidebar
  // resizes the map (see showSidebar/hideSidebar callers), so pins are never
  // hidden behind it.
  function showSidebar(route) {
    document.getElementById('sidebar-name').textContent = route.name;
    // Values set via textContent (never innerHTML) so route data can't inject
    // markup; the labels are static in the HTML.
    document.getElementById('sidebar-distance').textContent = route.distance_km + ' km';
    document.getElementById('sidebar-elevation').textContent = route.elevation_m + ' m';
    // Point the GPX download at the route's static file. Same-origin +
    // download attribute -> the browser saves rather than navigates. Encode
    // the path (spaces/diacritics) but keep the pretty original filename as
    // the download name.
    var dl = document.getElementById('download-gpx');
    dl.href = 'gpx/' + encodeURIComponent(route.file);
    dl.setAttribute('download', route.file);
    document.getElementById('route-sidebar').hidden = false;
    // The map's flex box just narrowed (desktop) / shortened (mobile); Leaflet
    // must re-measure before any fitBounds so the fit uses the new viewport.
    map.invalidateSize();
    document.title = route.name;
  }

  function hideSidebar() {
    document.getElementById('route-sidebar').hidden = true;
    // Map reclaimed the sidebar's space — re-measure so the follow-up fitAll()
    // uses the full width.
    map.invalidateSize();
    document.title = 'Cyklocesta';
  }

  // Close button collapses the detail panel but leaves the route drawn, its pin
  // selected, and the current zoom untouched — so closing the detail keeps you
  // zoomed in on the highlighted route instead of snapping back to the overview.
  // The #slug permalink stays too, so a refresh restores this state; browser
  // Back and the logo still return to the overview (deselectRoute). Re-clicking
  // the same pin reopens the panel (see selectRouteBySlug's same-slug branch).
  document.getElementById('sidebar-close').addEventListener('click', function () {
    document.getElementById('route-sidebar').hidden = true;
    // Map reclaimed the sidebar's space — re-measure so it fills the viewport
    // while keeping the same center/zoom (the route stays highlighted in place).
    map.invalidateSize();
  });

  // ---- Selecting / deselecting a route (one polyline at a time) -------------
  function clearPolyline() {
    if (currentPolyline) {
      map.removeLayer(currentPolyline);
      currentPolyline = null;
    }
  }

  // There is no deselect *control* — the only way to change state is to click a
  // different pin. This runs solely on the empty-hash path (browser Back lands
  // on the bare URL): restore the "Cyklocesta" overview so the map isn't stranded
  // showing a route the URL no longer references.
  function deselectRoute() {
    currentSlug = null;
    selectionToken++; // invalidate any in-flight fetch from the old selection
    clearPolyline();
    setSelectedMarker(null);
    hideSidebar();
    fitAll();
  }

  // Recenter + rezoom so the whole route fits the viewport at ANY starting
  // zoom: fitBounds zooms IN when the current view is too far out and OUT when
  // it's too close. The padding keeps a few neighbouring pins in view.
  function fitRoute(polyline) {
    map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
  }

  function selectRouteBySlug(slug) {
    var route = routesBySlug[slug];
    if (!route) {
      // Unknown/stale hash: no error, just leave the current view as-is.
      return;
    }
    if (slug === currentSlug) {
      // Same route re-clicked (its pin is still on the map): don't re-fetch.
      // If the detail panel was closed (route left highlighted), reopen it;
      // then recenter/rezoom to the route. This is also why an already-selected
      // pin used to look like "nothing happens" on click.
      if (document.getElementById('route-sidebar').hidden) showSidebar(route);
      if (currentPolyline) fitRoute(currentPolyline);
      return;
    }
    currentSlug = slug;
    hideNote();
    var token = ++selectionToken; // rapid clicks: only the latest response applies

    fetch('gpx/' + encodeURIComponent(route.file))
      .then(function (resp) {
        if (!resp.ok) throw new Error('GPX fetch failed: ' + resp.status);
        return resp.text();
      })
      .then(function (xmlText) {
        if (token !== selectionToken) return; // superseded by a newer selection
        var latlngs = parseGpxLatLngs(xmlText);
        clearPolyline();
        var polyline = L.polyline(latlngs, { color: '#e6550d', weight: 4 });
        // Clicking the drawn route line re-fits to it too (not just the pin),
        // so "zoom to fit" works whether the user clicks the pin or the route.
        // If the detail panel was closed (route left highlighted), reopen it —
        // same behaviour as re-clicking the pin.
        polyline.on('click', function () {
          if (document.getElementById('route-sidebar').hidden) showSidebar(route);
          fitRoute(polyline);
        });
        polyline.addTo(map);
        currentPolyline = polyline;
        // Open the sidebar first: it resizes the map (invalidateSize), so the
        // subsequent fitRoute() fits the route into the narrowed viewport.
        showSidebar(route);
        fitRoute(polyline);
        setSelectedMarker(slug);
      })
      .catch(function (err) {
        if (token !== selectionToken) return; // superseded; ignore stale error
        console.error(err);
        showNote('Could not load this route.');
        currentSlug = null;
        clearPolyline();
      });
  }

  function goToSlug(slug) {
    if (decodeURIComponent(location.hash.slice(1)) === slug) {
      // Same hash won't fire 'hashchange' — select directly.
      selectRouteBySlug(slug);
    } else {
      location.hash = slug;
    }
  }

  // Logo returns to the map overview: drop any #slug permalink (without a
  // reload) and deselect. pushState doesn't fire 'hashchange', so deselect
  // directly; if already at the overview this just re-fits all pins.
  document.getElementById('home-link').addEventListener('click', function (e) {
    e.preventDefault();
    if (location.hash) {
      history.pushState('', document.title, location.pathname + location.search);
    }
    deselectRoute();
  });

  window.addEventListener('hashchange', function () {
    var slug = decodeURIComponent(location.hash.slice(1));
    if (slug) {
      selectRouteBySlug(slug);
    } else {
      deselectRoute();
    }
  });

  // ---- Load routes.json and build markers ------------------------------------
  fetch('routes.json')
    .then(function (resp) {
      if (!resp.ok) throw new Error('routes.json fetch failed: ' + resp.status);
      return resp.json();
    })
    .then(function (data) {
      var routes = (data && data.routes) || [];
      routes.forEach(function (route) {
        routesBySlug[route.slug] = route;
        var marker = L.marker(route.pin, { icon: routePinIcon(false) });
        // Desktop hover tooltip: distance · elevation, straight from routes.json
        // (no GPX fetch). Gated on canHover so touch taps still just select.
        if (canHover) {
          marker.bindTooltip(route.distance_km + ' km · ' + route.elevation_m + ' m ↑', {
            direction: 'top',
            offset: [0, -12],
            className: 'pin-tooltip',
          });
        }
        marker.on('click', function () {
          goToSlug(route.slug);
        });
        markersBySlug[route.slug] = marker;
        clusterGroup.addLayer(marker);
      });
      // Deep-link: if the URL already has a matching #slug, select it —
      // and skip fitAll() entirely in that case. Both call map.fitBounds();
      // fitAll()'s is synchronous while selectRouteBySlug()'s only runs
      // later inside the async GPX-fetch .then(), and firing both races
      // Leaflet's view-change animation, with the fit-all view sometimes
      // winning even though it ran first (confirmed cold-load bug: the
      // route-specific zoom never took effect). Calling exactly one of the
      // two avoids the race outright.
      var initialSlug = decodeURIComponent(location.hash.slice(1));
      if (initialSlug && routesBySlug[initialSlug]) {
        selectRouteBySlug(initialSlug);
      } else {
        fitAll();
      }
    })
    .catch(function (err) {
      console.error(err);
      showNote('Could not load routes.');
    });
})();
