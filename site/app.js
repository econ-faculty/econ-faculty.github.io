/* Econ Faculty — client-side rendering. Data: data.js (index) + people/<university>.json (details). */
(function () {
  "use strict";
  const CONFIG = { repoUrl: "https://github.com/econ-faculty/econ-faculty.github.io", pageSize: 100 };
  const D = window.EF;
  const app = document.getElementById("app");
  if (!D) { app.innerHTML = `<p class="empty">data.js not found — run python scripts/build.py</p>`; return; }
  document.getElementById("generated").textContent = D.generated;
  document.getElementById("repo-link").href = CONFIG.repoUrl;

  const UT_LABEL = { economics: "Economics", business: "Business School", public_policy: "Public Policy",
    ag_resource_econ: "Agricultural & Resource Econ", environment: "Environment", law: "Law", public_health: "Public Health", other: "Other" };
  const U = D.universities;
  const P = D.people.map((r) => Object.fromEntries(D.cols.map((c, i) => [c, r[i]])));
  const SUFFIX = /^(jr\.?|sr\.?|ii|iii|iv)$/i;
  for (const p of P) {
    const toks = p.name.replace(/\(.*?\)|".*?"/g, " ").split(/\s+/).filter((t) => t && !SUFFIX.test(t.replace(/,$/, "")));
    p.sur = (toks[toks.length - 1] || p.name).normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  const BYID = new Map(P.map((p) => [p.id, p]));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const opt = (v, label, sel) => `<option value="${esc(v)}" ${String(sel) === String(v) ? "selected" : ""}>${esc(label)}</option>`;
  const link = (url, text) => url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)}</a>` : "";
  const uniq = (a) => [...new Set(a)];
  const rankCls = (r) => "rk-" + D.ranks[r].split(" ")[0];

  const cache = new Map();
  const loadUni = (uid) => {
    if (!cache.has(uid)) cache.set(uid, fetch(`people/${uid}.json`).then((r) => r.json()).catch(() => ({})));
    return cache.get(uid);
  };

  // ---------------------------------------------------------------- routing
  function route() {
    const h = location.hash.replace(/^#/, "") || "/";
    const [path, qs] = h.split("?");
    return { parts: path.split("/").filter(Boolean), q: new URLSearchParams(qs || "") };
  }
  function setQuery(base, obj) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(obj)) if (v !== "" && v != null && v !== false && !(Array.isArray(v) && !v.length)) q.set(k, Array.isArray(v) ? v.join(",") : v);
    const s = q.toString();
    history.replaceState(null, "", "#" + base + (s ? "?" + s : ""));
  }
  function setNav(v) { document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === v)); }
  function render() {
    const { parts, q } = route();
    const v = parts[0] || "";
    if (v === "p" && parts[1]) { setNav("people"); renderProfile(decodeURIComponent(parts[1])); }
    else if (v === "institutions") { setNav("institutions"); renderInstitutions(); }
    else if (v === "fields") { setNav("fields"); renderFields(); }
    else if (v === "about") { setNav("about"); renderAbout(); }
    else { setNav("people"); renderPeople(q); }
  }
  window.addEventListener("hashchange", render);
  function bindSearch(id, cb) {
    const el = document.getElementById(id); let t;
    el.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => {
      const pos = el.selectionStart; cb(el.value.trim()); const n = document.getElementById(id); if (n) { n.focus(); n.setSelectionRange(pos, pos); }
    }, 200); });
  }

  // ---------------------------------------------------------------- people
  const S = {};
  function readS(q) {
    S.q = q.get("q") || ""; S.region = q.get("region") || ""; S.country = q.get("country") || ""; S.uni = q.get("uni") || "";
    S.ut = q.get("ut") || ""; S.pf = q.get("field") || ""; S.rank = q.get("rank") || ""; S.page = +(q.get("p") || 1); S.sort = q.get("sort") || "";
    S.fields = (q.get("f") || "").split(",").filter((x) => x !== "").map(Number);
  }
  function match(p, ign) {
    const u = U[p.uni];
    if (ign !== "region" && S.region && u.region !== S.region) return false;
    if (ign !== "country" && S.country && u.country !== S.country) return false;
    if (ign !== "uni" && S.uni && u.id !== S.uni) return false;
    if (ign !== "ut" && S.ut !== "" && p.unit_type !== +S.ut) return false;
    if (ign !== "pf" && S.pf) {
      const lab = D.pfields[p.pfield];
      if (S.pf.startsWith("g:") ? lab.split(":")[0] !== S.pf.slice(2) : lab !== D.pfields[+S.pf]) return false;
    }
    if (ign !== "rank" && S.rank !== "" && p.rank !== +S.rank) return false;
    if (ign !== "fields" && S.fields.length) for (const f of S.fields) if (!p.fields.includes(f)) return false;
    if (S.q) {
      const hay = (p.name + " " + p.unit + " " + p.area + " " + D.pfields[p.pfield] + " " + p.phd + " " + u.short + " " + u.name + " " + p.fields.map((f) => D.fields[f]).join(" ")).toLowerCase();
      if (!S.q.toLowerCase().split(/\s+/).every((t) => hay.includes(t))) return false;
    }
    return true;
  }
  function renderPeople(q) {
    readS(q);
    const list = P.filter((p) => match(p)).sort(S.sort === "first" ? ((a, b) => a.name.localeCompare(b.name, "en", { sensitivity: "base" })) : ((a, b) => a.sur.localeCompare(b.sur, "en", { sensitivity: "base" }) || a.name.localeCompare(b.name, "en", { sensitivity: "base" })));
    const pages = Math.max(1, Math.ceil(list.length / CONFIG.pageSize));
    S.page = Math.min(Math.max(1, S.page), pages);
    const shown = list.slice((S.page - 1) * CONFIG.pageSize, S.page * CONFIG.pageSize);
    const count = (fn) => P.filter(fn).length;
    const regions = uniq(U.map((u) => u.region));
    const countries = uniq(U.filter((u) => !S.region || u.region === S.region).map((u) => u.country));
    const unis = U.filter((u) => u.n && (!S.region || u.region === S.region) && (!S.country || u.country === S.country));
    const pfc = {}; for (const p of P) if (match(p, "pf")) pfc[p.pfield] = (pfc[p.pfield] || 0) + 1;
    const groups = uniq(D.pfields.map((x) => x.split(":")[0]));
    const fieldOpts = groups.map((g) => {
      const items = D.pfields.map((x, i) => [x, i]).filter(([x, i]) => x.split(":")[0] === g && pfc[i]);
      if (!items.length) return "";
      const tot = items.reduce((a, [, i]) => a + pfc[i], 0);
      const subs = items.filter(([x]) => x.includes(":"));
      return `<optgroup label="${esc(g)}">${subs.length > 1 || !subs.length ? opt("g:" + g, `${g} — all (${tot})`, S.pf) : ""}${items.map(([x, i]) => opt(i, `${x.includes(":") ? x.split(": ")[1] : x} (${pfc[i]})`, S.pf)).join("")}</optgroup>`;
    }).join("");
    const fc = {}; for (const p of P) if (match(p, "fields")) for (const f of p.fields) fc[f] = (fc[f] || 0) + 1;
    const withPhd = list.filter((p) => p.phd).length;

    app.innerHTML = `
      <p class="intro">An open directory of tenure-line faculty doing research in <b>economics and business</b> at leading universities — economics departments, business schools, public policy schools, agricultural &amp; resource economics, and economists in other units. Search by region, institution, unit, field or PhD institution.</p>
      <section class="stats">
        <div class="stat"><div class="n">${list.length.toLocaleString()}</div><div class="l">faculty${list.length !== P.length ? ` (of ${P.length.toLocaleString()})` : ""}</div>
          <div class="sub">${D.ranks.map((r, i) => `${r.replace(" Professor", "")} ${list.filter((p) => p.rank === i).length}`).join(" · ")}</div></div>
        <div class="stat"><div class="n">${uniq(list.map((p) => p.uni)).length}</div><div class="l">institutions</div><div class="sub">${uniq(list.map((p) => U[p.uni].country)).length} countries</div></div>
        <div class="stat"><div class="n">${list.filter((p) => p.unit_type === 0).length.toLocaleString()}</div><div class="l">in economics departments</div><div class="sub">${list.filter((p) => p.unit_type === 1).length.toLocaleString()} in business schools</div></div>
        <div class="stat"><div class="n">${list.length ? Math.round(100 * withPhd / list.length) : 0}%</div><div class="l">with PhD information</div><div class="sub">more details being added</div></div>
      </section>
      <section class="controls">
        <div class="row">
          <input id="q" type="search" placeholder="Search name, unit, field, PhD institution…" value="${esc(S.q)}" autocomplete="off">
          <select id="region"><option value="">All regions</option>${regions.map((r) => opt(r, `${r} (${count((p) => U[p.uni].region === r && match(p, "region"))})`, S.region)).join("")}</select>
          <select id="country"><option value="">All countries</option>${countries.map((c) => opt(c, c, S.country)).join("")}</select>
          <select id="uni"><option value="">All institutions</option>${unis.map((u) => opt(u.id, `${u.short} (${count((p) => U[p.uni].id === u.id && match(p, "uni"))})`, S.uni)).join("")}</select>
        </div>
        <div class="row">
          <select id="ut"><option value="">All unit types</option>${D.unit_types.map((t, i) => opt(i, `${UT_LABEL[t]} (${count((p) => p.unit_type === i && match(p, "ut"))})`, S.ut)).join("")}</select>
          <select id="field"><option value="">All fields</option>${fieldOpts}</select>
          <select id="rank"><option value="">All ranks</option>${D.ranks.map((r, i) => opt(i, `${r} (${count((p) => p.rank === i && match(p, "rank"))})`, S.rank)).join("")}</select>
          <select id="sort">${opt("", "Sort: last name A–Z", S.sort)}${opt("first", "Sort: first name A–Z", S.sort)}</select>
          <button class="btn" id="reset" type="button">Reset</button>
        </div>
        <div class="row"><span class="lbl">Topics</span>
          ${D.fields.map((f, i) => [f, i]).filter(([, i]) => fc[i] || S.fields.includes(i)).sort((a, b) => (fc[b[1]] || 0) - (fc[a[1]] || 0))
            .map(([f, i]) => `<button class="chip ${S.fields.includes(i) ? "active" : ""}" data-f="${i}">${esc(f)}<span class="c">${fc[i] || 0}</span></button>`).join("")}
        </div>
      </section>
      <p class="count">${list.length.toLocaleString()} results · page ${S.page} of ${pages}</p>
      <section class="tbl-wrap"><table>
        <thead><tr><th>Name</th><th>Rank</th><th>Institution</th><th>Unit</th><th>Field</th><th>PhD</th></tr></thead>
        <tbody>${shown.map((p) => `<tr class="clk" data-id="${esc(p.id)}">
          <td><a href="#/p/${encodeURIComponent(p.id)}"><b>${esc(p.name)}</b></a></td>
          <td><span class="badge ${rankCls(p.rank)}">${esc(D.ranks[p.rank].replace(" Professor", ""))}</span></td>
          <td>${esc(U[p.uni].short)}</td>
          <td>${esc(p.unit)}${p.area ? `<div class="small">${esc(p.area)}</div>` : ""}</td>
          <td><span class="tag pf">${esc(D.pfields[p.pfield])}</span></td>
          <td class="small">${esc(p.phd)}${p.phd_year ? " " + p.phd_year : ""}</td></tr>`).join("") || `<tr><td colspan="6" class="empty">No matches.</td></tr>`}
        </tbody></table></section>
      ${pages > 1 ? `<div class="pager">${S.page > 1 ? `<button class="btn" data-pg="${S.page - 1}">← Prev</button>` : ""}<span class="small">Page ${S.page} / ${pages}</span>${S.page < pages ? `<button class="btn" data-pg="${S.page + 1}">Next →</button>` : ""}</div>` : ""}`;

    const push = (page) => setQuery("/", { q: S.q, region: S.region, country: S.country, uni: S.uni, ut: S.ut, field: S.pf, rank: S.rank, f: S.fields, sort: S.sort, p: page > 1 ? page : "" });
    const rer = (page = 1) => { push(page); renderPeople(route().q); };
    bindSearch("q", (v) => { S.q = v; rer(); });
    for (const k of ["region", "country", "uni", "ut", "field", "rank", "sort"]) document.getElementById(k).onchange = (e) => {
      S[k === "field" ? "pf" : k] = e.target.value;
      if (k === "region") { S.country = ""; S.uni = ""; } if (k === "country") S.uni = ""; if (k === "ut") S.pf = "";
      rer();
    };
    document.getElementById("reset").onclick = () => { history.replaceState(null, "", "#/"); renderPeople(new URLSearchParams()); };
    app.querySelectorAll("[data-f]").forEach((b) => b.onclick = () => { const f = +b.dataset.f; S.fields = S.fields.includes(f) ? S.fields.filter((x) => x !== f) : [...S.fields, f]; rer(); });
    app.querySelectorAll("[data-pg]").forEach((b) => b.onclick = () => { rer(+b.dataset.pg); window.scrollTo(0, 0); });
    app.querySelectorAll("tr.clk").forEach((tr) => tr.onclick = (e) => { if (!e.target.closest("a")) location.hash = "#/p/" + encodeURIComponent(tr.dataset.id); });
  }

  // ---------------------------------------------------------------- profile
  function renderProfile(id) {
    const p = BYID.get(id);
    requestAnimationFrame(() => window.scrollTo(0, 0));
    if (!p) { app.innerHTML = `<p class="crumb"><a href="#/">← Back</a></p><p class="empty">Not found.</p>`; return; }
    const u = U[p.uni];
    app.innerHTML = `<p class="crumb"><a href="#/">People</a> / <a href="#/?uni=${u.id}">${esc(u.short)}</a> / ${esc(p.name)}</p><p class="small">Loading…</p>`;
    loadUni(u.id).then((det) => {
      const r = det[id] || {};
      const edu = [["PhD", r.phd_institution, r.phd_year, r.phd_field], ["Master's", r.ma_institution, r.ma_year, r.ma_field], ["Bachelor's", r.ba_institution, r.ba_year, r.ba_field]]
        .filter((e) => e[1]);
      const links = [link(r.homepage_url, "Homepage ↗"), link(r.profile_url, "Faculty profile ↗"), link(r.cv_url, "CV ↗"),
        link(r.google_scholar_url, "Google Scholar ↗"), r.orcid ? link(String(r.orcid).startsWith("http") ? r.orcid : "https://orcid.org/" + r.orcid, "ORCID ↗") : ""].filter(Boolean).join("");
      const kv = (k, v) => v ? `<dt>${k}</dt><dd>${esc(v)}</dd>` : "";
      app.innerHTML = `
        <p class="crumb"><a href="#/">People</a> / <a href="#/?uni=${u.id}">${esc(u.short)}</a> / ${esc(p.name)}</p>
        <section class="profile-h">
          <h1>${esc(p.name)}</h1>
          <div class="ttl">${esc(r.title || D.ranks[p.rank])}</div>
          <div class="ttl" style="margin-top:-6px">${esc(r.unit || "")}${r.area ? " · " + esc(r.area) : ""} · ${esc(u.name)}</div>
          <div><span class="badge ${rankCls(p.rank)}">${esc(D.ranks[p.rank])}</span> <span class="badge plain">${esc(UT_LABEL[D.unit_types[p.unit_type]])}</span>
            <a class="badge pfb" href="#/?field=${p.pfield}">${esc(D.pfields[p.pfield])}</a>
            <span class="badge plain">${esc(u.country)}</span></div>
          <div style="margin-top:10px">${p.fields.map((f) => `<a class="tag" href="#/?f=${f}">${esc(D.fields[f])}</a>`).join("")}</div>
          ${links ? `<div class="links">${links}</div>` : ""}
        </section>
        <div class="grid2">
          <div>
            <section class="box"><h3>Education</h3>
              ${edu.length ? `<ul class="timeline">${edu.map(([d, s, y, f]) => `<li><span class="deg">${d}</span><span class="yr">${y || ""}</span><span class="fd">${esc(s)}${f ? " · " + esc(f) : ""}</span></li>`).join("")}</ul>` : `<p class="small">Not yet available.</p>`}
              ${r.education_raw && !edu.length ? `<p class="small">${esc(r.education_raw)}</p>` : ""}
              ${r.phd_advisors ? `<p class="small" style="margin-top:6px">PhD advisor(s) / committee: ${esc(r.phd_advisors)}</p>` : ""}
            </section>
            <section class="box"><h3>Appointment</h3><dl class="kv">
              ${kv("Title", r.title)}${kv("Unit", r.unit)}${kv("Area", r.area)}${kv("Also in", r.other_units)}${kv("Joined", r.year_joined)}${kv("Current rank since", r.year_current_rank)}${kv("First job after PhD", r.first_job_after_phd)}
            </dl>
            ${r.prior_positions ? `<h3 style="margin-top:12px">Career</h3><ul class="career">${String(r.prior_positions).split(";").filter((x) => x.trim()).map((x) => `<li>${esc(x.trim())}</li>`).join("")}</ul>` : ""}
            </section>
          </div>
          <div>
            <section class="box"><h3>Research fields</h3>
              ${r.fields_raw ? `<p>${esc(r.fields_raw)}</p>` : `<p class="small">Not listed.</p>`}</section>
            <section class="box"><h3>Publications &amp; working papers</h3><div class="coming">Coming soon.</div></section>
            <section class="box"><h3>Source</h3><p class="small">${r.source_url ? link(r.source_url, "University directory") + " · " : ""}${r.detail_source ? "Details from " + esc(r.detail_source) + (r.cv_date ? " (" + esc(r.cv_date) + ")" : "") + " · " : ""}${r.notes ? esc(r.notes) + " · " : ""}
              <a href="${CONFIG.repoUrl}/edit/main/data/faculty/${u.id}.json" target="_blank" rel="noopener">Suggest a correction</a></p></section>
          </div>
        </div>`;
    });
  }

  // ---------------------------------------------------------------- institutions
  function renderInstitutions() {
    const regions = uniq(U.map((u) => u.region));
    app.innerHTML = `<p class="intro">Institutions currently covered. The directory is growing — more universities will be added over time.</p>` +
      regions.map((rg) => `<div class="group-h"><span class="nm">${esc(rg)}</span><span class="n">${U.filter((u) => u.region === rg).reduce((a, u) => a + u.n, 0).toLocaleString()} faculty</span></div>
        <section class="tbl-wrap"><table><thead><tr><th>Institution</th><th>Country</th><th class="num">Total</th>
          ${["economics", "business", "public_policy", "ag_resource_econ"].map((t) => `<th class="num">${UT_LABEL[t]}</th>`).join("")}<th class="num">Other</th></tr></thead><tbody>
          ${U.filter((u) => u.region === rg).map((u) => {
            const b = u.by_unit_type || {};
            const other = Object.entries(b).filter(([k]) => !["economics", "business", "public_policy", "ag_resource_econ"].includes(k)).reduce((a, [, v]) => a + v, 0);
            return `<tr class="clk" data-uni="${u.id}"><td><b>${esc(u.name)}</b> <span class="small">${esc(u.short)}</span></td><td>${esc(u.country)}</td><td class="num">${u.n || "—"}</td>
              ${["economics", "business", "public_policy", "ag_resource_econ"].map((t) => `<td class="num">${b[t] || ""}</td>`).join("")}<td class="num">${other || ""}</td></tr>`;
          }).join("")}</tbody></table></section>`).join("");
    app.querySelectorAll("tr[data-uni]").forEach((tr) => tr.onclick = () => { location.hash = "#/?uni=" + tr.dataset.uni; });
  }

  // ---------------------------------------------------------------- fields
  function renderFields() {
    const c = {}; for (const p of P) c[p.pfield] = (c[p.pfield] || 0) + 1;
    const t = {}; for (const p of P) for (const f of p.fields) t[f] = (t[f] || 0) + 1;
    const groups = uniq(D.pfields.map((x) => x.split(":")[0]));
    app.innerHTML = `<p class="intro">Each faculty member is assigned one <b>primary field</b>, organized by school type: economics subfields; business-school areas (with sub-areas for large ones such as Finance, Marketing, Management, Operations &amp; IS); public policy; law; public health. Below that, <b>topics</b> are the (possibly multiple) research interests listed on each profile.</p>` +
      groups.map((g) => {
        const items = D.pfields.map((x, i) => [x, i]).filter(([x]) => x.split(":")[0] === g);
        const tot = items.reduce((a, [, i]) => a + (c[i] || 0), 0);
        return `<div class="group-h"><a class="nm" href="#/?field=g:${encodeURIComponent(g)}">${esc(g)}</a><span class="n">${tot.toLocaleString()} faculty</span></div><div class="fgrid">
          ${items.map(([x, i]) => `<a class="fcell" href="#/?field=${i}"><span>${esc(x.includes(":") ? x.split(": ")[1] : x)}</span><span class="c">${(c[i] || 0).toLocaleString()}</span></a>`).join("")}</div>`;
      }).join("") +
      `<div class="group-h"><span class="nm">Topics</span></div><div class="fgrid">${D.fields.map((f, i) => [f, i]).filter(([, i]) => t[i]).sort((a, b) => t[b[1]] - t[a[1]])
        .map(([f, i]) => `<a class="fcell" href="#/?f=${i}"><span>${esc(f)}</span><span class="c">${t[i].toLocaleString()}</span></a>`).join("")}</div>`;
  }

  // ---------------------------------------------------------------- about
  function renderAbout() {
    app.innerHTML = `<article class="prose">
      <h2>About</h2>
      <p><b>Econ Faculty</b> is an open, community-maintained directory of tenure-line faculty who do research in economics and business at leading universities around the world. It aims to make it easy to find scholars by region, institution, unit and research field, and — in later releases — to browse their publications and working papers.</p>
      <h2>Coverage</h2>
      <ul>
        <li><b>Institutions (first release):</b> the top-10 US economics departments' universities (Harvard, MIT, Stanford, Berkeley, Chicago, Princeton, Yale, Northwestern, Columbia, Penn); Oxford, Cambridge, LSE, London Business School and Warwick in the UK; HKU, CUHK and HKUST in Hong Kong; NUS, NTU and SMU in Singapore.</li>
        <li><b>Units:</b> economics departments; all tenure-line faculty in business schools (finance, accounting, marketing, management, strategy, organizational behavior, operations, etc.); economists and management scholars in public policy schools; agricultural &amp; resource economics departments; and economists in environment, law, public health and other units.</li>
        <li><b>Ranks:</b> Assistant, Associate and Full Professors (UK Lecturer → Assistant, Senior Lecturer/Reader → Associate). Emeriti, visiting, adjunct, clinical, practice and teaching-track positions are excluded.</li>
      </ul>
      <h2>Data</h2>
      <p>Information is compiled from public university directories, faculty profile pages and personal websites. Research fields are mapped to a standard taxonomy from the interests each person lists. Education details are being added progressively. We do not collect emails, phone numbers or photos.</p>
      <h2>Corrections &amp; removal</h2>
      <p>Each institution's data lives in <code>data/faculty/&lt;institution&gt;.json</code> in the <a href="${CONFIG.repoUrl}" target="_blank" rel="noopener">GitHub repository</a>. Use “Suggest a correction” on any profile, or open an issue. Faculty who wish to be removed can open an issue and we will remove the entry.</p>
    </article>`;
  }

  render();
})();
