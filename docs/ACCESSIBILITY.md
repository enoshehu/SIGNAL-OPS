# Accessibility verification

The dashboard uses semantic landmarks, a keyboard skip link, labelled buttons and form controls,
an accessible table caption, visible focus indicators, live status text and a reduced-motion mode.
The layout has dedicated desktop, tablet and mobile breakpoints.

## Release checks

- [x] Keyboard access to theme, city controls, route buttons and links.
- [x] Visible `:focus-visible` indicator.
- [x] Programmatic labels for interactive controls.
- [x] Status and coverage changes exposed as live text.
- [x] Data chart values repeated as text and table values.
- [x] `prefers-reduced-motion` disables decorative animation and smooth scrolling.
- [x] Content reflows to one column below 760 px without requiring a desktop viewport.
- [x] Day-theme primary text/background contrast exceeds WCAG AA.
- [x] Night-theme primary text/background contrast exceeds WCAG AA.

Automated source checks run in `tests/test_site_accessibility.py`. Before a tagged release, also
perform a browser keyboard pass at 375 px and 1440 px and inspect with the browser accessibility
tree; automated checks do not replace assistive-technology review.
