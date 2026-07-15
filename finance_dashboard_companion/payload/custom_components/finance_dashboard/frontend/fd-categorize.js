/**
 * Finance — Drag & Drop Transaction Categorizer
 *
 * Admin-only Lovelace card for re-categorizing transactions.
 * Drag transactions into category buckets. System learns new
 * keyword patterns from user corrections.
 *
 * Usage (admin dashboards only):
 *   type: custom:fd-categorize
 *
 * PRIVACY: This card only renders for HA admin users.
 * Individual transaction data is shown — never expose on
 * public/non-admin dashboards.
 */

const _ALL_CATS = ["housing","groceries","dining","transport","insurance","subscriptions","loans","utilities","health","leisure","pets","clothing","charity","cards","cleaning","income","transfers","excluded","other"];

class FdCategorize extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) { this._render(); this._rendered = true; }
    this._load();
  }

  setConfig(config) { this._config = config || {}; }

  // Source category filter — "other" by default (backwards-compatible)
  get _sourceFilter() { return this.__sourceFilter || "other"; }
  set _sourceFilter(v) { this.__sourceFilter = v; }

  _render() {
    this.innerHTML = `
<ha-card header="${window._fd.tSync('categorize.title')}">
<style>
  .fdc { padding: 16px; font-size: 13px; }
  .fdc-info { color: var(--secondary-text-color); font-size: 12px; margin-bottom: 10px;
    padding: 10px; background: var(--primary-background-color); border-radius: 8px; }
  .fdc-filter { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 12px; color: var(--secondary-text-color); }
  .fdc-filter select {
    font-size: 12px; padding: 3px 8px; border-radius: 6px;
    border: 1px solid var(--divider-color);
    background: var(--primary-background-color);
    color: var(--primary-text-color);
    cursor: pointer; outline: none;
  }
  .fdc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .fdc-txns { max-height: 420px; overflow-y: auto; }
  .fdc-cats { display: flex; flex-direction: column; gap: 4px; }

  .fdc-txn { padding: 10px 12px; background: var(--primary-background-color);
    border: 1px solid var(--divider-color); border-radius: 8px;
    cursor: grab; transition: transform 0.15s, box-shadow 0.15s; margin-bottom: 6px; }
  .fdc-txn:active { cursor: grabbing; transform: scale(1.02);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
  .fdc-txn .name { font-weight: 500; margin-bottom: 2px; }
  .fdc-txn .meta { font-size: 11px; color: var(--secondary-text-color); }
  .fdc-txn .amt { font-weight: 600; float: right; }
  .fdc-txn .amt.neg { color: var(--primary-text-color); }
  .fdc-txn .amt.pos { color: var(--accent-color, #4ecca3); }

  .fdc-cat { padding: 5px 8px; border: 2px dashed var(--divider-color);
    border-radius: 8px; min-height: 32px;
    transition: border-color 0.2s, background 0.2s;
    display: flex; align-items: center; gap: 6px; }
  .fdc-cat.over { border-color: var(--accent-color, #4ecca3);
    background: rgba(78,204,163,0.07); }
  .fdc-cat .cat-dot { width: 7px; height: 7px; border-radius: 2px; flex-shrink: 0; }
  .fdc-cat .cat-label { font-weight: 600; font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .fdc-cat .cat-hint { font-size: 10px; color: var(--secondary-text-color); margin-left: auto; white-space: nowrap; }

  .fdc-learned { margin-top: 14px; padding: 12px; background: var(--primary-background-color);
    border-radius: 8px; }
  .fdc-learned h4 { font-size: 12px; color: var(--accent-color); margin-bottom: 6px; }
  .fdc-rule { font-size: 11px; color: var(--secondary-text-color); padding: 2px 0; }
  .fdc-none { color: var(--secondary-text-color); font-size: 12px; text-align: center; padding: 20px; }
</style>
<div class="fdc" id="fdc">
  <div class="fdc-info">
    <span id="fdc-instructions"></span>
    <strong id="fdc-admin-only"></strong>
  </div>
  <div class="fdc-filter">
    <span id="fdc-filter-label"></span>
    <select id="fdc-source-select"></select>
  </div>
  <div class="fdc-grid">
    <div class="fdc-txns" id="txnList"></div>
    <div class="fdc-cats" id="catList"></div>
  </div>
  <div class="fdc-learned" id="learned"></div>
</div>
</ha-card>`;
  }

  async _load() {
    if (!this._hass) return;
    const instrEl = this.querySelector("#fdc-instructions");
    const adminEl = this.querySelector("#fdc-admin-only");
    const filterLabelEl = this.querySelector("#fdc-filter-label");
    if (instrEl) instrEl.textContent = await window._fd.t("categorize.instructions");
    if (adminEl) adminEl.textContent = await window._fd.t("categorize.admin_only");
    if (filterLabelEl) filterLabelEl.textContent = window._fd.tSync("categorize.filter_label");
    try {
      const data = await this._hass.callApi("GET", "finance_dashboard/transactions");
      if (data.privacy === "aggregate_only") {
        this.querySelector("#fdc").innerHTML =
          `<div class="fdc-none">${window._fd.tSync("categorize.admin_required")}</div>`;
        return;
      }
      this._allTxns = data.transactions || [];
      this._initSourceSelect();
      this._renderCatTargets();
      this._renderTxnList();
      this._renderLearnedRules();
    } catch { /* not configured */ }
  }

  _initSourceSelect() {
    const select = this.querySelector("#fdc-source-select");
    if (!select || select.children.length > 0) return;

    const allOpt = document.createElement("option");
    allOpt.value = "all";
    allOpt.textContent = window._fd.tSync("categorize.filter_all");
    select.appendChild(allOpt);

    _ALL_CATS.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = window._fd.CAT_LABELS[c] || c;
      if (c === this._sourceFilter) opt.selected = true;
      select.appendChild(opt);
    });

    select.addEventListener("change", () => {
      this._sourceFilter = select.value;
      this._renderTxnList();
    });
  }

  _renderCatTargets() {
    const catColors = window._fd.CAT_COLORS;
    const catList = this.querySelector("#catList");
    catList.innerHTML = _ALL_CATS.map((c) =>
      `<div class="fdc-cat" data-cat="${c}">
        <div class="cat-dot" style="background:${catColors[c]}"></div>
        <span class="cat-label">${window._fd.CAT_LABELS[c] || c}</span>
        <span class="cat-hint">${window._fd.tSync("categorize.drop_here")}</span>
      </div>`
    ).join("");

    catList.querySelectorAll(".fdc-cat").forEach((el) => {
      el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("over"); });
      el.addEventListener("dragleave", () => el.classList.remove("over"));
      el.addEventListener("drop", (e) => {
        e.preventDefault();
        el.classList.remove("over");
        try {
          const data = JSON.parse(e.dataTransfer.getData("text/plain"));
          this._assignCategory(data.creditor, el.dataset.cat, data.amount);
          el.querySelector(".cat-hint").textContent =
            window._fd.tSync("categorize.assigned", { name: data.creditor });
        } catch {}
      });
    });
  }

  _renderTxnList() {
    const txns = this._allTxns || [];
    const f = this._sourceFilter;

    let filtered;
    if (f === "all") {
      filtered = txns.slice(0, 30);
    } else if (f === "other") {
      filtered = txns.filter((t) => t.category === "other" || !t.category).slice(0, 20);
    } else {
      filtered = txns.filter((t) => t.category === f).slice(0, 20);
    }

    const eur = (v) => new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(v);
    const txnList = this.querySelector("#txnList");
    if (!txnList) return;

    if (filtered.length === 0) {
      const emptyKey = f === "other" ? "categorize.all_done" : "categorize.filter_empty";
      txnList.innerHTML = `<div class="fdc-none">${window._fd.tSync(emptyKey)}</div>`;
      return;
    }

    txnList.innerHTML = filtered.map((t, i) => {
      const amt = parseFloat(t.amount);
      return `<div class="fdc-txn" draggable="true" data-idx="${i}"
        data-creditor="${(t.creditor || t.description || "").replace(/"/g, "")}"
        data-amount="${t.amount}">
        <span class="amt ${amt >= 0 ? "pos" : "neg"}">${eur(amt)}</span>
        <div class="name">${t.creditor || t.description || window._fd.tSync("categorize.unknown")}</div>
        <div class="meta">${t.date} &middot; ${window._fd.CAT_LABELS[t.category] || t.category || window._fd.tSync("categorize.uncategorized")}</div>
      </div>`;
    }).join("");

    txnList.querySelectorAll(".fdc-txn").forEach((el) => {
      el.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/plain", JSON.stringify({
          creditor: el.dataset.creditor,
          amount: el.dataset.amount,
        }));
      });
    });
  }

  async _assignCategory(creditor, category, amount) {
    // Scope the rule to the sign of the dragged transaction so the same
    // keyword can resolve differently for money in vs. money out (e.g. an
    // incoming salary vs. an outgoing transfer sharing the payer's name).
    const amt = parseFloat(amount);
    const direction = amt > 0 ? "credit" : amt < 0 ? "debit" : "any";
    if (this._hass && creditor) {
      try {
        await this._hass.callService("finance_dashboard", "add_categorization_rule", {
          category,
          keyword: creditor.toLowerCase(),
          direction,
        });
      } catch (e) {
        console.error("fd-categorize: add_categorization_rule failed:", e);
        return;
      }
    }
    this._addLearnedRule(creditor, category, direction);
    // Reload transactions from API so the list reflects the new categorization
    this._load();
  }

  _addLearnedRule(creditor, category, direction) {
    if (!this._learnedRules) this._learnedRules = [];
    this._learnedRules.push({ creditor, category, direction, time: new Date().toLocaleTimeString() });
  }

  _renderLearnedRules() {
    const el = this.querySelector("#learned");
    if (!el) return;
    if (!this._learnedRules || this._learnedRules.length === 0) {
      el.innerHTML = `<h4>${window._fd.tSync("categorize.learned")}</h4><div class="fdc-rule">${window._fd.tSync("categorize.none_session")}</div>`;
      return;
    }
    el.innerHTML = `<h4>${window._fd.tSync("categorize.learned_count", { count: this._learnedRules.length })}</h4>` +
      this._learnedRules.map((r) => {
        const dir = r.direction && r.direction !== "any"
          ? ` <em>(${window._fd.tSync("categorize.direction_" + r.direction)})</em>`
          : "";
        return `<div class="fdc-rule">${r.time}: "${r.creditor}" &rarr; ${window._fd.CAT_LABELS[r.category] || r.category}${dir}</div>`;
      }).join("");
  }

  static getStubConfig() { return {}; }
  getCardSize() { return 6; }
}

if (!customElements.get("fd-categorize")) customElements.define("fd-categorize", FdCategorize);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "fd-categorize",
  name: "Personal Bankin — Categorize",
  description: "Drag & drop transaction categorization (admin only).",
});
