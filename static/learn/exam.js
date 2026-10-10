/* StatsTricks360 Learn: an old paper in exam mode. Counts the answers given, marks them in
   the question grid, and, when the paper records its duration, shows the time left
   and submits the paper when it runs out. The deadline is the server's: the page only
   counts down to it, and the server refuses answers after it. */
(function () {
  'use strict';
  var form = document.getElementById('test-form');
  if (!form) return;
  var counter = document.getElementById('exam-answered');
  var clock = document.getElementById('exam-clock');

  function tally() {
    var n = 0;
    Array.prototype.forEach.call(form.querySelectorAll('fieldset.tq:not([data-withdrawn])'), function (fs) {
      var done = !!fs.querySelector('input:checked');
      if (done) n += 1;
      var link = document.querySelector('.exam-grid a[data-n="' + fs.getAttribute('data-n') + '"]');
      if (link) link.classList.toggle('is-answered', done);
    });
    if (counter) counter.textContent = n;
  }
  form.addEventListener('change', tally);
  tally();

  if (!clock) return;
  var end = Date.now() + Number(clock.getAttribute('data-seconds-left')) * 1000;
  function pad(x) { return (x < 10 ? '0' : '') + x; }
  function timeUp() {
    form.setAttribute('data-time-up', '1');
    clock.textContent = 'Time is up';
    if (typeof form.requestSubmit === 'function') form.requestSubmit(); else form.submit();
  }
  function tick() {
    var left = Math.max(0, Math.round((end - Date.now()) / 1000));
    var h = Math.floor(left / 3600), m = Math.floor(left % 3600 / 60), s = left % 60;
    clock.textContent = (h ? h + ':' + pad(m) : m) + ':' + pad(s) + ' left';
    clock.classList.toggle('is-low', left <= 300);
    if (left === 0) { clearInterval(timer); timeUp(); }
  }
  var timer = setInterval(tick, 1000);
  tick();
  form.addEventListener('learn:closed', function () {
    if (!form.getAttribute('data-time-up')) { clearInterval(timer); timeUp(); }
  });
})();
