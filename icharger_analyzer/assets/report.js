(() => {
  'use strict';
  const cards = [...document.querySelectorAll('.chart-card')];
  const select = document.getElementById('chart-select');
  const config = JSON.parse(document.getElementById('plot-config').textContent);
  const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));
  const axisKeys = gd => Object.keys(gd.layout).filter(k => /^yaxis\d*$/.test(k));
  let selected = 0;

  async function load(card) {
    if (card.loadPromise) return card.loadPromise;
    card.loadPromise = (async () => {
      const gd = card.querySelector('.plot-host');
      const spec = JSON.parse(card.querySelector('.plot-data').textContent);
      await Plotly.newPlot(gd, spec.data, spec.layout, config);
      card.dataset.ready = 'true';
      const xs = gd._fullData.flatMap(t => Array.from(t.x || []).filter(Number.isFinite));
      let lo = Infinity, hi = -Infinity;
      for (const x of xs) { lo = Math.min(lo, x); hi = Math.max(hi, x); }
      if (!Number.isFinite(lo)) { lo = 0; hi = 1; }
      if (hi <= lo) hi = lo + 1;
      const full = [lo, hi], span = hi - lo;
      const zoom = card.querySelector('[data-control=zoom]');
      const position = card.querySelector('[data-control=position]');
      const rangeText = card.querySelector('.range-text');
      const current = () => gd._fullLayout.xaxis.range.map(Number);
      function sync() {
        const [a, b] = current();
        const width = b - a;
        zoom.value = Math.log10(Math.max(1, span / width)) / 3 * 1000;
        const travel = span - width;
        position.disabled = travel <= span * 1e-8;
        position.value = travel > 0 ? clamp((a - lo) / travel * 1000, 0, 1000) : 0;
        rangeText.textContent = `${a.toFixed(2)} — ${b.toFixed(2)}`;
      }
      function setRange(a, b) {
        const width = clamp(b - a, span / 1000, span);
        a = clamp(a, lo, hi - width);
        return Plotly.relayout(gd, {'xaxis.range': [a, a + width], 'xaxis.autorange': false});
      }
      function scaleX(factor) {
        const [a, b] = current(), middle = (a + b) / 2;
        const width = Math.min(span, (b - a) * factor);
        return setRange(middle - width / 2, middle + width / 2);
      }
      function scaleY(factor) {
        const patch = {};
        for (const axis of axisKeys(gd)) {
          const [a, b] = gd._fullLayout[axis].range, mid = (a + b) / 2;
          patch[axis + '.range'] = [mid - (b - a) * factor / 2, mid + (b - a) * factor / 2];
          patch[axis + '.autorange'] = false;
        }
        return Plotly.relayout(gd, patch);
      }
      function fitY() {
        const [a, b] = current(), bounds = {};
        for (const trace of gd._fullData) {
          if (trace.visible === false || trace.visible === 'legendonly') continue;
          const key = 'yaxis' + (trace.yaxis || 'y').slice(1);
          const extent = bounds[key] || [Infinity, -Infinity];
          for (let i = 0; i < (trace.x || []).length; i++) {
            const x = trace.x[i], y = trace.y[i];
            if (x >= a && x <= b && Number.isFinite(y)) {
              extent[0] = Math.min(extent[0], y); extent[1] = Math.max(extent[1], y);
            }
          }
          bounds[key] = extent;
        }
        const patch = {};
        for (const [axis, [min, max]] of Object.entries(bounds)) {
          if (!Number.isFinite(min)) continue;
          const pad = Math.max((max - min) * .08, Math.abs(max) * .005, .001);
          patch[axis + '.range'] = [min - pad, max + pad];
          patch[axis + '.autorange'] = false;
        }
        return Plotly.relayout(gd, patch);
      }
      // Coalesce slider input so a long log never builds a render queue.
      let scheduled = false, pending;
      function schedule(action) {
        pending = action;
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(async () => {
          const next = pending; pending = null;
          try { await next(); } finally { scheduled = false; if (pending) schedule(pending); }
        });
      }
      zoom.addEventListener('input', () => {
        const width = span / 10 ** (Number(zoom.value) / 1000 * 3);
        const [a, b] = current(), middle = (a + b) / 2;
        schedule(() => setRange(middle - width / 2, middle + width / 2));
      });
      position.addEventListener('input', () => {
        const [a, b] = current(), width = b - a;
        const start = lo + (span - width) * Number(position.value) / 1000;
        schedule(() => setRange(start, start + width));
      });
      card.querySelectorAll('[data-action]').forEach(button => {
        button.addEventListener('click', async () => {
          const action = button.dataset.action;
          if (action === 'zoom-in') await scaleX(.5);
          if (action === 'zoom-out') await scaleX(2);
          if (action === 'y-in') await scaleY(.5);
          if (action === 'y-out') await scaleY(2);
          if (action === 'fit-y') await fitY();
          if (action === 'left' || action === 'right') {
            const [a, b] = current(), shift = (b - a) * .25 * (action === 'left' ? -1 : 1);
            await setRange(a + shift, b + shift);
          }
          if (action === 'reset') {
            const patch = {'xaxis.range': full, 'xaxis.autorange': false};
            axisKeys(gd).forEach(axis => { patch[axis + '.autorange'] = true; });
            await Plotly.relayout(gd, patch);
          }
          if (action === 'box') {
            const enabled = button.getAttribute('aria-pressed') !== 'true';
            button.setAttribute('aria-pressed', String(enabled));
            await Plotly.relayout(gd, {dragmode: enabled ? 'zoom' : 'pan'});
          }
          if (action === 'expand') await expand(card);
          if (action === 'export') await Plotly.downloadImage(gd, {
            format: 'png', filename: 'icharger-' + card.id, width: 1600, height: 800,
          });
        });
      });
      gd.on('plotly_relayout', sync);
      let previousWidth = gd.clientWidth;
      const resizeObserver = new ResizeObserver(() => {
        if (Math.abs(gd.clientWidth - previousWidth) < 1) return;
        previousWidth = gd.clientWidth;
        requestAnimationFrame(() => Plotly.Plots.resize(gd));
      });
      resizeObserver.observe(gd);
      await setRange(...full);
      sync();
      return gd;
    })().catch(error => {
      card.querySelector('.plot-host').textContent = 'Не удалось открыть график: ' + error.message;
      card.querySelector('.plot-host').classList.add('js-error');
      throw error;
    });
    return card.loadPromise;
  }

  async function expand(card) {
    const closing = card.classList.contains('expanded');
    for (const other of cards.filter(c => c.classList.contains('expanded'))) {
      other.classList.remove('expanded');
      other.querySelector('[data-action=expand]').textContent = 'Развернуть';
      other.querySelector('[data-action=expand]').setAttribute('aria-expanded', 'false');
      await Plotly.relayout(other.querySelector('.plot-host'), {height: 470});
    }
    if (!closing) {
      card.classList.add('expanded');
      card.querySelector('[data-action=expand]').textContent = 'Свернуть';
      card.querySelector('[data-action=expand]').setAttribute('aria-expanded', 'true');
      await Plotly.relayout(card.querySelector('.plot-host'), {height: Math.max(340, innerHeight - 230)});
    }
    document.body.classList.toggle('has-expanded', !closing);
    await Plotly.Plots.resize(card.querySelector('.plot-host'));
  }
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      const card = cards.find(c => c.classList.contains('expanded'));
      if (card) expand(card);
    }
  });
  async function go(index) {
    selected = clamp(index, 0, cards.length - 1);
    select.value = String(selected);
    await load(cards[selected]);
    cards[selected].scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'});
  }
  select?.addEventListener('change', () => go(Number(select.value)));
  document.getElementById('chart-prev')?.addEventListener('click', () => go(selected - 1));
  document.getElementById('chart-next')?.addEventListener('click', () => go(selected + 1));
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      load(entry.target).catch(() => {});
      observer.unobserve(entry.target);
    }
  }, {rootMargin: '500px'});
  cards.forEach(card => observer.observe(card));
})();
