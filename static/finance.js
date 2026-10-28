"use strict";
// Pure, deterministic educational models. All money inputs use EUR.
(function (root) {
  const range = (value, min, max, label) => {
    if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max)
      throw new RangeError(`Check ${label}: use a number from ${min} to ${max}.`);
    return value;
  };
  function project({initial, monthly, years, rate, fee, inflation}) {
    range(initial, 0, 1e7, "starting savings"); range(monthly, 0, 1e5, "monthly saving");
    range(years, 1, 60, "years"); if (!Number.isInteger(years)) throw new RangeError("Use whole years.");
    range(rate, -99, 50, "annual return"); range(fee, 0, 10, "annual fee"); range(inflation, 0, 30, "inflation");
    // Effective annual growth, with a proportional annual fee, converted to monthly.
    const factor = ((1 + rate / 100) * (1 - fee / 100)) ** (1 / 12);
    const grossFactor = (1 + rate / 100) ** (1 / 12);
    let value = initial, gross = initial;
    const rows = [{year: 0, nominal: initial, real: initial, contributed: initial}];
    for (let month = 1; month <= years * 12; month++) {
      value = value * factor + monthly; gross = gross * grossFactor + monthly;
      if (month % 12 === 0) rows.push({year: month / 12, nominal: value,
        real: value / ((1 + inflation / 100) ** (month / 12)), contributed: initial + monthly * month});
    }
    return {...rows.at(-1), feeDrag: gross - value, rows};
  }
  function budget({income, essential, flexible, debt, reserve, months}) {
    for (const [key, value] of Object.entries({income, essential, flexible, debt, reserve})) range(value, 0, 1e7, key);
    range(months, 1, 24, "reserve months");
    const spending = essential + flexible + debt, surplus = income - spending;
    const baseline = essential + debt, target = baseline * months;
    return {surplus, spending, target, gap: Math.max(0, target - reserve),
      coverage: baseline > 0 ? reserve / baseline : null,
      savingRate: income > 0 ? surplus / income * 100 : null};
  }
  function payoff({balance, apr, payment}) {
    range(balance, 0, 1e7, "debt balance"); range(apr, 0, 100, "debt APR"); range(payment, 0, 1e6, "payment");
    if (balance === 0) return {months: 0, interest: 0, total: 0};
    if (payment <= balance * apr / 1200 || payment === 0) return {months: null, reason: "Payment does not cover monthly interest and reduce the balance."};
    let remaining = balance, interest = 0, months = 0;
    while (remaining > 0.0000001 && months < 1200) {
      const cost = remaining * apr / 1200; interest += cost;
      remaining = Math.max(0, remaining + cost - payment); months++;
    }
    if (remaining > 0.0000001) return {months: null, reason: "Payoff exceeds this model’s 100-year limit. Increase the payment."};
    return {months, interest, total: balance + interest};
  }
  function business({fixed, price, variable, units, cash}) {
    for (const [key, value] of Object.entries({fixed, price, variable, units, cash})) range(value, 0, 1e9, key);
    if (!Number.isInteger(units)) throw new RangeError("Use whole sales units.");
    const margin = price - variable, profit = margin * units - fixed;
    return {margin, profit, revenue: price * units,
      breakEven: margin > 0 ? Math.ceil(fixed / margin) : null,
      runway: profit < 0 ? cash / -profit : null};
  }
  const api = {project, budget, payoff, business};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MonelioraFinance = api;
})(globalThis);
