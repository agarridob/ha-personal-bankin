/**
 * fd-transactions-log — Log of imported (cached) transactions.
 *
 * Properties:
 *   data {object} — Unified data object from fd-data-provider
 *
 * Reads data.transactions (admin-only, cache-only). Shows up to 25 rows
 * by default with an expand toggle to reveal the full filtered set.
 * Supports 7 filter controls: direction, category, account, search,
 * amount range, date range, and pending-only toggle.
 */

// TX_CAT_LABELS comes from window._fd.CAT_LABELS (set by fd-shared-styles.js).

const DEFAULT_LIMIT = 25;

const _filterDefaults = () => ({
  direction: "all",   // "all" | "income" | "expense"
  category: "",
  account: "",
  search: "",
  amountMin: "",
  amountMax: "",
  dateFrom: "",
  dateTo: "",
  pendingOnly: false,
});

class FdTransactionsLog extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._expanded = false;
    this._filters = _filterDefaults();
    this._allTxs = [];
  }

  set data(v) {
    this._data = v;
    this._expanded = false;
    this._render();
  }

  _hasActiveFilters() {
    const f = this._filters;
    return f.direction !== "all" || f.category || f.account || f.search ||
           f.amountMin !== "" || f.amountMax !== "" ||
           f.dateFrom || f.dateTo || f.pendingOnly;
  }

  _applyFilters(txs) {
    const f = this._filters;
    return txs.filter((t) => {
      const amount = parseFloat(t.amount);
      if (f.direction === "income" && !(amount > 0)) return false;
      if (f.direction === "expense" && !(amount < 0)) return false;
      if (f.category && t.category !== f.category) return false;
      if (f.account && t.account_name !== f.account) return false;
      if (f.search) {
        const q = f.search.toLowerCase();
        const hay = `${t.creditor || ""} ${t.description || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (f.amountMin !== "") {
        const minV = parseFloat(f.amountMin);
        if (!isNaN(minV) && Math.abs(amount) < minV) return false;
      }
      if (f.amountMax !== "") {
        const maxV = parseFloat(f.amountMax);
        if (!isNaN(maxV) && Math.abs(amount) > maxV) return false;
      }
      if (f.pendingOnly && t.status !== "pending") return false;
      if (f.dateFrom && t.date < f.dateFrom) return false;
      if (f.dateTo && t.date > f.dateTo) return false;
      return true;
    });
  }

  _render() {
    const d = this._data;
    const txs = Array.isArray(d?.transactions) ? d.transactions : null;

    const hasAccounts = (d?.accountCount || 0) > 0 || d?.demoMode;
    const everRefreshed = !!d?.lastRefresh || d?.demoMode;
    if (!hasAccounts || !everRefreshed || !txs) {
      this.shadowRoot.innerHTML = "";
      return;
    }

    this._allTxs = txs;
    const { CAT_LABELS, SHARED_CSS, escHtml, tSync } = window._fd;

    const accounts = [...new Set(txs.map((t) => t.account_name).filter(Boolean))].sort();
    const categories = [...new Set(txs.map((t) => t.category).filter(Boolean))].sort();
    const total = txs.length;

    const catOptions = categories.map((c) =>
      `<option value="${escHtml(c)}"${this._filters.category === c ? " selected" : ""}>${escHtml(CAT_LABELS[c] || c)}</option>`
    ).join("");

    const accOptions = accounts.map((a) =>
      `<option value="${escHtml(a)}"${this._filters.account === a ? " selected" : ""}>${escHtml(a)}</option>`
    ).join("");

    const LOCAL_CSS = `
:host { margin-bottom: 20px; }
.card-h .count { font-weight: 400; font-size: 12px; color: var(--tx2); }
.tx-filters {
  padding: 8px 18px 6px;
  border-bottom: 1px solid var(--bd);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.dir-pills {
  display: flex;
  border: 1px solid var(--bd);
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}
.dir-pill {
  padding: 4px 10px;
  font-size: 12px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--tx2);
  font-family: inherit;
  white-space: nowrap;
  transition: background 0.1s;
}
.dir-pill.active { background: var(--ac); color: #fff; }
.dir-pill:not(.active):hover { background: var(--sf2); }
.filter-search {
  flex: 1;
  min-width: 100px;
  padding: 4px 8px;
  font-size: 12px;
  border: 1px solid var(--bd);
  border-radius: 8px;
  background: var(--sf2);
  color: var(--tx);
  font-family: inherit;
  outline: none;
}
.filter-search:focus { border-color: var(--ac); }
.filter-select {
  padding: 4px 6px;
  font-size: 12px;
  border: 1px solid var(--bd);
  border-radius: 8px;
  background: var(--sf2);
  color: var(--tx);
  font-family: inherit;
  outline: none;
  cursor: pointer;
  max-width: 150px;
}
.filter-select:focus { border-color: var(--ac); }
.filter-amount-group {
  display: flex;
  align-items: center;
  gap: 3px;
  border: 1px solid var(--bd);
  border-radius: 8px;
  background: var(--sf2);
  padding: 0 6px;
}
.filter-label { font-size: 12px; color: var(--tx2); white-space: nowrap; }
.filter-amount {
  width: 60px;
  padding: 4px 2px;
  font-size: 12px;
  border: none;
  background: transparent;
  color: var(--tx);
  font-family: inherit;
  outline: none;
}
.filter-date {
  padding: 4px 6px;
  font-size: 12px;
  border: 1px solid var(--bd);
  border-radius: 8px;
  background: var(--sf2);
  color: var(--tx);
  font-family: inherit;
  outline: none;
}
.filter-date:focus { border-color: var(--ac); }
.filter-pending {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--tx2);
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
}
.filter-pending input[type=checkbox] { cursor: pointer; accent-color: var(--ac); }
.filter-clear {
  padding: 4px 10px;
  font-size: 11px;
  border: 1px solid var(--bd);
  border-radius: 8px;
  background: transparent;
  color: var(--tx2);
  cursor: pointer;
  font-family: inherit;
  margin-left: auto;
  flex-shrink: 0;
}
.filter-clear:hover { border-color: var(--dg); color: var(--dg); }
.tx-list { padding: 6px 18px 12px; max-height: 540px; overflow-y: auto; }
.tx-item {
  display: grid;
  grid-template-columns: 56px 1fr auto;
  gap: 12px;
  align-items: flex-start;
  padding: 10px 0;
  border-bottom: 1px solid var(--bd);
  font-size: 13px;
}
.tx-item:last-child { border-bottom: none; }
.tx-date { font-size: 11px; color: var(--tx2); font-variant-numeric: tabular-nums; padding-top: 2px; white-space: nowrap; }
.tx-main { min-width: 0; }
.tx-label { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; align-items: center; gap: 8px; }
.tx-sub { font-size: 11px; color: var(--tx2); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tx-meta { margin-top: 4px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.tx-cat { font-size: 10px; color: var(--tx2); background: var(--sf2); padding: 2px 6px; border-radius: 4px; }
.tx-acc { font-size: 10px; color: var(--tx2); }
.tx-pending { font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--wn); border: 1px solid var(--wn); padding: 1px 5px; border-radius: 4px; }
.tx-amount { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; padding-top: 2px; }
.tx-amount.pos { color: var(--ac); }
.tx-amount.neg { color: var(--dg); }
.tx-toggle { display: block; margin: 6px auto 0; padding: 6px 16px; background: transparent; border: 1px solid var(--bd); border-radius: 8px; color: var(--tx2); font-size: 12px; cursor: pointer; font-family: inherit; }
.tx-toggle:hover { color: var(--tx2); border-color: var(--tx2); }
.tx-empty { padding: 24px 18px; color: var(--tx2); font-size: 13px; text-align: center; }
`;

    this.shadowRoot.innerHTML = `
<style>${SHARED_CSS}${LOCAL_CSS}</style>
<div class="card">
  <div class="card-h">
    <span>${tSync("transactions.title")}</span>
    <span class="count" id="countLabel">${total} ${tSync("transactions.in_cache")}</span>
  </div>
  <div class="tx-filters">
    <div class="filter-row">
      <div class="dir-pills">
        <button class="dir-pill${this._filters.direction === "all" ? " active" : ""}" data-dir="all">${tSync("transactions.filter.all")}</button>
        <button class="dir-pill${this._filters.direction === "income" ? " active" : ""}" data-dir="income">${tSync("transactions.filter.income")}</button>
        <button class="dir-pill${this._filters.direction === "expense" ? " active" : ""}" data-dir="expense">${tSync("transactions.filter.expense")}</button>
      </div>
      <input class="filter-search" id="filterSearch" type="search"
        placeholder="${tSync("transactions.filter.search_placeholder")}"
        value="${escHtml(this._filters.search)}">
    </div>
    <div class="filter-row">
      <select class="filter-select" id="filterCat">
        <option value="">${tSync("transactions.filter.all_categories")}</option>
        ${catOptions}
      </select>
      ${accounts.length > 1 ? `
      <select class="filter-select" id="filterAcc">
        <option value="">${tSync("transactions.filter.all_accounts")}</option>
        ${accOptions}
      </select>` : ""}
      <div class="filter-amount-group">
        <span class="filter-label">&gt; €</span>
        <input class="filter-amount" id="filterAmtMin" type="number" min="0" step="0.01"
          placeholder="0" value="${escHtml(this._filters.amountMin)}">
      </div>
      <div class="filter-amount-group">
        <span class="filter-label">&lt; €</span>
        <input class="filter-amount" id="filterAmtMax" type="number" min="0" step="0.01"
          placeholder="∞" value="${escHtml(this._filters.amountMax)}">
      </div>
      <input class="filter-date" id="filterDateFrom" type="date"
        title="${tSync("transactions.filter.date_from")}" value="${this._filters.dateFrom}">
      <input class="filter-date" id="filterDateTo" type="date"
        title="${tSync("transactions.filter.date_to")}" value="${this._filters.dateTo}">
      <label class="filter-pending">
        <input type="checkbox" id="filterPending"${this._filters.pendingOnly ? " checked" : ""}>
        ${tSync("transactions.filter.pending_only")}
      </label>
      <button class="filter-clear" id="filterClear"
        style="${this._hasActiveFilters() ? "" : "display:none"}">
        ${tSync("transactions.filter.clear")}
      </button>
    </div>
  </div>
  <div id="txListContainer"></div>
</div>`;

    this._attachFilterListeners();
    this._updateList();
  }

  _attachFilterListeners() {
    const sr = this.shadowRoot;
    const upd = () => this._updateList();

    sr.querySelectorAll(".dir-pill").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._filters.direction = btn.dataset.dir;
        sr.querySelectorAll(".dir-pill").forEach((b) =>
          b.classList.toggle("active", b.dataset.dir === this._filters.direction)
        );
        upd();
      });
    });

    const search = sr.getElementById("filterSearch");
    if (search) search.addEventListener("input", () => { this._filters.search = search.value; upd(); });

    const cat = sr.getElementById("filterCat");
    if (cat) cat.addEventListener("change", () => { this._filters.category = cat.value; upd(); });

    const acc = sr.getElementById("filterAcc");
    if (acc) acc.addEventListener("change", () => { this._filters.account = acc.value; upd(); });

    const amtMin = sr.getElementById("filterAmtMin");
    if (amtMin) amtMin.addEventListener("input", () => { this._filters.amountMin = amtMin.value; upd(); });

    const amtMax = sr.getElementById("filterAmtMax");
    if (amtMax) amtMax.addEventListener("input", () => { this._filters.amountMax = amtMax.value; upd(); });

    const dateFrom = sr.getElementById("filterDateFrom");
    if (dateFrom) dateFrom.addEventListener("change", () => { this._filters.dateFrom = dateFrom.value; upd(); });

    const dateTo = sr.getElementById("filterDateTo");
    if (dateTo) dateTo.addEventListener("change", () => { this._filters.dateTo = dateTo.value; upd(); });

    const pending = sr.getElementById("filterPending");
    if (pending) pending.addEventListener("change", () => { this._filters.pendingOnly = pending.checked; upd(); });

    const clear = sr.getElementById("filterClear");
    if (clear) {
      clear.addEventListener("click", () => {
        this._filters = _filterDefaults();
        this._expanded = false;
        this._render();
      });
    }
  }

  _updateList() {
    const sr = this.shadowRoot;
    const container = sr.getElementById("txListContainer");
    if (!container) return;

    const { CAT_LABELS, escHtml, tSync } = window._fd;
    const txs = this._allTxs;
    const filtered = this._applyFilters(txs);
    const total = txs.length;
    const filteredCount = filtered.length;

    const countLabel = sr.getElementById("countLabel");
    if (countLabel) {
      countLabel.textContent = this._hasActiveFilters()
        ? `${filteredCount}/${total} ${tSync("transactions.in_cache")}`
        : `${total} ${tSync("transactions.in_cache")}`;
    }

    const clearBtn = sr.getElementById("filterClear");
    if (clearBtn) clearBtn.style.display = this._hasActiveFilters() ? "" : "none";

    if (filteredCount === 0) {
      container.innerHTML = `<div class="tx-empty">${tSync(
        this._hasActiveFilters() ? "transactions.filter.no_results" : "transactions.empty_cache"
      )}</div>`;
      return;
    }

    const limit = this._expanded ? filteredCount : DEFAULT_LIMIT;
    const visible = filtered.slice(0, limit);

    const eur = (v) => new Intl.NumberFormat("de-DE", {
      style: "currency", currency: "EUR",
    }).format(Number(v) || 0);

    const rows = visible.map((t) => {
      const amount = parseFloat(t.amount);
      const isPositive = !isNaN(amount) && amount > 0;
      const amountClass = isPositive ? "pos" : "neg";
      const sign = isPositive ? "+" : "";
      const label = t.creditor || t.description || "—";
      const sub = t.creditor && t.description && t.creditor !== t.description
        ? t.description : "";
      const cat = CAT_LABELS[t.category] || t.category || tSync("general.other");
      const dateStr = this._formatDate(t.date);
      const pendingBadge = t.status === "pending"
        ? `<span class="tx-pending" title="${tSync("transactions.pending_title")}">${tSync("transactions.pending")}</span>`
        : "";
      const account = t.account_name
        ? `<span class="tx-acc">${escHtml(t.account_name)}</span>`
        : "";

      return `<div class="tx-item">
        <div class="tx-date">${escHtml(dateStr)}</div>
        <div class="tx-main">
          <div class="tx-label">${escHtml(label)} ${pendingBadge}</div>
          ${sub ? `<div class="tx-sub">${escHtml(sub)}</div>` : ""}
          <div class="tx-meta">
            <span class="tx-cat">${escHtml(cat)}</span>
            ${account}
          </div>
        </div>
        <div class="tx-amount ${amountClass}">${sign}${eur(amount)}</div>
      </div>`;
    }).join("");

    const toggleBtn = filteredCount > DEFAULT_LIMIT
      ? `<button class="tx-toggle" id="toggleBtn" aria-expanded="${this._expanded ? "true" : "false"}">
          ${this._expanded ? tSync("transactions.show_less") : tSync("transactions.show_all", { count: String(filteredCount) })}
        </button>`
      : "";

    container.innerHTML = `<div class="tx-list">${rows}</div>${toggleBtn}`;

    const btn = sr.getElementById("toggleBtn");
    if (btn) {
      btn.addEventListener("click", () => {
        this._expanded = !this._expanded;
        this._updateList();
      });
    }
  }

  _formatDate(iso) {
    if (!iso) return "";
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    if (!m) return iso;
    return `${m[3]}.${m[2]}.`;
  }
}

if (!customElements.get("fd-transactions-log")) customElements.define("fd-transactions-log", FdTransactionsLog);
