(() => {
  const QUICK = `npx keyrelay run --env DEMO_TOKEN -- node -e "console.log(process.env.DEMO_TOKEN ? 'Handoff complete.' : 'No value received.')"`;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const app = document.getElementById('app');

  /* Copy CTA with inline success and error states */
  document.querySelectorAll('[data-copy]').forEach(btn => btn.addEventListener('click', async () => {
    const status = btn.closest('.cta-row')?.querySelector('.status');
    try {
      await navigator.clipboard.writeText(QUICK);
      if (status) { status.textContent = 'Copied. Paste it in your terminal and open the printed link.'; status.className = 'status t-sm ok'; }
      else { const t = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => btn.textContent = t, 1800); }
    } catch {
      if (status) { status.textContent = 'Copy failed. Your browser blocked clipboard access, so select the command and copy it by hand.'; status.className = 'status t-sm err'; }
    }
    document.body.classList.remove('menu-open');
  }));

  /* Mobile menu */
  const toggle = document.querySelector('.toggle');
  toggle.addEventListener('click', () => {
    const open = document.body.classList.toggle('menu-open');
    toggle.setAttribute('aria-expanded', open); toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  });
  document.querySelectorAll('.panel a').forEach(a => a.addEventListener('click', () => {
    document.body.classList.remove('menu-open'); toggle.setAttribute('aria-expanded', 'false');
  }));

  /* Current section in nav */
  const spyLinks = document.querySelectorAll('[data-spy]');
  const spy = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) spyLinks.forEach(a => a.setAttribute('aria-current', a.dataset.spy === e.target.id ? 'true' : 'false'));
  }), { rootMargin: '-45% 0px -50% 0px' });
  ['top','why','how','proof','security','faq','start'].forEach(id => spy.observe(document.getElementById(id)));

  /* Hero appear: page opens plain, then settles in once on load */
  const startHero = () => requestAnimationFrame(() => requestAnimationFrame(() => {
    app.classList.add('loaded');
    // the hero mockup starts its own card intro after the headline lands
    setTimeout(() => document.getElementById('mock').classList.add('in'), reduce ? 0 : 450);
  }));
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(startHero);

  /* Scroll reveals for text sections, once */
  const rvObs = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); rvObs.unobserve(e.target); }
  }), { threshold: 0.15 });
  document.querySelectorAll('.rv').forEach(el => rvObs.observe(el));

  /* Card intros (bento, demo recording) at about 30% visible, once */
  const introAt = new Map();
  const cardObs = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); introAt.set(e.target.id, performance.now()); cardObs.unobserve(e.target); }
  }), { threshold: 0.3 });
  ['bento', 'gif'].forEach(id => cardObs.observe(document.getElementById(id)));

  /* Header shifts one surface step once the hero top scrolls under it */
  const bar = document.getElementById('bar');
  new IntersectionObserver(([e]) => bar.classList.toggle('scrolled', !e.isIntersecting), { rootMargin: '-65px 0px 0px 0px' })
    .observe(document.getElementById('top-edge'));

  if (reduce) return; // stories off: every visual rests on its design state

  /* Story clock: one rAF loop, per card time advances only while the bento is on screen */
  const easeInOut = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;
  const easeOut = t => 1 - Math.pow(1 - t, 3);
  function track(keys, t, ease = easeInOut) {
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [t1, v1] = keys[i], [t0, v0] = keys[i - 1];
      if (t <= t1) { const k = ease(Math.min(1, (t - t0) / (t1 - t0 || 1))); return v0 + (v1 - v0) * k; }
    }
    return keys[keys.length - 1][1];
  }
  const $ = id => document.getElementById(id);
  const bento = $('bento');
  let visible = false, clock = 0, last = 0;
  new IntersectionObserver(es => es.forEach(e => visible = e.isIntersecting)).observe(bento);
  const START = 2.4, OFFSETS = [0, 1.2, 2.4];

  // Story 1: the command in the instruction deletes and retypes glyph by glyph; the agent's call rises back after it
  const CMD = $('s0-cmd').textContent, cmdEl = $('s0-cmd'), caret = $('s0-caret'), l1 = $('s0-l1'), l2 = $('s0-l2');
  const DEL = .03, TYPE = .05, P0 = 5.8;
  const rise = (el, a) => { el.style.opacity = a; el.style.transform = `translateY(${(1-a)*10}px)`; el.style.filter = `blur(${(1-a)*4}px)`; };
  function story0(t) {
    const n = CMD.length, delEnd = .4 + n * DEL, typeStart = delEnd + .3, typeEnd = typeStart + n * TYPE;
    let shown = n;
    if (t > .4 && t < delEnd) shown = n - Math.floor((t - .4) / DEL);
    else if (t >= delEnd && t < typeStart) shown = 0;
    else if (t >= typeStart && t < typeEnd) shown = Math.floor((t - typeStart) / TYPE);
    cmdEl.textContent = CMD.slice(0, shown);
    const typing = t > .2 && t < typeEnd + .9;
    caret.style.opacity = typing ? ((t % 1) < .55 || (t > .4 && t < typeEnd) ? 1 : 0) : 0;
    rise(l1, track([[0,1],[.3,1],[.6,0],[typeEnd+.15,0],[typeEnd+.6,1]], t, easeOut));
    rise(l2, track([[0,1],[.3,1],[.6,0],[typeEnd+.5,0],[typeEnd+.95,1]], t, easeOut));
  }

  // Story 2: dots fill the first field, then the second, Send once presses, the fields clear and the confirmation shows
  const f0 = $('s1-f0'), f1 = $('s1-f1'), sbtn = $('s1-btn'), msg = $('s1-msg'), P1 = 6.4;
  const dots = (el, n) => { if (el.childElementCount !== n) el.innerHTML = '<i></i>'.repeat(n); };
  function story1(t) {
    const sent = t >= 3.3;
    dots(f0, sent || t < .5 ? 0 : Math.min(12, Math.floor((t - .5) / .1) + 1));
    dots(f1, sent || t < 1.9 ? 0 : Math.min(10, Math.floor((t - 1.9) / .1) + 1));
    f0.classList.toggle('focus', t > .3 && t < 1.75);
    f1.classList.toggle('focus', t >= 1.75 && t < 3.3);
    sbtn.style.transform = `scale(${track([[3.0,1],[3.12,.97],[3.3,1]], t)})`;
    sbtn.style.opacity = t > 3.12 && t < 3.5 ? .6 : 1;
    rise(msg, track([[3.4,0],[3.9,1],[5.4,1],[6.0,0]], t, easeOut));
  }

  // Story 3: the agent's copy leaves, arrives showing the raw echo, then the redaction chip replaces it with a ring
  const rows = [$('s2-l0'), $('s2-l1'), $('s2-l2')], raw = $('s2-raw'), chip = $('s2-chip'), P2 = 5.2;
  function story2(t) {
    rows.forEach((r, i) => rise(r, track([[0,1],[.3+i*.06,1],[.75+i*.06,0],[1.2+i*.4,0],[1.8+i*.4,1]], t, easeOut)));
    const unredacted = t > .9 && t < 2.6;
    raw.style.display = unredacted ? 'inline' : 'none';
    chip.style.display = unredacted ? 'none' : 'inline-block';
    chip.style.transform = `scale(${t < 2.6 ? 1 : track([[2.6,.86],[2.85,1.1],[3.2,1]], t)})`;
    chip.style.boxShadow = `0 0 0 ${track([[2.6,0],[2.9,3],[3.7,0]], t)}px rgba(103,232,249,.35)`;
  }
  const stories = [[story0, P0], [story1, P1], [story2, P2]];

  function frame(now) {
    const dt = last ? Math.min(.05, (now - last) / 1000) : 0; last = now;
    if (visible && introAt.has('bento')) {
      clock += dt;
      stories.forEach(([fn, period], i) => {
        const local = clock - START - OFFSETS[i];
        // each run starts and ends on the design state, then a short rest
        fn(local < 0 ? 0 : local % (period + .8) > period ? 0 : local % (period + .8));
      });
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
