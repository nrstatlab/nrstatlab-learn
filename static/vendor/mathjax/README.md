# MathJax 3.2.2, served by the application

The site's pages load MathJax 3 from `https://cdn.jsdelivr.net/npm/mathjax@3/es5/`. The application
serves this copy instead (`apps/study/services.py`, `rewrite_for_origin`), so the formulas draw with
no internet connection and the Content Security Policy needs no outside host.

- Version: 3.2.2, from the `mathjax` npm package (the version `mathjax@3` resolves to).
- Licence: Apache License 2.0 (`LICENSE`).
- Kept: the two combined components the pages use (`tex-mml-chtml.js`, `tex-chtml.js`), and what they
  load on demand: `input/` (TeX extensions such as `noerrors` and `tagformat`), `output/chtml/`
  (the fonts), `ui/` (the menu), `a11y/` and `sre/` (the accessibility tools the menu can switch on).
- To update: replace these files from a newer 3.x `mathjax` package, keeping the same layout.
