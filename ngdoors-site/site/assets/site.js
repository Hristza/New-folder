/* NG Doors — nav, rail, lightbox, facet filter, enquiry mailto. No dependencies. */
(function () {
  'use strict';

  /* ---------------------------------------------------------- mobile nav */
  var burger = document.querySelector('.burger');
  var nav = document.getElementById('nav');
  if (burger && nav) {
    burger.addEventListener('click', function () {
      var open = nav.getAttribute('data-open') === 'true';
      nav.setAttribute('data-open', open ? 'false' : 'true');
      burger.setAttribute('aria-expanded', open ? 'false' : 'true');
    });
    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        nav.setAttribute('data-open', 'false');
        burger.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.getAttribute('data-open') === 'true') {
        nav.setAttribute('data-open', 'false');
        burger.setAttribute('aria-expanded', 'false');
        burger.focus();
      }
    });
  }

  /* ---------------------------------------------------------- category rail */
  var rail = document.getElementById('rail');
  if (rail) {
    var step = function () { return Math.max(200, rail.clientWidth * 0.7); };
    var prev = document.querySelector('.rail-prev');
    var next = document.querySelector('.rail-next');
    if (prev) prev.addEventListener('click', function () { rail.scrollBy({ left: -step(), behavior: 'smooth' }); });
    if (next) next.addEventListener('click', function () { rail.scrollBy({ left: step(), behavior: 'smooth' }); });
  }

  /* ---------------------------------------------------------- lightbox */
  var dlg = document.getElementById('lightbox');
  var lbImg = document.getElementById('lb-img');
  var lbCount = document.getElementById('lb-counter');
  var shots = [];
  var at = 0;

  function show(i) {
    if (!shots.length) return;
    at = (i + shots.length) % shots.length;
    lbImg.src = shots[at];
    lbCount.textContent = shots.length > 1 ? (at + 1) + ' / ' + shots.length : '';
    var oneOnly = shots.length < 2;
    dlg.querySelector('.lb-prev').hidden = oneOnly;
    dlg.querySelector('.lb-next').hidden = oneOnly;
  }

  function open(list, i) {
    shots = list;
    show(i);
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');
  }

  if (dlg) {
    dlg.querySelector('.lb-close').addEventListener('click', function () { dlg.close(); });
    dlg.querySelector('.lb-prev').addEventListener('click', function () { show(at - 1); });
    dlg.querySelector('.lb-next').addEventListener('click', function () { show(at + 1); });
    dlg.addEventListener('click', function (e) {
      // clicking the backdrop (the dialog element itself, or the padded stage) closes
      if (e.target === dlg || e.target.classList.contains('lb-stage')) dlg.close();
    });
    document.addEventListener('keydown', function (e) {
      if (!dlg.open) return;
      if (e.key === 'ArrowRight') { show(at + 1); }
      else if (e.key === 'ArrowLeft') { show(at - 1); }
    });
  }

  function parseGallery(el) {
    try { return JSON.parse(el.getAttribute('data-gallery')) || []; }
    catch (err) { return []; }
  }

  /* gallery album grids */
  var albums = document.querySelectorAll('[data-gallery]');
  Array.prototype.forEach.call(albums, function (holder) {
    var list = parseGallery(holder);
    if (!list.length) return;
    if (holder.classList.contains('gallery-main')) {
      holder.addEventListener('click', function () {
        var main = document.getElementById('pmain');
        var idx = main && main.dataset.at ? parseInt(main.dataset.at, 10) : 0;
        open(list, idx || 0);
      });
      return;
    }
    holder.addEventListener('click', function (e) {
      var btn = e.target.closest('.photo');
      if (!btn) return;
      open(list, parseInt(btn.getAttribute('data-i'), 10) || 0);
    });
  });

  /* ---------------------------------------------------------- product thumbs */
  var main = document.getElementById('pmain');
  var thumbs = document.querySelectorAll('.thumb');
  if (main && thumbs.length) {
    var mainImg = main.querySelector('img');
    Array.prototype.forEach.call(thumbs, function (t) {
      t.addEventListener('click', function () {
        var inner = t.querySelector('img');
        mainImg.src = inner.src;
        mainImg.srcset = inner.srcset;
        main.dataset.at = t.getAttribute('data-i');
        Array.prototype.forEach.call(thumbs, function (o) { o.removeAttribute('aria-current'); });
        t.setAttribute('aria-current', 'true');
      });
    });
  }

  /* ---------------------------------------------------------- facet filter */
  var facets = document.getElementById('facets');
  var fgrid = document.getElementById('filtergrid');
  if (facets && fgrid) {
    facets.addEventListener('click', function (e) {
      var btn = e.target.closest('.chip');
      if (!btn) return;
      Array.prototype.forEach.call(facets.querySelectorAll('.chip'), function (c) {
        c.setAttribute('aria-pressed', c === btn ? 'true' : 'false');
      });
      var f = btn.getAttribute('data-f');
      var shown = 0;
      Array.prototype.forEach.call(fgrid.children, function (cell) {
        var ok = f === '*' ||
          (f.charAt(0) === 't' && cell.getAttribute('data-t') === f.slice(2)) ||
          (f.charAt(0) === 'a' && cell.getAttribute('data-a') === f.slice(2));
        cell.hidden = !ok;
        if (ok) shown++;
      });
      var note = document.querySelector('.count-note');
      if (note) note.textContent = shown + ' от ' + fgrid.children.length + ' артикула';
    });
  }

  /* ---------------------------------------------------------- enquiry form */
  var form = document.getElementById('enquiry-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var d = new FormData(form);
      var body = 'Име: ' + (d.get('name') || '') +
        '\nЗа връзка: ' + (d.get('contact') || '') +
        '\nИнтерес: ' + (d.get('topic') || '') +
        '\n\n' + (d.get('message') || '');
      window.location.href = 'mailto:info@ngdoors.bg?subject=' +
        encodeURIComponent('Запитване от сайта') + '&body=' + encodeURIComponent(body);
    });
  }

  /* ---------------------------------------------------------- size picker */
  /* Repricing mirrors build.py's money(): euro primary at the fixed statutory
     rate, lev in brackets, comma decimal separator. The two must agree exactly —
     check.py compares a sample of them, because a price that changes format when
     you touch it reads as a broken page. */
  var BGN_PER_EUR = 1.95583;

  function money(bgn) {
    var eur = (bgn / BGN_PER_EUR).toFixed(2).replace('.', ',');
    var lev = bgn.toFixed(2).replace('.', ',');
    return '<span class="eur">' + eur + ' €</span> <span class="bgn">(' + lev + ' лв.)</span>';
  }

  var group = document.querySelector('.sizes[role="radiogroup"]');
  var priceEl = document.querySelector('.price-big[data-bgn]');
  if (group && priceEl) {
    var pills = [].slice.call(group.querySelectorAll('.size-pill'));
    var base = parseFloat(priceEl.getAttribute('data-bgn'));
    var cta = document.querySelector('.product-cta a[href^="mailto:"]');
    var ctaHref = cta ? cta.getAttribute('href') : null;

    function select(pill, focus) {
      pills.forEach(function (p) {
        var on = p === pill;
        p.setAttribute('aria-checked', on ? 'true' : 'false');
        p.tabIndex = on ? 0 : -1;
      });
      var total = base + parseFloat(pill.getAttribute('data-delta') || '0');
      priceEl.innerHTML = money(total);
      /* Re-trigger the value-change transition without animating layout. */
      priceEl.classList.remove('price-bump');
      void priceEl.offsetWidth;
      priceEl.classList.add('price-bump');
      /* The enquiry should say which size she is being asked about. */
      if (cta && ctaHref) {
        cta.setAttribute('href', ctaHref + '%20—%20' +
          encodeURIComponent(pill.getAttribute('data-size')));
      }
      if (focus) pill.focus();
    }

    group.addEventListener('click', function (e) {
      var pill = e.target.closest ? e.target.closest('.size-pill') : null;
      if (pill) select(pill, false);
    });

    group.addEventListener('keydown', function (e) {
      var i = pills.indexOf(document.activeElement);
      if (i < 0) return;
      var next = null;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = pills[(i + 1) % pills.length];
      else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = pills[(i - 1 + pills.length) % pills.length];
      else if (e.key === ' ' || e.key === 'Enter') next = pills[i];
      if (next) { e.preventDefault(); select(next, true); }
    });
  }

  /* ---------------------------------------------------------- scroll reveal */
  /* opacity + transform only. Never height: animating it relayouts the page and
     the reveal lands as a stutter on exactly the low-end phones it is for. */
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var reveals = [].slice.call(document.querySelectorAll('.reveal'));
  if (reveals.length) {
    if (reduced || !('IntersectionObserver' in window)) {
      reveals.forEach(function (el) { el.classList.add('is-in'); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          var el = en.target;
          /* Stagger by position within the parent, capped so a 24-card grid does
             not make the last card wait two seconds to exist. */
          var sibs = [].slice.call(el.parentNode.children);
          el.style.transitionDelay = Math.min(sibs.indexOf(el), 5) * 60 + 'ms';
          el.classList.add('is-in');
          io.unobserve(el);
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
      reveals.forEach(function (el) { io.observe(el); });

      /* Safety net. An IntersectionObserver only fires for elements that actually
         intersect, so pressing End jumps the viewport over everything in between
         and those cards stay at opacity 0 for good — content permanently invisible
         because of a decoration. Anything already above the fold is revealed here
         whether or not it was ever observed. Self-removing once nothing is left. */
      var pending = reveals.slice();
      var sweep = function () {
        for (var i = pending.length - 1; i >= 0; i--) {
          var el = pending[i];
          if (el.classList.contains('is-in')) { pending.splice(i, 1); continue; }
          if (el.getBoundingClientRect().top < window.innerHeight) {
            io.unobserve(el);
            el.classList.add('is-in');
            pending.splice(i, 1);
          }
        }
        if (!pending.length) window.removeEventListener('scroll', onScroll);
      };
      var ticking = false;
      var onScroll = function () {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(function () { ticking = false; sweep(); });
      };
      window.addEventListener('scroll', onScroll, { passive: true });
    }
  }

  /* ---------------------------------------------------------- scene films */
  /* Every clip is silent, looping and decorative, so nothing here needs to
     recover from a refusal: autoplay is a request, not a guarantee, and a clip
     that never starts simply stays on its poster, which is its own first frame.
     That is why there is no error branch and no fallback image to swap in.

     Two jobs. Play only what is on screen, because a paused offscreen video is
     the difference between one decoded stream and four on a phone. And carry a
     slow parallax on the bands, which is the whole reason the film is taller
     than the band it sits in. */
  var films = [].slice.call(document.querySelectorAll('[data-film]'));
  if (films.length) {
    if (reduced) {
      films.forEach(function (v) { v.removeAttribute('autoplay'); v.pause(); });
    } else {
      var live = [];
      var start = function (v) {
        var go = v.play();
        if (go && go.catch) go.catch(function () {});
      };

      if ('IntersectionObserver' in window) {
        var vio = new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            var v = en.target;
            var i = live.indexOf(v);
            if (en.isIntersecting) {
              if (i < 0) live.push(v);
              start(v);
            } else {
              if (i >= 0) live.splice(i, 1);
              v.pause();
            }
          });
        }, { rootMargin: '200px 0px' });
        films.forEach(function (v) { vio.observe(v); });
      } else {
        live = films.slice();
        films.forEach(start);
      }

      /* Parallax, on the bands only -- the hero already moves, and moving its
         box as well would fight the shot. The film has 9% of slack above and
         below it, so the travel is capped well inside that and no gap can open
         at either end however tall the band gets. */
      var bands = films.filter(function (v) {
        return v.parentNode && v.parentNode.classList.contains('scene');
      });
      bands.forEach(function (v) { v.setAttribute('data-parallax', 'true'); });

      if (bands.length) {
        var pTick = false;
        var drift = function () {
          var vh = window.innerHeight || 1;
          bands.forEach(function (v) {
            var r = v.parentNode.getBoundingClientRect();
            if (r.bottom < 0 || r.top > vh) return;
            /* -1 when the band is entering at the bottom, +1 when it leaves
               the top, 0 when it is centred. */
            var t = ((vh - r.top) / (vh + r.height)) * 2 - 1;
            v.style.transform = 'translate3d(0,' + (t * 5).toFixed(2) + '%,0)';
          });
        };
        var onDrift = function () {
          if (pTick) return;
          pTick = true;
          window.requestAnimationFrame(function () { pTick = false; drift(); });
        };
        window.addEventListener('scroll', onDrift, { passive: true });
        window.addEventListener('resize', onDrift, { passive: true });
        drift();
      }
    }
  }

  /* ---------------------------------------------------------- sticky price */
  var bar = document.getElementById('stickybuy');
  if (bar && priceEl) {
    var anchor = priceEl;
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (e) {
        bar.setAttribute('data-show', e[0].isIntersecting ? 'false' : 'true');
      }, { rootMargin: '-90px 0px 0px 0px' }).observe(anchor);
    }
  }
})();
