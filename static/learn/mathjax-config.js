/* The site's own MathJax set-up (tools/exams/appsc_paper.py), so maths reads the same here.
   A file rather than an inline script, so the Content Security Policy allows only 'self'. */
window.MathJax = {
  tex: { inlineMath: [['$', '$']], displayMath: [['$$', '$$']], processEscapes: true },
  options: { skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }
};
