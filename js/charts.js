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
function scrollChartsToEnd(root) {       // جدیدترین نقطه سمت راست؛ شروع از انتها
  (root || document).querySelectorAll('[data-chart]').forEach(el => { el.scrollLeft = el.scrollWidth; });
}
