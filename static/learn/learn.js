/* NRSTATLAB Learn: connects the site's own progress script to a learner's account.

   assets/progress.js (in the content repository, unchanged) draws every progress
   mark from one localStorage entry, nrstatlab.progress.v1. This script runs
   before it (it is not deferred; progress.js is) and decides what that entry holds:

   - Signed in: the account's progress, as the server sent it in the
     #nrstat-account block. What the browser held before the first sign-in is set
     aside, once, as nrstatlab.progress.v1.guest, and offered for import. Each
     press of "Mark this unit done" is then sent to the server.
   - Signed out, after being signed in on this device: the set-aside progress is
     put back, so a shared computer never shows the last learner's progress.

   nrstatlab.account holds an opaque id for the account (never the email), so
   the script can tell a first sign-in from a return visit. Every storage access
   is guarded: with storage blocked, pages work as they always have. */

(function () {
  'use strict';

  var KEY = 'nrstatlab.progress.v1';
  var GUEST = KEY + '.guest';
  var MARK = 'nrstatlab.account';

  var node = document.getElementById('nrstat-account');
  var state;
  try { state = JSON.parse(node.textContent); } catch (e) { return; }

  var store;
  try { store = window.localStorage; store.getItem(KEY); } catch (e) { return; }
  function get(k) { try { return store.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { store.setItem(k, v); return true; } catch (e) { return false; } }
  function del(k) { try { store.removeItem(k); } catch (e) { /* blocked */ } }
  function parse(s) {
    try {
      var o = JSON.parse(s);
      if (o && o.v === 1 && o.done && typeof o.done === 'object') return o;
    } catch (e) { /* unreadable */ }
    return null;
  }

  // ---- signed out: give the browser its own progress back -------------------
  if (!state.signed_in) {
    if (get(MARK) === null) return;               // never signed in here: nothing to undo
    var guest = get(GUEST);
    if (guest !== null && parse(guest)) set(KEY, guest);
    else del(KEY);
    del(GUEST);
    del(MARK);
    return;
  }

  // ---- signed in: the account's progress becomes this browser's --------------
  var before = get(MARK);
  var local = parse(get(KEY));
  if (before === null) {                          // first sign-in on this device
    if (local) set(GUEST, JSON.stringify(local));
    else del(GUEST);
  }
  set(MARK, state.account);
  // The last page read is kept for the same learner; another account's is dropped.
  var last = (before === null || before === state.account) && local ? local.last : null;
  set(KEY, JSON.stringify({ v: 1, done: state.done || {}, last: last || null }));

  var here = decodeURIComponent(window.location.pathname.slice(1));
  if (here === '' || here.slice(-1) === '/') here += 'index.html';

  function post(url, data) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': state.csrf },
      body: JSON.stringify(data)
    }).then(function (r) {
      return r.ok ? r.json() : Promise.reject(r.status);
    });
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // ---- "Mark this unit done": send each press to the account ------------------
  var correcting = false;
  function note(button, text) {
    var box = button.parentNode;
    var n = box.querySelector('.learn-note');
    if (!text) { if (n) n.remove(); return; }
    if (!n) {
      n = el('span', 'learn-note');
      n.setAttribute('role', 'status');
      box.appendChild(n);
    }
    n.textContent = text;
  }
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest && e.target.closest('.progress-toggle button');
    if (!b || correcting) return;
    // progress.js has already flipped the entry (its handler is on the button itself).
    var s = parse(get(KEY));
    var done = !!(s && s.done[here]);
    post('/me/progress/studied', { page: here, done: done }).then(function (r) {
      note(b, '');
      if (r.done !== done) {
        // The account says otherwise (a unit whose test is passed stays done):
        // press again, unsent, so the page shows the account's state.
        correcting = true;
        b.click();
        correcting = false;
        if (r.status === 'passed') note(b, 'You passed this unit’s test, so it stays done.');
      }
    }, function (status) {
      note(b, status === 403
        ? 'Not saved: you are signed out. Sign in again to save your progress.'
        : 'Not saved; check your connection. Your account is unchanged.');
    });
  });

  // ---- the offer to bring over what this browser had marked -------------------
  function offer() {
    if (!state.offer_import) return;
    var stash = parse(get(GUEST));
    if (!stash) return;
    var ids = Object.keys(stash.done).filter(function (id) { return !(state.done || {})[id]; });
    if (!ids.length) return;

    var box = el('div', 'learn-banner');
    box.setAttribute('role', 'region');
    box.setAttribute('aria-label', 'Progress saved in this browser');
    var p = el('p', null, 'This browser has ' + ids.length + ' page' + (ids.length === 1 ? '' : 's') +
                          ' marked done from before you signed in. Bring ' +
                          (ids.length === 1 ? 'it' : 'them') + ' over to your account?');
    var yes = el('button', 'learn-yes', 'Bring over');
    var no = el('button', 'learn-no', 'Not now');
    yes.type = no.type = 'button';
    var msg = el('span', 'learn-note');
    msg.setAttribute('role', 'status');
    function send(url, data) {
      yes.disabled = no.disabled = true;
      post(url, data).then(function () { window.location.reload(); }, function () {
        yes.disabled = no.disabled = false;
        msg.textContent = 'That did not go through; check your connection and try again.';
      });
    }
    yes.addEventListener('click', function () { send('/me/progress/import', { done: ids.slice(0, 400) }); });
    no.addEventListener('click', function () { send('/me/progress/import/dismiss', {}); });
    box.appendChild(p);
    box.appendChild(yes);
    box.appendChild(no);
    box.appendChild(msg);

    var nav = document.querySelector('nav.sitenav');
    if (nav) nav.parentNode.insertBefore(box, nav.nextSibling);
    else document.body.insertBefore(box, document.body.firstChild);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', offer);
  else offer();
})();
