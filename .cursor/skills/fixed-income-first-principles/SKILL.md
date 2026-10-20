---
name: fixed-income-first-principles
description: Review bond cashflows, discounting and credit, liquidity, rate and reinvestment risks without confusing bonds and deposits.
---
# Fixed-income cashflows and risks

Source: sebi_bond_risks in knowledge/finance_sources.json. Original educational explanation, not a current price, rating or credit opinion.

## Start from promised cashflows
A plain fixed-rate bond promises coupons and principal, subject to issuer performance. In a simplified constant-yield model, price = sum(C[t] / (1 + y)^t) + face / (1 + y)^T. For fixed positive payments, increasing the discount rate lowers present value. Quote frequency and units must match; accrued interest and clean/dirty price conventions matter. Coupon rate is not yield to maturity or total return.

## Separate the failure channels
Default changes whether payments arrive. Rate changes alter resale value. Thin liquidity affects exit price. A call can end future coupons and create reinvestment risk. A credit rating is an opinion that may change, not a promise of payment. Maturity held without default does not eliminate purchasing-power or opportunity costs.

## Compare only the actual instrument
Request issuer, security identifier, cashflow schedule, maturity, call terms, executable price, accrued interest and account restrictions before comparing yields. A bond, debt fund and bank FD have different cashflows and access terms. Do not apply bank deposit insurance to a bond. Do not estimate duration, credit loss or executable liquidity from a product label.
