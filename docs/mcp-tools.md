# MCP tools

Tools read canonical PostgreSQL. Pass `user_id` when more than one user exists, or set `AICIO_USER_ID`. Holdings default to the user's latest CAS document; pass `document_id` to read an earlier statement. Raw CAS page text is never returned.

## `get_holdings`

Returns AMC, fund, folio, ISIN, closing units, NAV, reported valuation, valuation date, and source page. Use it for “What are my holdings?”

## `get_portfolio_summary`

Returns total value, AMC/fund allocations, top holdings, and concentration measurements: largest holding, top three, top five, and largest AMC percentages. Use it for total-value and exposure questions.

## `get_transactions`

Accepts optional `start_date`, `end_date`, `fund`, `amc`, and `transaction_type` filters. Original descriptions and normalized event types are both returned.

## `get_sips`

Returns SIP activity and separates failed payments from successful SIP purchases. Use it for “Which SIP payments failed?”

## `search_knowledge`

Performs local keyword matching over `knowledge/*.md`. The results are general education, not individual recommendations.

## `get_source`

Accepts a one-based CAS page number and returns the holdings linked to that page. Raw source is intentionally not exposed.

## `get_behavioral_profile`

Returns the stored psychometric profile for a user (latest completed session, or `session_id` if provided). Includes explicit score polarity. Does not re-score and does not include raw answers.
