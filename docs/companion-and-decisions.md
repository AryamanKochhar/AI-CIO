# Companion and decision experience

This follow-up improves the repository UI while keeping the financial calculations and evidence sources in their existing services.

## Milo, the financial companion

Milo is original SVG artwork implemented in `companion-art.tsx`: a rounded explorer with expressive eyes, a soft teal silhouette and a small set of useful accessories. There are no generated image assets or external illustration dependencies. Unique SVG gradient IDs support multiple companions on a page.

The real companion reflects saved Twin completeness, rather than screen position or assumed answers:

| Recorded information | Accessory | Meaning |
| --- | --- | --- |
| Psychometric assessment | Thoughtful lenses | Decision behaviour is recorded. |
| Income | Everyday satchel | Income information is available. |
| Liquid savings | Reserve badge | Accessible cash has been recorded, not judged sufficient. |
| Goals | Goal compass | A direction has been supplied. |
| Portfolio | Portfolio notebook | Investment holdings are available. |

The six visual stages range from an initial hello to all five areas connected. The home page and welcome screen offer an interactive preview, explicitly labelled as an illustration rather than saved user data. Changing its stage never changes the profile. The actual Twin page has an accessory checklist and a contextual CTA for the next missing information area; a complete profile links to Decisions.

The form pages use a compact companion, preserving space for the current question. Subtle floating, blinking and accessory arrival animations respect `prefers-reduced-motion`. Information progress is labelled separately from financial health. The interface does not reward investment risk, profitable outcomes or higher portfolio values with character upgrades.

## Transparent demo profiles

The home page retains Tom, Maya and Arjun as selectable synthetic personas. Cards now distinguish their life context, occupation, goal and horizon. The selected profile shows income, expenses and liquid savings, with a direct launch action. The full fixed-answer table remains expanded by default, contains all 18 responses, supports keyboard scrolling and clearly labels the synthetic confidence and response time. Tom's IAS occupation is explicitly interpreted as Indian Administrative Service.

## From a question to a useful next step

The Decisions setup places the question first, followed by goal selection and the primary run action. Full input details and statement history are available as optional disclosures. DOM order matches visual order for keyboard users. Goal copy describes funding projections under assumptions, rather than a calibrated chance of success.

The result leads with its key takeaway, with trajectory as supporting context. Top-level actions let the user change focus, refresh or move into a what-if review. Three navigation cards link directly to priorities, outlook and the evidence trail. Ranked cards identify the first review, evidence source, relative support, supporting facts and a contextual next action. The methodology remains inspectable and explains that support percentages are review priorities, not investment odds.

The evidence section has its own anchor and explanation. Specialist views, scenarios, goal projections, data quality, trace and detailed assumptions remain available. The shared journey shows the current page and links among the Twin, Decisions, Tax and FDs.

## Cache integration

The page uses `useDecisionWorkspace(userId, objective)` to fetch the Twin and server-validated saved decision independently. Both user and objective are included in decision query keys. Successful runs call `recordDecision`. A stale saved result clears the previous result and returns to setup; an in-progress new request stays in its running state. A small status line identifies revalidation. Background cache updates do not interrupt a person who is changing the decision setup. A manually cleared goal selection is preserved during Twin revalidation.

The cache provider controls session boundaries, mutation invalidation and the bounded Twin snapshot. A saved result from another objective cannot replace an open what-if result. These changes do not add production authentication to the repository's original account model.

## Review evidence

Initial real-browser design checks covered the public home, the complete synthetic Tom Twin, the Decisions setup and a 390-pixel mobile home. No horizontal overflow was observed at 1280 or 390 pixels. The implementation passed a frontend typecheck and lint. Final project gates, real decision runs and the screenshot gallery are recorded separately by the delivery validation workflow; screenshots use synthetic personas only.

Final review: all project gates passed (206 backend tests passed, 4 skipped; 8 frontend tests passed; typecheck, lint and production build passed). A single live synthetic review used the configured equity agent and AI narrative, with no reported equity fallback. Its eight support shares summed to 100.00. The brief appeared in 39.72 seconds on the initial run and 1.41 seconds after a hard reload. The browser recorded no page errors or mobile horizontal overflow; reduced-motion animation was `none`, and all 18 fixed-answer rows supported keyboard access. See the [reviewed gallery](screenshots/README.md) and its [machine-readable checks](screenshots/ui-checks.json).
