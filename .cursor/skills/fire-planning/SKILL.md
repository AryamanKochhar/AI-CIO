---
name: fire-planning
description: Build an auditable financial-independence goal from spending, earmarked funding, investment willingness, loss capacity and dated deposit terms.
---
# Financial independence and retirement planning

Sources: knowledge/fire_sources.json and knowledge/fd_rate_catalog.json. These are original project notes informed by public primary sources. They are not quotations from a full book, a validated risk questionnaire, a regulated-adviser certification, or proof of future returns. Each quoted principle below is a project-authored rule that the application can resolve to this exact section.

## Define the spending liability

Financial independence is a funded spending plan, not a universal corpus multiple.

Ask for current age, target age, the spending period to plan through, monthly retirement spending in today's rupees, separately dated reliable income, earmarked starting assets, inflation and medical or one-time commitments. Age 65 is a retirement target; do not describe it as early retirement by definition. A user chooses the target age.

Let E0 be monthly spending in today's INR, i an annual inflation scenario and Y years until independence. Annual first-year spending at the target is E = 12 * E0 * (1 + i)^Y. This is an original compound-growth identity, not an inflation forecast. The dates, currency and price basis of reliable income must match before subtracting it. If P is verified annual income in target-date rupees, net annual portfolio spending is D = max(0, E - P). A pension starting later leaves an unfunded bridge and cannot offset spending before it begins. Missing future income must be requested or explicitly set to zero by the user, never inferred from occupation. Sources: fire_sebi_retirement, fire_sebi_inflation, nism_retirement.

## Treat withdrawal rates as scenarios

A withdrawal-rate scenario is not a guaranteed Indian safe rate.

For a chosen positive starting withdrawal fraction w, the comparison corpus C = D / w describes the first year's spending-to-capital ratio. It does not prove that capital supports inflation-adjusted spending for life. Show sensitivities such as different user-selected withdrawal assumptions and planning ages. A constant annual cashflow finite-horizon present-value illustration is a different model: at real net return q and L end-year payments, PV = D * (1 - (1 + q)^(-L)) / q; when q = 0, PV = D * L. This finite annuity consumes capital and fails to protect against longer life or varying returns. Do not label either model as perpetual or guaranteed FIRE.

Morningstar's 2025 study used specific US return, inflation, asset-mix and horizon assumptions. It found a 3.9% starting rate for its 30-year fixed-real-spending base case with a 90% model success criterion. A longer horizon reduced supported starting withdrawals. This context does not supply an Indian safe rate or an AI-CIO success probability. Source: fire_morningstar2025.

## Constrain contributions by consent and capacity

Use the lower of declared investment willingness and uncommitted surplus; never assume all surplus is available.

Normalize verified recurring cashflows to monthly INR. Subtract actual expenses and committed payments once. If recorded expenses already include an EMI, do not subtract it again. Protect the emergency reserve and existing goal contributions. A willingness amount of zero is a valid preference; an absent willingness amount is missing information. Do not replace either with the full surplus. Confirm that willingness means an amount the user wants to contribute to FIRE after other commitments.

For earmarked starting capital A, n end-of-month contributions, annual net nominal accumulation scenario r and monthly equivalent m = (1 + r)^(1/12) - 1, the projected target capital is A * (1 + m)^n + c * ((1 + m)^n - 1) / m. Solving for c gives max(0, (C - A * (1 + m)^n) / (((1 + m)^n - 1) / m)). At m = 0 use max(0, (C - A) / n). Handle n = 0 separately as an immediate funding gap; do not divide by zero. Net return means after the stated fees and tax scenario, not a current FD card rate. The formula assumes constant returns and contributions; it cannot establish actual performance. Sources: nism_retirement, cfa_suitability.

## Respect willingness and loss capacity

A funding gap does not justify increasing risk beyond the investor's stated willingness or financial capacity.

Psychometric answers describe declared preferences. They are not a prediction of behaviour and do not establish income stability, liquidity or ability to absorb a loss. Show the answers or score used, its date, and how the scenario changes. Separate willingness to invest an amount from willingness to accept investment losses. Respect a user's conservative preference even if a higher-risk scenario closes a projected gap.

Portfolio-mix bands, score cutoffs, stress shocks and return assumptions are explicit application policies requiring review; do not attribute their numerical values to CFA, NISM or SEBI. Compare a lower-risk alternative, contribution adjustment, spending adjustment and a later target where relevant. A single score is not sufficient product suitability evidence. Sources: fire_cfa_risk, cfa_suitability.

## Match deposit maturities to cash needs

Today's fixed deposit rate applies only to an eligible deposit booked for its stated term, not to future renewals.

Compare only verified rates for the same currency, amount tier, tenor, resident and age eligibility, access terms, payout basis and verification date. A monthly savings allocation is money to set aside; an FD requires an eligible lump-sum booking, while a recurring deposit is a different contract. Do not pretend future monthly bookings receive today's rate. Reject missing, future-dated or overdue rate evidence and request a fresh quotation. A seven-day review window is application policy, not a bank validity guarantee.

A callable FD can still reduce access through premature-closure terms and lower applicable interest. Gross card rates are not after-tax real returns. Do not use a higher headline yield as the sole reason to choose a bank, infer monthly payout by dividing the card rate by 12, or replace the emergency reserve with a long lock-in. Verify DICGC coverage across eligible deposits at one bank in the same right and capacity, including accrued interest, before discussing available cover. The INR 500000 maximum is not per FD or branch. Sources: fire_sbi_rates, fire_sbi_terms, fire_sbi_senior, fire_hdfc_rates, fire_hdfc_terms, fire_icici_rates, fire_icici_terms, dicgc_guide.

## Earmark assets and contributions once

An emergency reserve or another goal's earmarked assets cannot also be counted toward FIRE.

Use assets explicitly assigned to this goal. A residence occupied by the household is not spendable retirement funding without a separately agreed sale, rent or borrowing plan. Locked or inaccessible assets need an availability date. Do not infer earmarking from total net worth or count an FD both as current assets and future proceeds. Show other goal commitments beside the FIRE budget; missing shared-funding information limits the conclusion. Sources: nism_retirement, fire_sebi_retirement.

## Review outcomes without promising them

A deterministic projection does not measure sequence risk or a probability of success.

With end-period withdrawals, W[t+1] = W[t] * (1 + r[t]) - withdrawal[t]. The order of returns changes the money left to recover after withdrawals. Name this limitation when showing smooth paths. Source verification confirms that a quoted project principle matches its file; it does not confirm the user's inputs, current bank offer, investment suitability or a financial outcome.

Show the inputs, units, dates, arithmetic, selected assumptions, missing evidence, alternatives and a next review trigger. Revisit the goal after a material change in income, spending, health, household needs or risk preferences. If the plan has a gap, report the gap and feasible alternatives. Do not silently raise return assumptions, claim a probability from ranking scores, or recommend an automatic trade. Sources: fire_morningstar2025, nism_retirement.
