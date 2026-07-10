// COMMITTED on purpose. Holds ONLY the production Mapy.com key, which is
// HTTP-referrer-locked to the live domain and therefore safe in a public
// repo (a scraped copy won't work from another origin). NEVER put the dev
// key here — that goes in gitignored config.local.js (see config.example.js).
// Placeholder until the prod key is created at deploy time (open-questions #2,
// #18/#19: the referrer restriction needs the final domain first).
window.APP_CONFIG = {
  mapyKey: '_Sdm1JC4dy4x52_N3OHO_4j-4O7c5A9ACBDQfp0zDMI',
};
