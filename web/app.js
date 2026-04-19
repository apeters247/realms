// REALMS frontend — vanilla JS + D3 + Leaflet
const API = (path) => `${window.location.origin}${path}`;

async function fetchJSON(path) {
  const resp = await fetch(API(path));
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} on ${path}`);
  return resp.json();
}

// -------------- Navigation --------------
document.querySelectorAll('.nav button').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav button').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    const view = btn.dataset.view;
    document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
    document.getElementById(`view-${view}`).classList.add('active');
    loadView(view);
  });
});

const loaded = new Set();
function loadView(view) {
  if (view === 'entities') return renderEntities();
  if (view === 'hierarchy' && !loaded.has('hierarchy')) { renderHierarchy(); loaded.add('hierarchy'); return; }
  if (view === 'graph' && !loaded.has('graph')) { initGraphView(); loaded.add('graph'); return; }
  if (view === 'map' && !loaded.has('map')) { renderMap(); loaded.add('map'); return; }
  if (view === 'search') return;
  if (view === 'stats') return renderStats();
  if (view === 'sources') return renderSources();
}

// -------------- Entities view --------------
let entityPage = 1;
const PER_PAGE = 25;

function currentEntityFilters() {
  return {
    q: document.getElementById('entity-q').value.trim(),
    entity_type: document.getElementById('entity-type').value,
    alignment: document.getElementById('entity-alignment').value,
    realm: document.getElementById('entity-realm').value,
  };
}

async function renderEntities() {
  const f = currentEntityFilters();
  const params = new URLSearchParams({ page: entityPage, per_page: PER_PAGE });
  for (const [k, v] of Object.entries(f)) if (v) params.set(k, v);
  const data = await fetchJSON(`/entities/?${params}`);
  const tbody = document.querySelector('#entity-table tbody');
  tbody.innerHTML = '';
  for (const e of data.data) {
    const tr = document.createElement('tr');
    tr.dataset.id = e.id;
    tr.innerHTML = `
      <td>${escapeHtml(e.name)}</td>
      <td>${e.entity_type || ''}</td>
      <td>${e.alignment || ''}</td>
      <td>${e.realm || ''}</td>
      <td>${(e.consensus_confidence || 0).toFixed(2)}</td>
    `;
    tr.addEventListener('click', () => {
      document.querySelectorAll('#entity-table tbody tr').forEach((r) => r.classList.remove('selected'));
      tr.classList.add('selected');
      renderEntityDetail(e.id);
    });
    tbody.appendChild(tr);
  }
  renderPagination(data.pagination);
}

function renderPagination(p) {
  const el = document.getElementById('entity-pagination');
  el.innerHTML = `
    <span>${p.total} total</span>
    <button id="prev" ${p.page <= 1 ? 'disabled' : ''}>← Prev</button>
    <span>Page ${p.page} / ${p.total_pages || 1}</span>
    <button id="next" ${p.page >= p.total_pages ? 'disabled' : ''}>Next →</button>
  `;
  el.querySelector('#prev').addEventListener('click', () => { entityPage = Math.max(1, entityPage - 1); renderEntities(); });
  el.querySelector('#next').addEventListener('click', () => { entityPage += 1; renderEntities(); });
}

['entity-q', 'entity-type', 'entity-alignment', 'entity-realm'].forEach((id) => {
  document.getElementById(id).addEventListener('input', () => { entityPage = 1; renderEntities(); });
});

async function renderEntityDetail(id) {
  const data = await fetchJSON(`/entities/${id}`);
  const e = data.data;
  const el = document.getElementById('entity-detail');
  el.classList.remove('detail-empty');
  el.classList.add('detail');

  const altNames = Object.entries(e.alternate_names || {})
    .map(([lang, names]) => `<span class="badge"><strong>${lang}:</strong> ${names.join(', ')}</span>`)
    .join('');
  const powers = (e.powers || []).map((p) => `<span class="badge">${escapeHtml(p)}</span>`).join('');
  const domains = (e.domains || []).map((d) => `<span class="badge">${escapeHtml(d)}</span>`).join('');
  const cultures = (e.cultural_associations || []).map((c) => `<span class="badge">${escapeHtml(c)}</span>`).join('');
  const regions = (e.geographical_associations || []).map((r) => `<span class="badge">${escapeHtml(r)}</span>`).join('');

  const rels = Object.entries(e.relationships || {}).map(([type, list]) => `
    <div class="row">
      <div class="k">${type.replace(/_/g, ' ')}</div>
      ${list.map((r) => `<span class="badge">${escapeHtml(r.entity_name || '?')}</span>`).join('')}
    </div>
  `).join('');

  const sources = (e.sources || []).map((s) => `
    <div class="row">
      <span class="badge">#${s.id}</span> ${escapeHtml(s.source_name)} <small>(conf ${(s.credibility_score || 0).toFixed(2)})</small>
    </div>
  `).join('');

  const extractions = (e.extraction_details || []).slice(0, 3).map((x) => `
    <div class="quote">${escapeHtml(x.raw_quote || '(no quote)')}</div>
  `).join('');

  el.innerHTML = `
    <h2>${escapeHtml(e.name)}</h2>
    <div class="row"><span class="k">Type</span><span class="v">${e.entity_type || '—'}</span></div>
    <div class="row"><span class="k">Alignment</span><span class="v">${e.alignment || '—'}</span></div>
    <div class="row"><span class="k">Realm</span><span class="v">${e.realm || '—'}</span></div>
    <div class="row"><span class="k">Confidence</span><span class="v">${(e.consensus_confidence || 0).toFixed(2)}</span></div>
    ${e.description ? `<p>${escapeHtml(e.description)}</p>` : ''}
    ${altNames ? `<div class="section"><h3>Alternate names</h3>${altNames}</div>` : ''}
    ${powers ? `<div class="section"><h3>Powers</h3>${powers}</div>` : ''}
    ${domains ? `<div class="section"><h3>Domains</h3>${domains}</div>` : ''}
    ${cultures ? `<div class="section"><h3>Cultures</h3>${cultures}</div>` : ''}
    ${regions ? `<div class="section"><h3>Regions</h3>${regions}</div>` : ''}
    ${rels ? `<div class="section"><h3>Relationships</h3>${rels}</div>` : ''}
    ${sources ? `<div class="section"><h3>Sources</h3>${sources}</div>` : ''}
    ${extractions ? `<div class="section"><h3>Source quotes</h3>${extractions}</div>` : ''}
  `;
}

// -------------- Hierarchy (D3) --------------
async function renderHierarchy() {
  const data = await fetchJSON('/hierarchy/tree');
  const tree = data.data;
  const el = document.getElementById('hierarchy-tree');
  el.innerHTML = '';

  const width = el.clientWidth || 900;
  const dx = 20;
  const dy = 180;

  const root = d3.hierarchy(tree);
  root.x0 = 0;
  root.y0 = 0;
  root.descendants().forEach((d, i) => { d.id = i; d._children = d.children; if (d.depth && d.data.type !== 'category') d.children = null; });

  const svg = d3.select(el).append('svg')
    .attr('viewBox', [-40, -20, width, 600])
    .style('width', '100%')
    .style('height', '70vh')
    .style('font', '12px sans-serif')
    .style('user-select', 'none');

  const gLink = svg.append('g').attr('fill', 'none').attr('stroke', '#30363d').attr('stroke-width', 1.5);
  const gNode = svg.append('g').attr('cursor', 'pointer').attr('pointer-events', 'all');

  function update(source) {
    const treeLayout = d3.tree().nodeSize([dx, dy]);
    treeLayout(root);

    const nodes = root.descendants();
    const links = root.links();

    let left = root, right = root;
    root.eachBefore((n) => {
      if (n.x < left.x) left = n;
      if (n.x > right.x) right = n;
    });
    const height = right.x - left.x + 80;
    svg.transition().duration(250).attr('viewBox', [-40, left.x - 20, width, height]);

    const node = gNode.selectAll('g').data(nodes, (d) => d.id);
    const nodeEnter = node.enter().append('g')
      .attr('transform', () => `translate(${source.y0},${source.x0})`)
      .attr('class', (d) => `node ${d.data.type || 'root'}`)
      .on('click', (_event, d) => {
        d.children = d.children ? null : d._children;
        update(d);
      });
    nodeEnter.append('circle').attr('r', 5);
    nodeEnter.append('text')
      .attr('dy', '0.32em')
      .attr('x', (d) => (d._children ? -8 : 8))
      .attr('text-anchor', (d) => (d._children ? 'end' : 'start'))
      .text((d) => `${d.data.name}${d.data.entity_count ? ` (${d.data.entity_count})` : ''}`);

    node.merge(nodeEnter).transition().duration(250)
      .attr('transform', (d) => `translate(${d.y},${d.x})`);
    node.exit().transition().duration(250)
      .attr('transform', () => `translate(${source.y},${source.x})`).remove();

    const link = gLink.selectAll('path').data(links, (d) => d.target.id);
    const linkEnter = link.enter().append('path').attr('class', 'link')
      .attr('d', () => {
        const o = { x: source.x0, y: source.y0 };
        return d3.linkHorizontal().x((d) => d.y).y((d) => d.x)({ source: o, target: o });
      });
    link.merge(linkEnter).transition().duration(250)
      .attr('d', d3.linkHorizontal().x((d) => d.y).y((d) => d.x));
    link.exit().transition().duration(250)
      .attr('d', () => {
        const o = { x: source.x, y: source.y };
        return d3.linkHorizontal().x((d) => d.y).y((d) => d.x)({ source: o, target: o });
      }).remove();

    root.eachBefore((d) => { d.x0 = d.x; d.y0 = d.y; });
  }
  update(root);
}

// -------------- Map (Leaflet) --------------
async function renderMap() {
  const data = await fetchJSON('/regions/');
  const map = L.map('map').setView([0, 0], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18,
  }).addTo(map);

  for (const r of data.data) {
    if (r.center_latitude == null || r.center_longitude == null) continue;
    const marker = L.marker([r.center_latitude, r.center_longitude]).addTo(map);
    marker.bindPopup(`<strong>${escapeHtml(r.name)}</strong><br/>${r.region_type || ''}`);
  }
}

// -------------- Search --------------
const searchInput = document.getElementById('search-q');
let searchTimer = null;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 300);
});

async function runSearch() {
  const q = searchInput.value.trim();
  const el = document.getElementById('search-results');
  if (!q) { el.innerHTML = ''; return; }
  const data = await fetchJSON(`/search/?q=${encodeURIComponent(q)}`);
  const groups = [
    ['Entities', data.data.entities, (e) => `<li>${escapeHtml(e.name)} <small>(${e.entity_type || '—'}, ${e.realm || '—'})</small></li>`],
    ['Entity classes', data.data.entity_classes, (c) => `<li>${escapeHtml(c.name)}</li>`],
    ['Cultures', data.data.cultures, (c) => `<li>${escapeHtml(c.name)} <small>(${c.region || ''})</small></li>`],
    ['Sources', data.data.sources, (s) => `<li>${escapeHtml(s.source_name)}</li>`],
  ];
  el.innerHTML = groups.filter(([_, items]) => items.length).map(([label, items, render]) => `
    <div class="group"><h3>${label}</h3><ul>${items.map(render).join('')}</ul></div>
  `).join('') || '<p class="muted">No results.</p>';
}

// -------------- Stats --------------
async function renderStats() {
  const data = (await fetchJSON('/stats/')).data;
  const cards = document.getElementById('stats-cards');
  cards.innerHTML = `
    <div class="stat-card"><div class="n">${data.total_entities}</div><div class="label">Entities</div></div>
    <div class="stat-card"><div class="n">${data.total_extractions}</div><div class="label">Extractions</div></div>
    <div class="stat-card"><div class="n">${data.sources_processed}</div><div class="label">Sources processed</div></div>
    <div class="stat-card"><div class="n">${(data.avg_confidence || 0).toFixed(2)}</div><div class="label">Avg. confidence</div></div>
    <div class="stat-card"><div class="n">${Object.keys(data.by_culture || {}).length}</div><div class="label">Cultures documented</div></div>
  `;
  renderBarChart('chart-by-type', data.by_type);
  renderBarChart('chart-by-alignment', data.by_alignment);
  renderBarChart('chart-by-realm', data.by_realm);
}

function renderBarChart(elId, data) {
  const el = document.getElementById(elId);
  const entries = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  el.innerHTML = entries.map(([k, v]) => `
    <div class="bar">
      <div class="label">${escapeHtml(k)}</div>
      <div class="fill" style="width:${(v / max) * 360}px"></div>
      <div class="count">${v}</div>
    </div>
  `).join('') || '<p class="muted">No data yet.</p>';
}

// -------------- Sources view --------------
async function renderSources() {
  const data = await fetchJSON('/sources/?per_page=100&sort=-ingested_at');
  const counts = { pending: 0, processing: 0, completed: 0, failed: 0 };
  for (const s of data.data) {
    counts[s.ingestion_status] = (counts[s.ingestion_status] || 0) + 1;
  }
  document.getElementById('sources-status').innerHTML = Object.entries(counts)
    .map(([k, v]) => `<div class="chip"><span class="status-pill ${k}">${k}</span> ${v}</div>`)
    .join('');

  const tbody = document.querySelector('#sources-table tbody');
  tbody.innerHTML = data.data.map((s) => `
    <tr>
      <td>${s.id}</td>
      <td>${escapeHtml(s.source_name)}</td>
      <td>${s.source_type}</td>
      <td><span class="status-pill ${s.ingestion_status}">${s.ingestion_status}</span></td>
      <td>${(s.credibility_score || 0).toFixed(2)}</td>
      <td>${s.processed_at ? new Date(s.processed_at).toLocaleString() : '—'}</td>
    </tr>
  `).join('');
}

// -------------- Relationship Graph (Cytoscape) --------------
let cy = null;

const TYPE_COLORS = {
  deity: '#bc8cff',
  ancestor: '#ff8c6e',
  animal_ally: '#57c999',
  plant_spirit: '#55e0b0',
  nature_spirit: '#a6e3ff',
  angelic: '#f0f0f0',
  demonic: '#f85149',
  human_specialist: '#d29922',
  null: '#8b949e',
};

const REL_COLORS = {
  parent_of: '#ff7eb6',
  child_of: '#ff7eb6',
  consort_of: '#ffd36e',
  sibling_of: '#a4e6ff',
  allied_with: '#57c999',
  enemy_of: '#f85149',
  teacher_of: '#bc8cff',
  student_of: '#bc8cff',
  serves: '#d29922',
  ruled_by: '#d29922',
  aspect_of: '#88d3ff',
  manifests_as: '#ff9bf0',
  syncretized_with: '#c8e89b',
  created_by: '#e0c060',
  co_occurs_with: '#3a4555',
  associated_with: '#485664',
};

async function initGraphView() {
  // populate culture filter from the current entity data
  try {
    const cres = await fetchJSON('/cultures/?per_page=100&sort=name');
    const sel = document.getElementById('graph-culture');
    for (const c of cres.data) {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = c.name;
      sel.appendChild(opt);
    }
  } catch (e) { console.warn('culture list failed', e); }
  document.getElementById('graph-refresh').addEventListener('click', renderGraph);
  renderGraph();
}

async function renderGraph() {
  const culture = document.getElementById('graph-culture').value;
  const relType = document.getElementById('graph-rel-type').value;
  const maxNodes = document.getElementById('graph-max-nodes').value;

  const info = document.getElementById('graph-info');
  info.textContent = 'Loading…';

  const params = new URLSearchParams();
  if (culture) params.set('culture', culture);
  if (relType) params.set('rel_type', relType);
  params.set('max_nodes', maxNodes);

  const res = await fetchJSON(`/graph/?${params}`);
  const { nodes, edges, stats } = res.data;
  info.textContent = `${stats.node_count} nodes · ${stats.edge_count} edges · ${stats.semantic_edges} semantic · ${stats.weak_edges} weak`;

  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById('cy'),
    elements: { nodes, edges },
    style: [
      {
        selector: 'node',
        style: {
          'background-color': (ele) => TYPE_COLORS[ele.data('entity_type')] || TYPE_COLORS.null,
          'label': 'data(label)',
          'color': '#e6edf3',
          'font-size': '10px',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': '4px',
          'width': (ele) => 10 + (ele.data('confidence') || 0) * 20,
          'height': (ele) => 10 + (ele.data('confidence') || 0) * 20,
          'border-width': 1,
          'border-color': '#30363d',
        },
      },
      {
        selector: 'edge',
        style: {
          'width': (ele) => ele.data('is_semantic') ? 2 : 0.6,
          'line-color': (ele) => REL_COLORS[ele.data('rel_type')] || '#30363d',
          'target-arrow-color': (ele) => REL_COLORS[ele.data('rel_type')] || '#30363d',
          'target-arrow-shape': (ele) => ele.data('is_semantic') ? 'triangle' : 'none',
          'curve-style': 'bezier',
          'opacity': (ele) => ele.data('is_semantic') ? 0.9 : 0.35,
          'label': (ele) => ele.data('is_semantic') ? ele.data('rel_type') : '',
          'font-size': '8px',
          'color': '#8b949e',
          'text-background-color': '#0e1117',
          'text-background-opacity': 0.8,
          'text-background-padding': '2px',
        },
      },
      {
        selector: 'node:selected',
        style: { 'border-width': 3, 'border-color': '#58a6ff' },
      },
    ],
    layout: {
      name: 'cose',
      animate: false,
      nodeRepulsion: 5000,
      idealEdgeLength: 80,
      edgeElasticity: 80,
      gravity: 0.25,
      numIter: 1200,
    },
    wheelSensitivity: 0.2,
    minZoom: 0.1,
    maxZoom: 3,
  });

  cy.on('tap', 'node', (e) => {
    const id = e.target.data('id');
    // switch to Entities view with this entity selected
    document.querySelector('.nav button[data-view="entities"]').click();
    setTimeout(() => renderEntityDetail(id), 50);
  });
}

// -------------- Utilities --------------
function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Initial load
renderEntities();
