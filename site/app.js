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

  const V = D.v ? "?v=" + D.v : "";  // build version: busts stale browser caches after each deploy
  const getJSON = (url) => fetch(url + V).then((r) => { if (!r.ok) throw new Error(r.status + " " + url); return r.json(); });
  const cache = new Map();
  const loadUni = (uid) => {
    if (!cache.has(uid)) cache.set(uid, getJSON(`people/${uid}.json`).catch(() => ({})));
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
    else if (v === "papers") { setNav("papers"); renderPapers(q); }
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
    S.ut = q.get("ut") || ""; S.pf = q.get("field") || ""; S.rank = q.get("rank") || ""; S.page = +(q.get("p") || 1); S.sort = q.get("sort") || ""; S.jr = q.get("jr") || "";
    S.fields = (q.get("f") || "").split(",").filter((x) => x !== "").map(Number);
  }
  function match(p, ign) {
    const u = U[p.uni];
    if (ign !== "region" && S.region && u.region !== S.region) return false;
    if (ign !== "country" && S.country && u.country !== S.country) return false;
    if (ign !== "uni" && S.uni && u.id !== S.uni) return false;
    if (ign !== "ut" && S.ut !== "" && p.unit_type !== +S.ut) return false;
    if (ign !== "pf" && S.pf) {
      const ok = S.pf.startsWith("g:") ? p.pfield.some((i) => D.pfields[i].split(":")[0] === S.pf.slice(2)) : p.pfield.includes(+S.pf);
      if (!ok) return false;
    }
    if (ign !== "rank" && S.rank !== "" && p.rank !== +S.rank) return false;
    if (ign !== "jr" && S.jr !== "") {
      const ok = S.jr.startsWith("t:") ? p.jr.some((j) => D.journals[j][1] === +S.jr.slice(2)) : p.jr.includes(+S.jr);
      if (!ok) return false;
    }
    if (ign !== "fields" && S.fields.length) for (const f of S.fields) if (!p.fields.includes(f)) return false;
    if (S.q) {
      const hay = (p.name + " " + p.unit + " " + p.area + " " + p.pfield.map((i) => D.pfields[i]).join(" ") + " " + p.phd + " " + u.short + " " + u.name + " " + p.fields.map((f) => D.fields[f]).join(" ")).toLowerCase();
      if (!S.q.toLowerCase().split(/\s+/).every((t) => hay.includes(t))) return false;
    }
    return true;
  }
  function renderPeople(q) {
    readS(q);
    const bySur = (a, b) => a.sur.localeCompare(b.sur, "en", { sensitivity: "base" }) || a.name.localeCompare(b.name, "en", { sensitivity: "base" });
    const SORTS = { first: (a, b) => a.name.localeCompare(b.name, "en", { sensitivity: "base" }), top5: (a, b) => b.np[3] - a.np[3] || b.np[4] - a.np[4] || bySur(a, b),
      lead: (a, b) => b.np[4] - a.np[4] || b.np[3] - a.np[3] || bySur(a, b), pubs: (a, b) => b.np[0] - a.np[0] || bySur(a, b) };
    const list = P.filter((p) => match(p)).sort(SORTS[S.sort] || bySur);
    const pages = Math.max(1, Math.ceil(list.length / CONFIG.pageSize));
    S.page = Math.min(Math.max(1, S.page), pages);
    const shown = list.slice((S.page - 1) * CONFIG.pageSize, S.page * CONFIG.pageSize);
    const count = (fn) => P.filter(fn).length;
    const regions = uniq(U.map((u) => u.region));
    const countries = uniq(U.filter((u) => !S.region || u.region === S.region).map((u) => u.country));
    const unis = U.filter((u) => u.n && (!S.region || u.region === S.region) && (!S.country || u.country === S.country));
    const pfc = {}; for (const p of P) if (match(p, "pf")) for (const i of p.pfield) pfc[i] = (pfc[i] || 0) + 1;
    const groups = uniq(D.pfields.map((x) => x.split(":")[0]));
    const fieldOpts = groups.map((g) => {
      const items = D.pfields.map((x, i) => [x, i]).filter(([x, i]) => x.split(":")[0] === g && pfc[i]);
      if (!items.length) return "";
      const tot = P.filter((p) => match(p, "pf") && p.pfield.some((i) => D.pfields[i].split(":")[0] === g)).length;
      const subs = items.filter(([x]) => x.includes(":"));
      return `<optgroup label="${esc(g)}">${subs.length > 1 || !subs.length ? opt("g:" + g, `${g} — all (${tot})`, S.pf) : ""}${items.map(([x, i]) => opt(i, `${x.includes(":") ? x.split(": ")[1] : x} (${pfc[i]})`, S.pf)).join("")}</optgroup>`;
    }).join("");
    const fc = {}; for (const p of P) if (match(p, "fields")) for (const f of p.fields) fc[f] = (fc[f] || 0) + 1;
    const withPhd = list.filter((p) => p.phd).length;
    const jrOpts = journalOpts(S.jr);

    app.innerHTML = `
      <p class="intro">An open directory of tenure-line faculty doing research in <b>economics and business</b> at leading universities — economics departments, business schools, public policy schools, agricultural &amp; resource economics, and economists in other units. Search by region, institution, unit, field, PhD institution or the journals people publish in — or search papers directly in the <a href="#/papers">Papers</a> tab.</p>
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
          <select id="jr"><option value="">Published in: any journal</option>${jrOpts}</select>
          <select id="sort">${opt("", "Sort: last name A–Z", S.sort)}${opt("first", "Sort: first name A–Z", S.sort)}${opt("top5", "Sort: most Top-5 econ papers", S.sort)}${opt("lead", "Sort: most leading-journal papers", S.sort)}${opt("pubs", "Sort: most publications", S.sort)}</select>
          <button class="btn" id="reset" type="button">Reset</button>
        </div>
      </section>
      <p class="count">${list.length.toLocaleString()} results · page ${S.page} of ${pages}</p>
      <section class="tbl-wrap"><table>
        <thead><tr><th>Name</th><th>Rank</th><th>Institution</th><th>Unit</th><th>Field</th><th>PhD</th><th title="Publications in leading journals (Top-5 econ in brackets)">Leading pubs</th></tr></thead>
        <tbody>${shown.map((p) => `<tr class="clk" data-id="${esc(p.id)}">
          <td><a href="#/p/${encodeURIComponent(p.id)}"><b>${esc(p.name)}</b></a></td>
          <td><span class="badge ${rankCls(p.rank)}">${esc(D.ranks[p.rank].replace(" Professor", ""))}</span></td>
          <td>${esc(U[p.uni].short)}</td>
          <td>${esc(p.unit)}${p.area ? `<div class="small">${esc(p.area)}</div>` : ""}</td>
          <td>${p.pfield.map((i) => `<span class="tag pf">${esc(D.pfields[i])}</span>`).join("")}</td>
          <td class="small">${esc(p.phd)}${p.phd_year ? " " + p.phd_year : ""}</td>
          <td class="small num">${p.np[4] ? p.np[4] + (p.np[3] ? ` <span class="muted">(${p.np[3]})</span>` : "") : ""}</td></tr>`).join("") || `<tr><td colspan="7" class="empty">No matches.</td></tr>`}
        </tbody></table></section>
      ${pages > 1 ? `<div class="pager">${S.page > 1 ? `<button class="btn" data-pg="${S.page - 1}">← Prev</button>` : ""}<span class="small">Page ${S.page} / ${pages}</span>${S.page < pages ? `<button class="btn" data-pg="${S.page + 1}">Next →</button>` : ""}</div>` : ""}`;

    const push = (page) => setQuery("/", { q: S.q, region: S.region, country: S.country, uni: S.uni, ut: S.ut, field: S.pf, rank: S.rank, jr: S.jr, f: S.fields, sort: S.sort, p: page > 1 ? page : "" });
    const rer = (page = 1) => { push(page); renderPeople(route().q); };
    bindSearch("q", (v) => { S.q = v; rer(); });
    for (const k of ["region", "country", "uni", "ut", "field", "rank", "jr", "sort"]) document.getElementById(k).onchange = (e) => {
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
            ${p.pfield.map((i) => `<a class="badge pfb" href="#/?field=${i}">${esc(D.pfields[i])}</a>`).join(" ")}
            <span class="badge plain">${esc(u.country)}</span></div>
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
            <section class="box"><h3>Publications &amp; working papers${r.n_papers ? ` <span class="small">(${r.n_papers})</span>` : ""}</h3><div id="pubs">${r.n_papers ? `<p class="small">Loading…</p>` : `<div class="coming">Coming soon.</div>`}</div></section>
            <section class="box"><h3>Source</h3><p class="small">${r.source_url ? link(r.source_url, "University directory") + " · " : ""}${r.detail_source ? "Details from " + esc(r.detail_source) + (r.cv_date ? " (" + esc(r.cv_date) + ")" : "") + " · " : ""}${r.notes ? esc(r.notes) + " · " : ""}
              <a href="${CONFIG.repoUrl}/edit/main/data/faculty/${u.id}.json" target="_blank" rel="noopener">Suggest a correction</a></p></section>
          </div>
        </div>`;
      if (r.n_papers) getJSON(`pubs/${encodeURIComponent(id)}.json`).then((ps) => paperList(ps, document.getElementById("pubs")))
        .catch((e) => { console.error(e); const el = document.getElementById("pubs"); if (el) el.innerHTML = `<p class="empty">Could not load the paper list — please reload the page (Ctrl+F5).</p>`; });
    });
  }


  // ---------------------------------------------------------------- papers (shared formatting)
  const CAT = [["pub", "Publications"], ["rr", "Revise & resubmit"], ["wp", "Working papers"]];
  const authorsTxt = (a) => !a || !a.length ? "" : a.length === 1 ? a[0] : a.length === 2 ? `${a[0]} and ${a[1]}` : `${a.slice(0, -1).join(", ")}, and ${a[a.length - 1]}`;
  const scholar = (t) => "https://scholar.google.com/scholar?q=" + encodeURIComponent('"' + t + '"');
  // journal topic badge; colour by broad group (econ / business / other disciplines)
  const TOPIC_GRP = (i) => { const x = D.jtopics[i]; return ["Finance", "Real Estate", "Accounting", "Management & Strategy", "Organizational Behavior", "Entrepreneurship & Innovation", "Marketing", "Operations & IS", "Management Practice"].includes(x) ? 1
    : ["Psychology", "Multidisciplinary Science", "Political Science", "Sociology", "Statistics"].includes(x) ? 2 : 0; };
  const tierBadge = (r, c) => r != null && r >= 0 && c !== "wp" && c !== 2 && D.journals[r][2] != null ? ` <span class="tier g${TOPIC_GRP(D.journals[r][2])}">${esc(D.jtopics[D.journals[r][2]])}</span>` : "";
  const titleLink = (t, l, lt) => l ? `<a href="${esc(l)}" target="_blank" rel="noopener" title="${lt === "wp" ? "Working-paper version" : "Published version"}">${esc(t)}</a>`
    : `<a class="srch" href="${scholar(t)}" target="_blank" rel="noopener" title="Search Google Scholar">${esc(t)}</a>`;
  function journalOpts(sel) {
    return D.tiers.map(([, lab], t) => `<optgroup label="${esc(lab)}">${opt("t:" + t, `Any ${lab.toLowerCase()} journal`, sel)}${D.journals.map((j, i) => [j, i]).filter(([j]) => j[1] === t).map(([j, i]) => opt(i, j[0], sel)).join("")}</optgroup>`).join("");
  }
  function cite(q) {  // AEA style: Authors. Year. Journal Vol (Issue): pages.  (title on its own line, linked)
    const vip = q.v ? ` ${esc(q.v)}${q.i ? ` (${esc(q.i)})` : ""}${q.p ? `: ${esc(q.p)}` : ""}` : q.p ? `, ${esc(q.p)}` : "";
    const where = q.c === "rr" ? (q.j ? `Revise &amp; resubmit, <i>${esc(q.j)}</i>` : "Revise &amp; resubmit")
      : q.c === "wp" ? (q.j ? esc(q.j) : "Working paper")
      : q.j ? (q.n ? `${esc(q.n)} in <i>${esc(q.j)}</i>` : `<i>${esc(q.j)}</i>${vip}`) : esc(q.n || "");
    return `<div class="pt">${titleLink(q.t, q.l, q.lt)}${tierBadge(q.r, q.c)}</div>
      <div class="pm">${esc(authorsTxt(q.a))}${q.a && q.a.length ? ". " : ""}${q.y || "n.d."}.${where ? " " + where + "." : ""}</div>`;
  }
  function paperList(ps, box) {
    if (!box) return;
    const st = { cat: "", q: "" };
    const draw = () => {
      const qs = st.q.toLowerCase().split(/\s+/).filter(Boolean);
      const keep = (q) => (!st.cat || q.c === st.cat) &&
        qs.every((t) => (q.t + " " + (q.j || "") + " " + (q.a || []).join(" ") + " " + (q.y || "")).toLowerCase().includes(t));
      const body = CAT.map(([c, lab]) => {
        const xs = ps.filter((q) => q.c === c && keep(q));
        return xs.length ? `<h4 class="psec">${lab} <span class="small">(${xs.length})</span></h4>${xs.map((q) => `<article class="paper">${cite(q)}${q.abs ? `<details><summary>Abstract</summary><div class="abs">${esc(q.abs)}</div></details>` : ""}</article>`).join("")}` : "";
      }).join("");
      box.querySelector(".plist").innerHTML = body || `<p class="small">No papers match.</p>`;
      box.querySelectorAll("[data-cat]").forEach((b) => b.classList.toggle("on", b.dataset.cat === st.cat));
    };
    const n = Object.fromEntries(CAT.map(([c]) => [c, ps.filter((q) => q.c === c).length]));
    box.innerHTML = `<div class="pbar"><span class="chips"><button class="chip" data-cat="">All</button>${CAT.map(([c, lab]) => `<button class="chip" data-cat="${c}">${lab} (${n[c]})</button>`).join("")}</span>
      <input type="search" id="pfq" placeholder="Filter by title, coauthor, journal, year…"></div><div class="plist"></div>`;
    box.querySelectorAll("[data-cat]").forEach((b) => b.onclick = () => { st.cat = b.dataset.cat; draw(); });
    box.querySelector("#pfq").oninput = (e) => { st.q = e.target.value.trim(); draw(); };
    draw();
  }

  // ---------------------------------------------------------------- paper search
  let PIDX = null;
  function renderPapers(q) {
    const s = { q: q.get("q") || "", cat: q.get("c") || "", jr: q.get("jr") || "", uni: q.get("uni") || "", y0: q.get("y0") || "", y1: q.get("y1") || "", page: +(q.get("p") || 1) };
    if (!PIDX) {
      app.innerHTML = `<p class="small">Loading paper index (${(D.n_pindex || 0).toLocaleString()} papers)…</p>`;
      getJSON("papers.json").then((rows) => {
        PIDX = rows.map((r) => ({ t: r[0], y: r[1], c: r[2], r: r[3], p: r[4], l: r[5], lt: r[0].toLowerCase() }));
        if (route().parts[0] === "papers") renderPapers(route().q);
      }).catch((e) => { console.error(e); app.innerHTML = `<p class="empty">Could not load the paper index — please reload the page (Ctrl+F5).</p>`; });
      return;
    }
    const toks = s.q.toLowerCase().split(/\s+/).filter(Boolean);
    const jrOk = (x) => s.jr === "" || (x.r >= 0 && (s.jr.startsWith("t:") ? D.journals[x.r][1] === +s.jr.slice(2) : x.r === +s.jr));
    const list = PIDX.filter((x) => (s.cat === "" || x.c === +s.cat) && jrOk(x) && (!s.uni || U[P[x.p].uni].id === s.uni) &&
      (!s.y0 || x.y >= +s.y0) && (!s.y1 || (x.y && x.y <= +s.y1)) && toks.every((t) => x.lt.includes(t) || P[x.p].name.toLowerCase().includes(t)))
      .sort((a, b) => b.y - a.y || a.c - b.c);
    const size = 100, pages = Math.max(1, Math.ceil(list.length / size)); s.page = Math.min(Math.max(1, s.page), pages);
    app.innerHTML = `<p class="intro">Search papers by faculty in the directory: publications in leading economics and business journals, papers under revise &amp; resubmit, and working papers. Words match the paper title or the faculty member's name.</p>
      <section class="controls"><div class="row">
        <input id="pq" type="search" placeholder="Search paper titles or author…" value="${esc(s.q)}" autocomplete="off">
        <select id="pc"><option value="">All types</option>${CAT.map(([, lab], i) => opt(i, lab, s.cat)).join("")}</select>
        <select id="pj"><option value="">Any journal</option>${journalOpts(s.jr)}</select>
      </div><div class="row">
        <select id="pu"><option value="">All institutions</option>${U.filter((u) => u.n).map((u) => opt(u.id, u.short, s.uni)).join("")}</select>
        <input id="py0" type="number" placeholder="From year" value="${esc(s.y0)}" style="max-width:120px"><input id="py1" type="number" placeholder="To year" value="${esc(s.y1)}" style="max-width:120px">
        <button class="btn" id="preset" type="button">Reset</button></div></section>
      <p class="count">${list.length.toLocaleString()} papers · page ${s.page} of ${pages}</p>
      <section>${list.slice((s.page - 1) * size, s.page * size).map((x) => { const p = P[x.p], j = x.r >= 0 ? D.journals[x.r] : null;
        return `<article class="paper"><div class="pt">${titleLink(x.t, x.l)}${tierBadge(x.r, x.c)}</div>
          <div class="pm"><a href="#/p/${encodeURIComponent(p.id)}">${esc(p.name)}</a> (${esc(U[p.uni].short)}) · ${x.y || "n.d."} · ${x.c === 1 ? "R&amp;R" + (j ? ", " : "") : x.c === 2 ? "Working paper" : ""}${j ? `<i>${esc(j[0])}</i>` : ""}</div></article>`; }).join("") || `<p class="empty">No matches.</p>`}</section>
      ${pages > 1 ? `<div class="pager">${s.page > 1 ? `<button class="btn" data-pg="${s.page - 1}">← Prev</button>` : ""}<span class="small">Page ${s.page} / ${pages}</span>${s.page < pages ? `<button class="btn" data-pg="${s.page + 1}">Next →</button>` : ""}</div>` : ""}`;
    const go = (page = 1) => { setQuery("/papers", { q: s.q, c: s.cat, jr: s.jr, uni: s.uni, y0: s.y0, y1: s.y1, p: page > 1 ? page : "" }); renderPapers(route().q); };
    bindSearch("pq", (v) => { s.q = v; go(); });
    for (const [id, k] of [["pc", "cat"], ["pj", "jr"], ["pu", "uni"], ["py0", "y0"], ["py1", "y1"]]) document.getElementById(id).onchange = (e) => { s[k] = e.target.value; go(); };
    document.getElementById("preset").onclick = () => { history.replaceState(null, "", "#/papers"); renderPapers(new URLSearchParams()); };
    app.querySelectorAll("[data-pg]").forEach((b) => b.onclick = () => { go(+b.dataset.pg); window.scrollTo(0, 0); });
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
    const c = {}; for (const p of P) for (const i of p.pfield) c[i] = (c[i] || 0) + 1;
    const t = {}; for (const p of P) for (const f of p.fields) t[f] = (t[f] || 0) + 1;
    const groups = uniq(D.pfields.map((x) => x.split(":")[0]));
    app.innerHTML = `<p class="intro">Each faculty member is tagged with up to <b>three fields</b> (their main research areas, in order), organized by school type: economics subfields; business-school areas (with sub-areas for large ones such as Finance, Marketing, Management, Operations &amp; IS); public policy; law; public health. Economists in business schools are classified under the Economics fields.</p>` +
      groups.map((g) => {
        const items = D.pfields.map((x, i) => [x, i]).filter(([x]) => x.split(":")[0] === g);
        const tot = P.filter((p) => p.pfield.some((i) => D.pfields[i].split(":")[0] === g)).length;
        return `<div class="group-h"><a class="nm" href="#/?field=g:${encodeURIComponent(g)}">${esc(g)}</a><span class="n">${tot.toLocaleString()} faculty</span></div><div class="fgrid">
          ${items.map(([x, i]) => `<a class="fcell" href="#/?field=${i}"><span>${esc(x.includes(":") ? x.split(": ")[1] : x)}</span><span class="c">${(c[i] || 0).toLocaleString()}</span></a>`).join("")}</div>`;
      }).join("");
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
