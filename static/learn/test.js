/* NRSTATLAB Learn: the unit test page. Each answer is sent to the server as it is
   chosen, so a dropped connection or a closed tab loses nothing. The form also
   posts every answer when it is submitted, so the page works without this. */
(function () {
  'use strict';
  var form = document.getElementById('test-form');
  if (!form) return;
  var url = form.getAttribute('data-answer-url');
  var csrf = form.querySelector('input[name=csrfmiddlewaretoken]').value;

  function answerOf(fs) {
    var type = fs.getAttribute('data-qtype');
    var n = fs.getAttribute('data-n');
    if (type === 'multiple') {
      return Array.prototype.map.call(fs.querySelectorAll('input:checked'), function (i) { return i.value; });
    }
    if (type === 'match') {
      var pairs = {};
      Array.prototype.forEach.call(fs.querySelectorAll('select'), function (s) {
        pairs[s.name.slice(('q' + n + '-').length)] = s.value;
      });
      return pairs;
    }
    if (type === 'numeric') return fs.querySelector('input').value;
    var c = fs.querySelector('input:checked');
    return c ? c.value : '';
  }
  function answered(fs) {
    var a = answerOf(fs);
    if (Array.isArray(a)) return a.length > 0;
    if (a && typeof a === 'object') return Object.keys(a).some(function (k) { return a[k]; });
    return !!a;
  }
  function save(fs) {
    var status = fs.querySelector('.tq-status');
    status.textContent = 'Saving…';
    fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ question: Number(fs.getAttribute('data-n')), answer: answerOf(fs) })
    }).then(function (r) {
      if (r.ok) { status.textContent = 'Saved'; return; }
      return r.json().then(function (j) { status.textContent = j.error || 'Not saved.'; });
    }, function () {
      status.textContent = 'Not saved yet (no connection); it will still be sent when you submit.';
    });
  }
  form.addEventListener('change', function (e) {
    var fs = e.target.closest('fieldset.tq');
    if (fs) save(fs);
  });
  form.addEventListener('submit', function (e) {
    var left = Array.prototype.filter.call(form.querySelectorAll('fieldset.tq'), function (fs) { return !answered(fs); });
    if (left.length && !window.confirm(left.length + ' question' + (left.length === 1 ? ' is' : 's are') +
                                       ' not answered. Submit anyway?')) {
      e.preventDefault();
    }
  });
})();
