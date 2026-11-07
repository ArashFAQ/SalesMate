/* نمودار خطی SVG (بدون کتابخانه): چند سری با مقیاس جدا، برچسب روی نقطه، اسکرول افقی */
'use strict';
function lineChart(points, series, opt) {
  opt = opt || {};
  if (!points.length) return '<div class="empty">داده‌ای نیست</div>';
  const slot = opt.slot || 70, H = opt.h || 250, padT = 40, padB = 46, padX = 14;
  const W = Math.max(320, points.length * slot + padX * 2), plotH = H - padT - padB;
  const maxes = series.map(s => Math.max(1e-9, ...points.map(p => +p[s.key] || 0)));
  const X = i => padX + slot * (i + 0.5);
  let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" style="display:block">';
  for (let g = 0; g <= 4; g++) { const y = padT + plotH * g / 4; svg += '<line x1="0" x2="' + W + '" y1="' + y + '" y2="' + y + '" stroke="#CBD5E1" stroke-opacity=".35"/>'; }
  series.forEach((s, si) => {
    const Y = v => padT + plotH - ((+v || 0) / maxes[si]) * plotH;
    const pts = points.map((p, i) => [X(i), Y(p[s.key])]);
    if (si === 0 && pts.length > 1) svg += '<path d="M' + pts[0][0] + ',' + (padT + plotH) + ' ' + pts.map(q => 'L' + q[0] + ',' + q[1]).join(' ') + ' L' + pts[pts.length - 1][0] + ',' + (padT + plotH) + 'Z" fill="' + s.color + '" fill-opacity=".10"/>';
    svg += '<polyline fill="none" stroke="' + s.color + '" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round" points="' + pts.map(q => q.join(',')).join(' ') + '"/>';
    pts.forEach((q, i) => {
      svg += '<circle cx="' + q[0] + '" cy="' + q[1] + '" r="4" fill="#fff" stroke="' + s.color + '" stroke-width="2.2"/>';
      const lab = s.fmt ? s.fmt(points[i][s.key]) : String(points[i][s.key]);
      const dy = si === 0 ? -9 : 17;
      svg += '<text x="' + q[0] + '" y="' + (q[1] + dy) + '" text-anchor="middle" font-size="10" font-weight="700" fill="' + s.color + '" stroke="var(--card)" stroke-width="3" paint-order="stroke">' + esc(lab) + '</text>';
    });
  });
  points.forEach((p, i) => {
    svg += '<text x="' + X(i) + '" y="' + (H - 26) + '" text-anchor="middle" font-size="11" font-weight="700" fill="currentColor">' + esc(p.label) + '</text>';
    if (p.sub) svg += '<text x="' + X(i) + '" y="' + (H - 11) + '" text-anchor="middle" font-size="9.5" fill="#94A3B8">' + esc(p.sub) + '</text>';
  });
  svg += '</svg>';
  const leg = '<div class="legend">' + series.map(s => '<span><i style="background:' + s.color + '"></i>' + esc(s.name) + '</span>').join('') + '</div>';
  return leg + '<div class="chart-wrap" dir="ltr" data-chart>' + svg + '</div>';
}
/* سه خط (کل / فروشگاه / شرکت) با مقیاس مشترک؛ هر نقطه: مبلغ (میلیارد ریال) و متراژ. points[i] = {label, sub, t:[a,m], s:[a,m], c:[a,m]} */
function lineChart3(points, opt) {
  opt = opt || {};
  if (!points.length) return '<div class="empty">داده‌ای نیست</div>';
  const slot = opt.slot || 84, H = opt.h || 340, padT = 18, padB = 46, padX = 14;
  const W = Math.max(320, points.length * slot + padX * 2), plotH = H - padT - padB, PH = 25;
  const S = [{ k: 't', name: 'کل', color: '#1565C0' }, { k: 's', name: 'فروشگاه', color: '#F59E0B' }, { k: 'c', name: 'شرکت', color: '#7C3AED' }];
  const mx = Math.max(1e-9, ...points.map(p => +p.t[0] || 0));
  const X = i => padX + slot * (i + 0.5), Y = v => padT + plotH - ((+v || 0) / mx) * plotH;
  const fa1 = v => v ? fa(v.toFixed(2).replace(/\.?0+$/, '')) : '۰';
  let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" style="display:block">';
  for (let g = 0; g <= 4; g++) { const y = padT + plotH * g / 4; svg += '<line x1="0" x2="' + W + '" y1="' + y + '" y2="' + y + '" stroke="#CBD5E1" stroke-opacity=".35"/>'; }
  S.forEach(sr => { svg += '<polyline fill="none" stroke="' + sr.color + '" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round" points="' + points.map((p, i) => X(i) + ',' + Y(p[sr.k][0])).join(' ') + '"/>'; });
  points.forEach((p, i) => {
    const placed = [], pw = Math.min(slot - 4, 78);
    S.slice().sort((a, b) => Y(p[a.k][0]) - Y(p[b.k][0])).forEach(sr => {
      const a = +p[sr.k][0] || 0, m = +p[sr.k][1] || 0, y = Y(a), x = X(i);
      svg += '<circle cx="' + x + '" cy="' + y + '" r="4" fill="#fff" stroke="' + sr.color + '" stroke-width="2.2"/>';
      if (!a && !m && sr.k !== 't') return;
      const c0 = [y - PH - 7, y + 7]; let top = null;
      for (const cy of [c0[0], c0[1], c0[0] - PH - 2, c0[1] + PH + 2, c0[0] - 2 * PH - 4, c0[1] + 2 * PH + 4]) {
        if (cy < 2 || cy + PH > padT + plotH + 4) continue;
        if (placed.every(o => cy + PH <= o || cy >= o + PH)) { top = cy; break; }
      }
      if (top === null) top = c0[0];
      placed.push(top);
      svg += '<rect x="' + (x - pw / 2) + '" y="' + top + '" width="' + pw + '" height="' + PH + '" rx="6" fill="var(--card)" fill-opacity=".92" stroke="' + sr.color + '" stroke-width="1.1"/>' +
        '<text x="' + x + '" y="' + (top + 10.5) + '" text-anchor="middle" font-size="9.5" font-weight="800" fill="currentColor">' + esc(fa1(a)) + '</text>' +
        '<text x="' + x + '" y="' + (top + 21) + '" text-anchor="middle" font-size="8.5" font-weight="700" fill="' + sr.color + '">' + esc(fa(Math.round(m))) + ' م</text>';
    });
    svg += '<text x="' + X(i) + '" y="' + (H - 26) + '" text-anchor="middle" font-size="11" font-weight="700" fill="currentColor">' + esc(p.label) + '</text>';
    if (p.sub) svg += '<text x="' + X(i) + '" y="' + (H - 11) + '" text-anchor="middle" font-size="9.5" fill="#94A3B8">' + esc(p.sub) + '</text>';
  });
  svg += '</svg>';
  const leg = '<div class="legend">' + S.map(s => '<span><i style="background:' + s.color + '"></i>' + s.name + '</span>').join('') + '<span class="muted">مبلغ به میلیارد ریال · م = متر مربع</span></div>';
  return leg + '<div class="chart-wrap" dir="ltr" data-chart>' + svg + '</div>';
}
function scrollChartsToEnd(root) {       // جدیدترین نقطه سمت راست؛ شروع از انتها
  (root || document).querySelectorAll('[data-chart]').forEach(el => { el.scrollLeft = el.scrollWidth; });
}
