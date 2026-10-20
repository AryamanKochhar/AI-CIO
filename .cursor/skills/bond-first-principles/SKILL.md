---
name: bond-first-principles
description: Verify bond identity, contractual cashflows, price conventions and financial-Twin suitability before publishing a bond comparison.
---

# Bond first principles

This is an original condensed project guide. It is not a full book, official endorsement, execution instruction or guarantee. Use dated official issue terms and actual provider evidence; educational references do not establish an investor's facts.

## Verify the exact instrument

A broker catalogue identifies a security but does not verify its contractual cashflows or present liquidity.

Resolve exact ISIN and exchange routing. A broker's EQUITY enum can carry government debt or SGBs. Do not infer an asset's economic or tax classification from that routing enum, a name substring or an empty derivative-expiry field.

## Price dated contractual cashflows

Use verified payment dates, face value, redemption rules and day-count conventions before calculating settlement cash or yield.

Keep clean and dirty pricing separate. NSE capital-market government securities and SGBs trade on dirty terms; accrued interest must not be added twice. Unsupported irregular coupons, floating coupons or embedded options require a separate model. Price observations do not establish settlement dates or costs.

## Separate coupon from yield

Coupon rate is not yield to maturity, total return or a guaranteed reinvestment rate.

Match yield convention, dates and price basis. A bill's simple annualized holding return is not a coupon bond's nominal semiannual yield. Contractual cashflows remain subject to payment and reinvestment assumptions.

## Explain rate sensitivity

A sovereign credit classification does not remove market-price, duration, inflation or reinvestment risk.

Use modified duration, DV01 and convexity only within the supported cashflow model. Rate shocks are illustrative sensitivity scenarios, not probabilities. A fixed-rate coupon and maturity do not guarantee a realized return if sold early.

## Verify an executable price

A last traded price without a recent trade and positive market depth does not establish an executable offer.

Record quote receipt time separately from last trade time, inspect both sides and size, and state price units. Even visible depth does not guarantee a fill or future exit. Never substitute zero or a stale close for an unavailable quote.

## Respect the whole financial Twin

Match bond maturity and liquidity to the selected goal, loss capacity, declared willingness and one confirmed shared investment budget.

Psychometric comfort cannot create financial capacity. A common surplus ceiling is not a separate allocation for every specialist or goal. Protect emergency liquidity; use hypothetical product comparisons without amounts until a specific allocation and costs are confirmed centrally.

## Separate gold from nominal debt

An SGB has gold-linked redemption; do not treat its future rupee principal as a fixed cashflow or an FD substitute.

Calculate the tranche coupon on verified original nominal value, not the secondary purchase price. Gold scenarios must state their hypothetical redemption basis. Do not invent a fixed YTM for an unknown future gold price.

## Establish current tax conditions

Do not infer a tax exemption from an SGB name; verify the current rule, acquisition route, ownership continuity and disposal event.

For tax year 2026–27 onward, verify Section 70(1)(x) conditions against the actual lot. A secondary-market purchase or premature redemption is not automatically exempt. Unknown costs and unsupported tax calculations stay unevaluated; current realized portfolio tax is not a proposed bond trade's tax.

## Scoped sources

- bond_rbi_primer: RBI Government Securities Market in India — A Primer.
- bond_rbi_retail_direct: RBI Retail Direct Scheme FAQ; verify dates and route-specific conditions.
- bond_rbi_sgb: RBI SGB FAQ, product mechanics; its 2019 tax text is not current tax authority.
- bond_sebi_bonds: SEBI Investor, Understanding Bonds.
- bond_cfa_duration: CFA Institute 2026 public duration overview; not the paywalled full curriculum.
- bond_cfa_convexity: CFA Institute 2026 public convexity overview; not the paywalled full curriculum.
- bond_nse_sgb_dirty: NSE CMTR32540, SGB dirty pricing; check subsequent amendments.
- bond_tax_2026: Income Tax Department, current Section 70(1)(x).

Exact official URLs and review dates belong in the shared finance source manifest. Display only the principles actually applied to verified facts.
