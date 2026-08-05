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
      <a class="wordmark" href="committee.html">${BRAND.name}</a>
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
