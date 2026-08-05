// The one place the product's identity is defined.
//
// The platform is not "oregontennis.org". It runs there, and the public rankings
// site keeps that name, but the scoring-input and evaluation system is its own
// product — so it can be pointed at another state, or stand on its own domain,
// without a rename.
//
// The custom wordmark font is still to come. It drops into the @font-face block
// in css/brand.css and is picked up by --brand-font; this file and that block are
// the only two places the identity lives.

export const BRAND = {
  // The wordmark. Rendered in --brand-font wherever `.wordmark` is used.
  name: 'Cheesybook',

  // Sits beside the wordmark in the masthead. One line, sentence case.
  tagline: 'Oregon high school tennis',

  // Shown on printed artifacts, where a reader has no URL bar.
  host: 'oregontennis.org',

  // Suffix for <title>. Keep it short — it is the browser tab.
  titleSuffix: 'Cheesybook',
};

/** `document.title` for a page, e.g. "Selection Board — Cheesybook". */
export function pageTitle(page) {
  return page ? `${page} — ${BRAND.titleSuffix}` : BRAND.titleSuffix;
}

/**
 * The masthead used across the branded pages.
 *
 * `links` is an array of {href, label}. The wordmark leads; the rankings site is
 * always reachable, because this product sits inside it for now.
 */
export function masthead({ links = [], current = '' } = {}) {
  const nav = links.map((l) =>
    `<a class="mast-link${l.label === current ? ' current' : ''}" href="${l.href}">${l.label}</a>`
  ).join('');
  return `
    <div class="mast-inner">
      <a class="wordmark" href="cheesybook.html">${BRAND.name}</a>
      <span class="mast-tagline">${BRAND.tagline}</span>
      <nav class="mast-nav">${nav}</nav>
    </div>`;
}

/** Apply the brand to a page: title, masthead, and the document language. */
export function applyBrand(page, { links, current } = {}) {
  document.title = pageTitle(page);
  const mast = document.querySelector('.mast');
  if (mast) mast.innerHTML = masthead({ links, current });
}


/**
 * A league's display name, distinct across classifications.
 *
 * The named leagues carry their classification already — "6A-2 Metro",
 * "5A-4 Intermountain". The Special Districts do not: 6A, 5A and 4A/3A/2A/1A
 * each have a Special District 1, and they are three different leagues. Keyed
 * or labelled on the name alone they collide, so the classification goes in
 * front the way OSAA writes it: 4A/3A/2A/1A-SD1.
 */
export function leagueLabel(classification, league) {
  const name = String(league || '').trim();
  const cls = String(classification || '').trim();
  if (!name) return '';
  if (!cls || name.startsWith(cls)) return name;
  const sd = name.match(/^Special District\s+(\d+)$/i);
  return sd ? `${cls}-SD${sd[1]}` : `${cls} ${name}`;
}

/** A key that cannot collide across classifications. */
export function leagueKey(classification, league) {
  return `${String(classification || '').trim()}|${String(league || '').trim()}`;
}
