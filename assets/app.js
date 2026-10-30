/* LKR bank-rates dashboard. Reads data/rates.json (written by scraper/run.py). */
(() => {
  "use strict";

  const state = {
    db: null,
    cur: "USD",
    type: "tt",                  // "tt" | "notes"
    sort: { key: "buy", dir: -1 },
    bank: null,
    days: 90,
    cbslDays: 365,
  };
  const charts = {};

  // ---------- helpers ----------
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const fmt = (v, d = 2) => (v == null || isNaN(v) ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const signed = (v, d = 2) => (v == null || isNaN(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "±") + fmt(Math.abs(v), d));
  const cls = (v, goodWhenPositive = true) => (v == null || Math.abs(v) < 1e-9 ? "" : (v > 0) === goodWhenPositive ? "up" : "down");
  const shortDate = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const longDate = (iso) => new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  const avg = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : null);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch (_) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} },
  };

  const buyKey = () => state.type + "_buy";
  const sellKey = () => state.type + "_sell";
  const typeName = () => (state.type === "tt" ? "TT" : "cash");

  // v1 files were USD-only (cbsl: rows, rates[bank]: rows); lift them into the per-currency shape.
  function normalize(db) {
    if (db.version === 2) return db;
    return {
      ...db,
      version: 2,
      cbsl: { USD: db.cbsl || [] },
      rates: Object.fromEntries(Object.entries(db.rates || {}).map(([b, r]) => [b, { USD: r }])),
      currencies: { USD: { name: "US Dollar", symbol: "$" } },
    };
  }

  function rows(arr, fields) {
    return (arr || []).map((r) => Object.fromEntries(fields.map((f, i) => [f, r[i]])));
  }
  const cbslRows = (cur = state.cur) => rows(state.db.cbsl[cur], state.db.fields.cbsl);
  const bankRows = (id, cur = state.cur) => rows((state.db.rates[id] || {})[cur], state.db.fields.rates);
  const cutoff = (days) => {
    if (!days) return "0000-00-00";
    const d = new Date(); d.setDate(d.getDate() - days);
    return d.toISOString().slice(0, 10);
  };

  // ---------- derived "today" snapshot for the selected currency ----------
  function snapshot() {
    const db = state.db;
    const cb = cbslRows();
    const cbNow = cb[cb.length - 1] || {};
    const cbPrev = cb[cb.length - 2] || {};
    // Latest date any bank reported (any currency) = "today" for staleness.
    let latestDate = "";
    Object.values(db.rates).forEach((byCur) => Object.values(byCur).forEach((r) => {
      if (r.length && r[r.length - 1][0] > latestDate) latestDate = r[r.length - 1][0];
    }));
    const all = Object.entries(db.banks).map(([id, meta]) => {
      const r = bankRows(id);
      const cur = r[r.length - 1];
      const prev = r[r.length - 2];
      const buy = cur ? cur[buyKey()] : null;
      const sell = cur ? cur[sellKey()] : null;
      return {
        id, ...meta, cur, buy, sell,
        spread: buy && sell ? sell - buy : null,
        buyVs: buy && cbNow.tt_buy ? buy - cbNow.tt_buy : null,
        sellVs: sell && cbNow.tt_sell ? sell - cbNow.tt_sell : null,
        chg: buy && prev && prev[buyKey()] ? buy - prev[buyKey()] : null,
        stale: !cur || cur.date !== latestDate,
      };
    });
    const list = all.filter((b) => b.cur);
    const notQuoted = all.filter((b) => !b.cur);
    const fresh = list.filter((b) => !b.stale);
    const bestBuy = fresh.filter((b) => b.buy).reduce((a, b) => (!a || b.buy > a.buy ? b : a), null);
    const bestSell = fresh.filter((b) => b.sell).reduce((a, b) => (!a || b.sell < a.sell ? b : a), null);
    return { cbNow, cbPrev, list, notQuoted, latestDate, bestBuy, bestSell };
  }

  // ---------- currency tabs ----------
  function renderCurTabs() {
    const db = state.db;
    $("#cur-tabs").innerHTML = Object.entries(db.currencies).map(([code, c]) => {
      const cb = db.cbsl[code] || [];
      const last = cb[cb.length - 1], prev = cb[cb.length - 2];
      const chg = last && prev && last[1] && prev[1] ? last[1] - prev[1] : null;
      return `<button class="cur-tab" role="tab" data-cur="${code}" aria-selected="${code === state.cur}" title="${esc(c.name)}">
        <span class="code">${code}<small>${esc(c.symbol)}</small></span>
        <span class="rate">${last ? fmt(last[1]) : "—"} <span class="${cls(chg, false)}">${chg == null ? "" : chg > 0 ? "▲" : chg < 0 ? "▼" : ""}</span></span>
      </button>`;
    }).join("");
    $$("#cur-tabs .cur-tab").forEach((b) => b.addEventListener("click", () => setCurrency(b.dataset.cur)));
  }

  function setCurrency(code) {
    state.cur = code;
    store.set("cur", code);
    writeHash();
    $$("#cur-tabs .cur-tab").forEach((b) => b.setAttribute("aria-selected", b.dataset.cur === code));
    renderAll();
  }

  // ---------- tiles ----------
  function renderTiles(s) {
    const { cbNow, cbPrev, bestBuy, bestSell } = s;
    const c = state.cur;
    const midChg = cbNow.mid && cbPrev.mid ? cbNow.mid - cbPrev.mid : null;
    // A rising rate = rupee weakening, shown red.
    $("#tiles").innerHTML = `
      <div class="tile">
        <div class="label">CBSL middle rate · 1 ${c}</div>
        <div class="value">${fmt(cbNow.mid, 2)}</div>
        <div class="meta"><span class="chip ${cls(midChg, false)}">${signed(midChg, 2)}</span> vs prev<span class="hide-xs">ious</span> · ${cbNow.date ? shortDate(cbNow.date) : ""}</div>
      </div>
      <div class="tile">
        <div class="label">CBSL avg TT buy / sell</div>
        <div class="value">${fmt(cbNow.tt_buy)}<span class="sep">/</span>${fmt(cbNow.tt_sell)}</div>
        <div class="meta">Average of licensed banks</div>
      </div>
      <div class="tile highlight">
        <div class="label">Best to sell your ${c}</div>
        <div class="value">${fmt(bestBuy && bestBuy.buy)}</div>
        <div class="meta">${bestBuy ? esc(bestBuy.name) : "—"}<span class="hide-xs"> · highest ${typeName()} buying</span></div>
      </div>
      <div class="tile highlight">
        <div class="label">Best to buy ${c}</div>
        <div class="value">${fmt(bestSell && bestSell.sell)}</div>
        <div class="meta">${bestSell ? esc(bestSell.name) : "—"}<span class="hide-xs"> · lowest ${typeName()} selling</span></div>
      </div>`;
  }

  // ---------- today table ----------
  function renderTable(s) {
    const { list, bestBuy, bestSell, cbNow, notQuoted } = s;
    const { key, dir } = state.sort;
    const sorted = [...list].sort((a, b) => {
      if (key === "name") return dir * a.short.localeCompare(b.short);
      const av = a[key], bv = b[key];
      if (av == null) return 1;
      if (bv == null) return -1;
      return dir * (av - bv);
    });
    $$("#rates-table th").forEach((th) => {
      th.classList.toggle("sorted", th.dataset.sort === key);
      th.classList.toggle("asc", th.dataset.sort === key && dir === 1);
    });
    $("#rates-table tbody").innerHTML = sorted.map((b) => {
      const staleBadge = b.stale ? `<span class="badge warn" title="Latest fetch failed; showing ${b.cur.date}">${shortDate(b.cur.date)}</span>` : "";
      return `<tr data-id="${b.id}" class="${b.id === state.bank ? "selected" : ""}">
        <td><span class="bank-name">${esc(b.short)}</span><span class="bank-full">${esc(b.name)}</span>${staleBadge}</td>
        <td class="num ${bestBuy && b.id === bestBuy.id ? "best" : ""}">${fmt(b.buy)}</td>
        <td class="num ${bestSell && b.id === bestSell.id ? "best" : ""}">${fmt(b.sell)}</td>
        <td class="num">${fmt(b.spread)}</td>
        <td class="num hide-sm ${cls(b.buyVs, true)}">${signed(b.buyVs)}</td>
        <td class="num hide-sm ${cls(b.sellVs, false)}">${signed(b.sellVs)}</td>
        <td class="num hide-sm">${signed(b.chg)}</td>
        <td class="hide-sm"><a href="${esc(b.url)}" target="_blank" rel="noopener" class="badge" title="Open ${esc(b.name)} rates page">source ↗</a></td>
      </tr>`;
    }).join("");
    const cbSpread = cbNow.tt_sell && cbNow.tt_buy ? cbNow.tt_sell - cbNow.tt_buy : null;
    $("#rates-table tfoot").innerHTML = `<tr>
      <td>CBSL avg (TT)</td>
      <td class="num">${fmt(cbNow.tt_buy)}</td><td class="num">${fmt(cbNow.tt_sell)}</td><td class="num">${fmt(cbSpread)}</td>
      <td class="num hide-sm" colspan="2" style="text-align:center;font-weight:500">Middle rate ${fmt(cbNow.mid, 4)}</td>
      <td class="hide-sm"></td><td class="hide-sm"></td></tr>`;
    $$("#rates-table tbody tr").forEach((tr) => tr.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      selectBank(tr.dataset.id);
      $("#history").scrollIntoView({ behavior: "smooth", block: "start" });
    }));
    const notes = ["Tap a bank for its history. ★ = best rate today."];
    if (notQuoted.length) notes.push(`${notQuoted.map((b) => b.name).join(", ")} ${notQuoted.length > 1 ? "don't" : "doesn't"} publish ${state.cur} rates.`);
    if (state.type === "notes") notes.push("Some banks only publish TT rates, shown as —.");
    $("#table-foot").textContent = notes.join(" ");
  }

  // ---------- chart defaults ----------
  function baseOptions() {
    const grid = css("--grid"), muted = css("--text-muted"), sec = css("--text-secondary");
    Chart.defaults.font.family = "Inter, system-ui, sans-serif";
    Chart.defaults.color = sec;
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", align: "start", labels: { usePointStyle: true, pointStyle: "line", boxWidth: 24, color: sec, padding: 14 } },
        tooltip: {
          backgroundColor: css("--surface-1"), titleColor: css("--text-primary"), bodyColor: sec,
          borderColor: css("--border"), borderWidth: 1, padding: 10, usePointStyle: true, boxPadding: 4,
          callbacks: { label: (c) => ` ${c.dataset.label}: ${fmt(c.parsed.y, 4)}` },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: muted, maxRotation: 0, autoSkipPadding: 16 }, border: { color: grid } },
        y: { grid: { color: grid }, ticks: { color: muted, callback: (v) => fmt(v, 0) }, border: { display: false } },
      },
    };
  }
  const lineDs = (label, data, color, extra = {}) => ({
    label, data, borderColor: color, backgroundColor: color, borderWidth: 2, tension: 0.15,
    pointRadius: data.filter((v) => v != null).length <= 31 ? 3 : 0, pointHoverRadius: 5, spanGaps: true, ...extra,
  });
  function draw(id, config) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart(document.getElementById(id), config);
  }
  const isNarrow = () => matchMedia("(max-width: 480px)").matches;

  // Vertical reference lines (CBSL buy/sell) on the range chart.
  const refLines = {
    id: "refLines",
    afterDatasetsDraw(chart, _a, opts) {
      const { ctx, chartArea: a, scales: { x } } = chart;
      ctx.save();
      (opts.lines || []).forEach((l) => {
        if (l.value == null) return;
        const px = x.getPixelForValue(l.value);
        ctx.strokeStyle = l.color; ctx.lineWidth = 1.5; ctx.setLineDash([5, 4]);
        ctx.beginPath(); ctx.moveTo(px, a.top); ctx.lineTo(px, a.bottom); ctx.stroke();
        ctx.setLineDash([]); ctx.fillStyle = l.color; ctx.font = "500 11px Inter, sans-serif";
        ctx.textAlign = l.align; ctx.fillText(l.label, px + (l.align === "left" ? 4 : -4), a.bottom + 14);
      });
      ctx.restore();
    },
  };

  // ---------- range (dumbbell) chart ----------
  function renderRange(s) {
    const items = s.list.filter((b) => b.buy && b.sell).sort((a, b) => b.buy - a.buy);
    // Height follows the number of banks so rows never get cramped.
    $("#range-box").style.height = `${Math.max(220, items.length * 32 + 90)}px`;
    const labels = items.map((b) => b.short);
    const c1 = css("--series-1"), c2 = css("--series-2"), ref = css("--ref");
    const o = baseOptions();
    o.indexAxis = "y";
    o.interaction = { mode: "index", axis: "y", intersect: false };
    o.layout = { padding: { bottom: 18, right: 8 } };
    // Bars default to a zero baseline; let Chart.js pick nice bounds around the rate band instead.
    o.scales = {
      x: { position: "top", beginAtZero: false, grace: "4%",
        grid: { color: css("--grid") }, ticks: { color: css("--text-muted"), callback: (v) => fmt(v, 0), maxTicksLimit: isNarrow() ? 5 : 10 }, border: { display: false } },
      y: { grid: { display: false }, ticks: { color: css("--text-primary"), font: { weight: 600 } }, border: { display: false } },
    };
    o.plugins.legend.display = false;
    o.plugins.tooltip.filter = (t) => t.datasetIndex > 0;
    o.plugins.tooltip.callbacks.title = (t) => {
      const b = items[t[0].dataIndex];
      return b ? `${b.name}${b.stale ? ` (as of ${shortDate(b.cur.date)})` : ""}` : "";
    };
    // Horizontal chart: the rate is on x (parsed.y is just the row index).
    o.plugins.tooltip.callbacks.label = (c) => {
      const b = items[c.dataIndex];
      return c.datasetIndex === 1
        ? ` Buying ${fmt(b.buy)}: bank pays you this per ${state.cur}`
        : ` Selling ${fmt(b.sell)}: you pay this per ${state.cur}`;
    };
    o.plugins.tooltip.callbacks.afterBody = (t) => {
      const b = items[t[0].dataIndex];
      if (!b) return [];
      return [
        "",
        `Spread (selling − buying): ${fmt(b.spread)}`,
        `Buying vs CBSL avg ${fmt(s.cbNow.tt_buy)}: ${signed(b.buyVs)}`,
        `Selling vs CBSL avg ${fmt(s.cbNow.tt_sell)}: ${signed(b.sellVs)}`,
      ];
    };
    o.plugins.refLines = {
      lines: [
        { value: s.cbNow.tt_buy, color: ref, label: "CBSL buy", align: "right" },
        { value: s.cbNow.tt_sell, color: ref, label: "CBSL sell", align: "left" },
      ],
    };
    const pt = { type: "scatter", pointRadius: 6, pointHoverRadius: 8, pointBorderWidth: 2, pointBorderColor: css("--surface-1") };
    draw("range-chart", {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Range", data: items.map((b) => [b.buy, b.sell]), backgroundColor: css("--border"), borderRadius: 4, borderSkipped: false, barThickness: 6 },
          { ...pt, label: "Buying", data: items.map((b, i) => ({ x: b.buy, y: labels[i] })), backgroundColor: c1 },
          { ...pt, label: "Selling", data: items.map((b, i) => ({ x: b.sell, y: labels[i] })), backgroundColor: c2 },
        ],
      },
      options: o,
      plugins: [refLines],
    });
  }

  // ---------- bank history ----------
  function selectBank(id) {
    state.bank = id;
    $("#bank-select").value = id;
    writeHash();
    $$("#rates-table tbody tr").forEach((tr) => tr.classList.toggle("selected", tr.dataset.id === id));
    renderBank();
  }

  function renderBank() {
    const id = state.bank;
    const meta = state.db.banks[id];
    const from = cutoff(state.days);
    const allRows = bankRows(id);
    const br = allRows.filter((r) => r.date >= from);
    const cb = cbslRows().filter((r) => r.date >= from);
    const cbBy = Object.fromEntries(cb.map((r) => [r.date, r]));
    const bBy = Object.fromEntries(br.map((r) => [r.date, r]));
    const dates = [...new Set([...cb.map((r) => r.date), ...br.map((r) => r.date)])].sort();
    const bk = buyKey(), sk = sellKey();
    const pick = (map, k) => dates.map((d) => (map[d] ? map[d][k] : null));

    const c1 = css("--series-1"), c2 = css("--series-2"), ref = css("--ref");
    const o = baseOptions();
    o.scales.x.ticks.callback = function (v) { return shortDate(this.getLabelForValue(v)); };
    o.plugins.tooltip.callbacks.title = (t) => longDate(t[0].label);
    if (isNarrow()) o.plugins.legend.labels.boxWidth = 14;
    draw("bank-chart", {
      type: "line",
      data: {
        labels: dates,
        datasets: [
          lineDs(`${meta.short} buying`, pick(bBy, bk), c1),
          lineDs(`${meta.short} selling`, pick(bBy, sk), c2),
          lineDs("CBSL avg buying", pick(cbBy, "tt_buy"), ref, { borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0 }),
          lineDs("CBSL avg selling", pick(cbBy, "tt_sell"), ref, { borderDash: [2, 3], borderWidth: 1.5, pointRadius: 0 }),
          lineDs("CBSL middle", pick(cbBy, "mid"), ref, { borderWidth: 1, pointRadius: 0 }),
        ],
      },
      options: o,
    });

    const buys = br.map((r) => r[bk]).filter(Boolean);
    const spreads = br.filter((r) => r[bk] && r[sk]).map((r) => r[sk] - r[bk]);
    const prem = br.filter((r) => r[bk] && cbBy[r.date] && cbBy[r.date].tt_buy).map((r) => r[bk] - cbBy[r.date].tt_buy);
    const premS = br.filter((r) => r[sk] && cbBy[r.date] && cbBy[r.date].tt_sell).map((r) => r[sk] - cbBy[r.date].tt_sell);
    const last = br[br.length - 1] || {};
    $("#bank-stats").innerHTML = [
      [`Latest ${typeName()} buy / sell`, `${fmt(last[bk])} / ${fmt(last[sk])}`],
      ["Avg spread", fmt(avg(spreads))],
      ["Avg buy vs CBSL", signed(avg(prem))],
      ["Avg sell vs CBSL", signed(avg(premS))],
      ["Buy range", buys.length ? `${fmt(Math.min(...buys))} – ${fmt(Math.max(...buys))}` : "—"],
      ["Days tracked", String(allRows.length)],
    ].map(([k, v]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");

    $("#bank-note").innerHTML = !allRows.length
      ? `${esc(meta.name)} doesn't publish ${state.cur} rates. CBSL lines are shown for reference.`
      : allRows.length < 7
        ? `Bank history is collected daily from ${longDate(allRows[0].date)}, so this chart fills in over time. CBSL lines are backfilled.`
        : `Source: <a href="${esc(meta.url)}" target="_blank" rel="noopener">${esc(meta.name)} website</a>`;

    const head = `<thead><tr><th>Date</th><th class="num">TT buy</th><th class="num">TT sell</th><th class="num">Cash buy</th><th class="num">Cash sell</th><th class="num">CBSL buy</th><th class="num">CBSL sell</th><th class="num">CBSL mid</th></tr></thead>`;
    const body = [...dates].reverse().filter((d) => bBy[d]).map((d) => {
      const r = bBy[d], c = cbBy[d] || {};
      return `<tr><td>${d}</td><td class="num">${fmt(r.tt_buy)}</td><td class="num">${fmt(r.tt_sell)}</td><td class="num">${fmt(r.notes_buy)}</td><td class="num">${fmt(r.notes_sell)}</td><td class="num">${fmt(c.tt_buy)}</td><td class="num">${fmt(c.tt_sell)}</td><td class="num">${fmt(c.mid, 4)}</td></tr>`;
    }).join("");
    $("#hist-table").innerHTML = head + `<tbody>${body}</tbody>`;
  }

  function downloadCsv(e) {
    e.preventDefault();
    const id = state.bank, cur = state.cur;
    const cbBy = Object.fromEntries(cbslRows().map((r) => [r.date, r]));
    const lines = ["date,currency,tt_buy,tt_sell,cash_buy,cash_sell,cbsl_tt_buy,cbsl_tt_sell,cbsl_mid"];
    bankRows(id).forEach((r) => {
      const c = cbBy[r.date] || {};
      lines.push([r.date, cur, r.tt_buy, r.tt_sell, r.notes_buy, r.notes_sell, c.tt_buy, c.tt_sell, c.mid].map((v) => v ?? "").join(","));
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = `${cur.toLowerCase()}-lkr-${id}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // ---------- CBSL chart ----------
  function renderCbsl() {
    const cb = cbslRows().filter((r) => r.date >= cutoff(state.cbslDays));
    $("#cbsl-title").textContent = `Central Bank of Sri Lanka · ${state.cur}/LKR`;
    const o = baseOptions();
    if (!state.cbslDays || state.cbslDays > 90) {
      // One tick per month (every 3rd month for long ranges or narrow screens), at the month's first trading day.
      const step = cb.length > 400 || isNarrow() ? 3 : 1;
      o.scales.x.ticks.autoSkip = false;
      o.scales.x.ticks.callback = (v, i) => {
        const d = cb[i].date, prev = i ? cb[i - 1].date : "";
        if (d.slice(0, 7) === prev.slice(0, 7) || +d.slice(5, 7) % step) return null;
        return new Date(d + "T00:00:00").toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
      };
    } else {
      o.scales.x.ticks.callback = function (v) { return shortDate(this.getLabelForValue(v)); };
    }
    o.plugins.tooltip.callbacks.title = (t) => longDate(t[0].label);
    draw("cbsl-chart", {
      type: "line",
      data: {
        labels: cb.map((r) => r.date),
        datasets: [
          lineDs("Avg TT buying", cb.map((r) => r.tt_buy), css("--series-1")),
          lineDs("Avg TT selling", cb.map((r) => r.tt_sell), css("--series-2")),
          lineDs("Middle rate", cb.map((r) => r.mid), css("--ref"), { borderDash: [6, 4], borderWidth: 1.5 }),
        ],
      },
      options: o,
    });
  }

  // ---------- wiring ----------
  function renderAll() {
    const s = snapshot();
    document.title = `${state.cur}/LKR Bank Rates`;
    $$(".cur-code").forEach((el) => (el.textContent = state.cur));
    $("#table-title").textContent = `Today's ${state.cur} rates by bank`;
    $("#today-date").textContent = s.latestDate ? longDate(s.latestDate) : "";
    renderTiles(s);
    renderTable(s);
    renderRange(s);
    renderBank();
    renderCbsl();
    // Freshness from the data itself: several sources are only reachable from some runners.
    const stale = s.list.filter((b) => b.stale).map((b) => b.short);
    const cbAgeDays = s.cbNow.date && s.latestDate ? (new Date(s.latestDate) - new Date(s.cbNow.date)) / 864e5 : 0;
    if (cbAgeDays > 4) stale.unshift("CBSL");
    $("#status-line").textContent = stale.length ? ` Not updated today: ${stale.join(", ")}.` : "";
  }

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    return { cur: (p.get("cur") || "").toUpperCase(), bank: p.get("bank") };
  }
  function writeHash() {
    history.replaceState(null, "", `#cur=${state.cur}&bank=${state.bank}`);
  }

  function segment(sel, onPick) {
    $$(sel + " button").forEach((b) => b.addEventListener("click", () => {
      $$(sel + " button").forEach((x) => x.classList.toggle("on", x === b));
      onPick(b);
    }));
  }

  function initTheme() {
    const saved = store.get("theme");
    if (saved) document.documentElement.dataset.theme = saved;
    $("#theme").addEventListener("click", () => {
      const dark = document.documentElement.dataset.theme
        ? document.documentElement.dataset.theme === "dark"
        : matchMedia("(prefers-color-scheme: dark)").matches;
      const next = dark ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      store.set("theme", next);
      if (state.db) renderAll();
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => state.db && renderAll());
  }

  async function init() {
    initTheme();
    try {
      const res = await fetch("data/rates.json", { cache: "no-cache" });
      state.db = normalize(await res.json());
    } catch (e) {
      $("#updated").textContent = "Could not load data/rates.json. Run the scraper first (see README).";
      return;
    }
    const db = state.db;
    const updated = new Date(db.updated);
    $("#updated").textContent = "Updated " + updated.toLocaleString("en-GB", { timeZone: "Asia/Colombo", dateStyle: "medium", timeStyle: "short" })
      + ` · ${Object.keys(db.banks).length} banks vs CBSL`;

    const h = readHash();
    const savedCur = store.get("cur");
    state.cur = [h.cur, savedCur, "USD"].find((c) => c && db.currencies[c]) || Object.keys(db.currencies)[0];
    state.bank = db.banks[h.bank] ? h.bank : Object.keys(db.banks)[0];

    renderCurTabs();
    const sel = $("#bank-select");
    sel.innerHTML = Object.entries(db.banks).map(([id, b]) => `<option value="${id}">${esc(b.name)}</option>`).join("");
    sel.value = state.bank;
    sel.addEventListener("change", () => selectBank(sel.value));

    segment(".type-seg", (b) => { state.type = b.dataset.type; renderAll(); });
    segment("#range-seg", (b) => { state.days = +b.dataset.days; renderBank(); });
    segment("#cbsl-range-seg", (b) => { state.cbslDays = +b.dataset.days; renderCbsl(); });
    $$("#rates-table th[data-sort]").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.sort;
      state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : k === "name" ? 1 : -1 };
      renderTable(snapshot());
    }));
    $("#csv").addEventListener("click", downloadCsv);
    window.addEventListener("hashchange", () => {
      const h2 = readHash();
      if (db.currencies[h2.cur] && h2.cur !== state.cur) setCurrency(h2.cur);
      if (db.banks[h2.bank] && h2.bank !== state.bank) selectBank(h2.bank);
    });
    let t;
    window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderAll, 200); });
    renderAll();
  }

  init();
})();
