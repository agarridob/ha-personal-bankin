/**
 * fd-stats-row — 4-KPI grid: balance, expenses, income, savings rate.
 *
 * Properties:
 *   data {object} — Unified data object from fd-data-provider
 */

class FdStatsRow extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._expanded = false; // accounts breakdown open/closed (persists across re-renders)
  }

  set data(v) { this._data = v; this._render(); }

  _render() {
    const d = this._data;
    if (!d) {
      // Show skeleton cards while data is loading
      this._renderSkeleton();
      return;
    }

    const { SHARED_CSS, escHtml, tSync } = window._fd;

    const eur = (v) => new Intl.NumberFormat("de-DE", {
      style: "currency", currency: "EUR",
    }).format(v || 0);

    const totalBalance = d.totalBalance || 0;
    const totalExp = d.summary?.totalExpenses || 0;
    const totalInc = d.summary?.totalIncome || 0;
    const surplus = d.summary?.balance || 0;
    const txnCount = d.summary?.transactionCount || 0;
    const accountCount = d.accountCount || 0;
    const savingsRate = totalInc > 0 ? Math.round(surplus / totalInc * 100) : 0;

    // Per-account breakdown: only expandable when there are accounts to show.
    const accounts = Array.isArray(d.accounts) ? [...d.accounts] : [];
    const canExpand = accounts.length > 0;
    if (!canExpand) this._expanded = false;
    const open = canExpand && this._expanded;

    const LOCAL_CSS = `
:host {
  margin-bottom: 20px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 768px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
}
#balance-wrap { cursor: ${canExpand ? "pointer" : "default"}; }
.accounts-detail {
  overflow: hidden;
  max-height: 0;
  opacity: 0;
  transition: max-height .28s ease, opacity .2s ease, margin-top .28s ease;
  margin-top: 0;
}
.accounts-detail.open {
  max-height: 1000px;
  opacity: 1;
  margin-top: 14px;
}
.acc-list {
  background: var(--sf);
  border: 1px solid var(--bd);
  border-radius: var(--r);
  overflow: hidden;
}
.acc-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--bd);
}
.acc-row:last-child { border-bottom: none; }
.acc-logo {
  width: 28px; height: 28px;
  border-radius: 7px;
  object-fit: contain;
  background: var(--sf2);
  flex: 0 0 auto;
}
.acc-logo-fallback {
  width: 28px; height: 28px;
  border-radius: 7px;
  background: var(--sf2);
  color: var(--tx2);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
  flex: 0 0 auto;
}
.acc-name {
  font-size: 14px;
  font-weight: 600;
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.acc-iban {
  font-size: 12px;
  color: var(--tx2);
  font-variant-numeric: tabular-nums;
  flex: 0 0 auto;
}
.acc-bal {
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  flex: 0 0 auto;
  text-align: right;
}
`;

    const accent = "var(--accent-color, #4ecca3)";
    const chevron = canExpand ? (open ? " ▴" : " ▾") : "";
    const accLabel = accountCount === 1 ? tSync("general.accounts_singular") : tSync("general.accounts_plural");

    const accountsHtml = accounts.map((a) => {
      const name = escHtml(a.name || "");
      const iban = escHtml(a.ibanMasked || "");
      const bal = eur(a.balance);
      const balClass = (a.balance || 0) >= 0 ? "pos" : "neg";
      const logo = a.logo
        ? `<img class="acc-logo" src="${escHtml(a.logo)}" alt="" loading="lazy">`
        : `<div class="acc-logo-fallback">${escHtml((a.institution || a.name || "?").charAt(0).toUpperCase())}</div>`;
      return `
  <div class="acc-row">
    ${logo}
    <span class="acc-name">${name}</span>
    <span class="acc-iban">${iban}</span>
    <span class="acc-bal ${balClass}">${escHtml(bal)}</span>
  </div>`;
    }).join("");

    this.shadowRoot.innerHTML = `
<style>${SHARED_CSS}${LOCAL_CSS}</style>
<div class="stats">
  <div id="balance-wrap"${canExpand ? ` role="button" tabindex="0" aria-expanded="${open}" aria-label="${escHtml(tSync("stats.balance.toggle_accounts"))}"` : ""}>
    <fd-stat-card id="balance"></fd-stat-card>
  </div>
  <fd-stat-card id="expenses"></fd-stat-card>
  <fd-stat-card id="income"></fd-stat-card>
  <fd-stat-card id="savings"></fd-stat-card>
</div>
<div class="accounts-detail${open ? " open" : ""}">
  <div class="acc-list">${accountsHtml}</div>
</div>`;

    const balance = this.shadowRoot.getElementById("balance");
    balance.label = tSync("stats.balance");
    balance.value = eur(totalBalance);
    balance.subtitle = `${accountCount} ${accLabel}${chevron}`;
    balance.accent = accent;
    balance.valclass = totalBalance >= 0 ? "pos" : "neg";

    if (canExpand) {
      const wrap = this.shadowRoot.getElementById("balance-wrap");
      const toggle = () => { this._expanded = !this._expanded; this._render(); };
      wrap.addEventListener("click", toggle);
      wrap.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
    }

    const expenses = this.shadowRoot.getElementById("expenses");
    expenses.label = tSync("stats.expenses");
    expenses.value = eur(totalExp);
    expenses.subtitle = tSync("stats.transactions", { count: txnCount });
    expenses.accent = "var(--dg, #e74c3c)";
    expenses.valclass = "neg";

    const income = this.shadowRoot.getElementById("income");
    income.label = tSync("stats.income");
    income.value = eur(totalInc);
    income.subtitle = tSync("stats.net");
    income.accent = "var(--bl, #3b82f6)";
    income.valclass = "";

    const savings = this.shadowRoot.getElementById("savings");
    savings.label = tSync("stats.savings");
    savings.value = `${savingsRate}%`;
    savings.subtitle = tSync("stats.month_surplus", { amount: `${surplus >= 0 ? "+" : ""}${eur(surplus)}` });
    savings.accent = "var(--pp, #8b5cf6)";
    savings.valclass = "";
  }
  _renderSkeleton() {
    const { SHARED_CSS, tSync } = window._fd;
    const LOCAL_CSS = `
:host { margin-bottom: 20px; }
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 768px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
}
`;
    this.shadowRoot.innerHTML = `
<style>${SHARED_CSS}${LOCAL_CSS}</style>
<div class="stats">
  <fd-stat-card id="balance"></fd-stat-card>
  <fd-stat-card id="expenses"></fd-stat-card>
  <fd-stat-card id="income"></fd-stat-card>
  <fd-stat-card id="savings"></fd-stat-card>
</div>`;
    ["balance", "expenses", "income", "savings"].forEach((id) => {
      const el = this.shadowRoot.getElementById(id);
      if (el) {
        el.label = { balance: tSync("stats.balance"), expenses: tSync("stats.expenses"), income: tSync("stats.income"), savings: tSync("stats.savings") }[id];
        el.setData(null); // triggers skeleton
      }
    });
  }
}

if (!customElements.get("fd-stats-row")) customElements.define("fd-stats-row", FdStatsRow);
