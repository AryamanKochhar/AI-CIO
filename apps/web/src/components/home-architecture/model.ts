/** Static architecture copy. Actual execution and applied evidence live in Decisions. */
export type AgentId = "equity" | "mutual-funds" | "bonds" | "tax" | "fd" | "goals";

export type ArchitectureReference = { label: string; url: string };
export type ArchitectureSkill = { name: string; principle: string };

export type ArchitectureAgent = {
  id: AgentId;
  name: string;
  eyebrow: string;
  description: string;
  outputs: [string, string];
  receives: [string, string, string];
  sends: [string, string, string];
  skills: ArchitectureSkill[];
  references: ArchitectureReference[];
  referenceCount: number;
  href: string;
};

export const architectureAgents: ArchitectureAgent[] = [
  {
    id: "equity",
    name: "Equity & portfolio",
    eyebrow: "Exposure & suitability",
    description: "Connect holdings and dated market evidence to your risk limits.",
    outputs: ["Holding and sector exposure", "Market indicators and risk findings"],
    receives: ["Holdings and portfolio metrics", "Goals, finances and risk profile", "Available dated market evidence"],
    sends: ["Portfolio analysis and observations", "Candidate strategies and constraints", "Evidence gaps and conditional actions"],
    skills: [
      { name: "Equity analysis", principle: "Price and technical indicators do not establish business value." },
      { name: "Portfolio principles", principle: "An equity finding must fit your horizon, liquidity and loss capacity." },
    ],
    references: [
      { label: "NISM · Research Analyst objectives", url: "https://www.nism.ac.in/test-objectives-research-analyst-w-e-f-january-20-2026" },
      { label: "CFA Institute · Financial analysis", url: "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/financial-analysis-techniques" },
      { label: "NSE · Company filings", url: "https://www.nseindia.com/companies-listing/corporate-filings-application?id=equity" },
    ],
    referenceCount: 6,
    href: "/decisions?objective=review_equity_portfolio",
  },
  {
    id: "mutual-funds",
    name: "Mutual funds",
    eyebrow: "Growth & diversification",
    description: "Look through fund names to performance, shared holdings and costs.",
    outputs: ["NAV growth and benchmark comparisons", "Holdings overlap and return correlation"],
    receives: ["Exact fund identities and values", "Goals, risk profile and budget", "Dated NAVs and AMC disclosures"],
    sends: ["Fund statistics and source coverage", "Combined underlying exposure", "Supported findings and switch checks"],
    skills: [
      { name: "Mutual fund analysis", principle: "Compare the correct plan, period and benchmark before judging a fund." },
      { name: "Portfolio principles", principle: "More fund names do not ensure diversification; examine overlap and correlation." },
    ],
    references: [
      { label: "NISM · Mutual fund objectives", url: "https://www.nism.ac.in/test-objectives-mutual-fund-distributors" },
      { label: "AMFI · Portfolio disclosures", url: "https://www.amfiindia.com/online-center/portfolio-disclosure" },
      { label: "CFA Institute · Performance evaluation", url: "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-performance-evaluation" },
    ],
    referenceCount: 7,
    href: "/mutual-funds",
  },
  {
    id: "bonds",
    name: "Bonds & government securities",
    eyebrow: "Cashflows & maturity",
    description: "Compare verified G-sec, Treasury bill and SGB terms with your goals.",
    outputs: ["Sourced instrument terms and maturities", "Conditional yield and liquidity checks"],
    receives: ["Holdings and selected goal dates", "Risk, reserve needs and shared budget", "Dhan catalogue plus verified issue terms"],
    sends: ["Sourced product comparisons", "Quote and suitability readiness", "Conditional alternatives and exclusions"],
    skills: [
      { name: "Bond first principles", principle: "Coupon is not yield; verify cashflows, settlement and a usable price." },
      { name: "Portfolio principles", principle: "Match maturity to cash needs; SGB redemption remains linked to gold." },
    ],
    references: [
      { label: "RBI · Government securities primer", url: "https://www.rbi.org.in/Scripts/FAQView.aspx?Id=79" },
      { label: "RBI · Retail Direct", url: "https://www.rbi.org.in/Scripts/FAQView.aspx?Id=145" },
      { label: "SEBI · Understanding bonds", url: "https://investor.sebi.gov.in/understanding_bonds.html" },
    ],
    referenceCount: 8,
    href: "/bonds",
  },
  {
    id: "tax",
    name: "Tax",
    eyebrow: "Period & transaction coverage",
    description: "Explain tax estimates within the records and asset classes actually supported.",
    outputs: ["Scoped gains and holding-period analysis", "Tax coverage and opportunity flags"],
    receives: ["Recorded holdings and transactions", "Instrument identity and acquisition dates", "Applicable income period and rules"],
    sends: ["Supported estimates and their scope", "Excluded or incomplete records", "Tax context for proposed reviews"],
    skills: [
      { name: "Tax period & classification", principle: "Establish the period and instrument class before applying a tax rule." },
      { name: "Portfolio principles", principle: "Visible realized tax is not the cost of a proposed fund switch." },
    ],
    references: [
      { label: "Income Tax Department · Applicable Act", url: "https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/objective-and-scope-new-act-faq" },
      { label: "Income Tax Department · Loss set-off", url: "https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/set%20off/carry%20forward%20of%20losses%20-faq" },
      { label: "Income Tax Department · AIS", url: "https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/ais-annual-information-statement" },
    ],
    referenceCount: 6,
    href: "/tax",
  },
  {
    id: "fd",
    name: "Fixed deposits",
    eyebrow: "Terms & liquidity",
    description: "Review your deposits alongside dated, eligible bank terms.",
    outputs: ["Deposit maturities and liquidity alerts", "Dated bank product comparisons"],
    receives: ["Recorded deposits and booked rates", "Liquid cash and access needs", "Official tenor-specific bank terms"],
    sends: ["Deposit summary and maturity alerts", "Comparable offers and eligibility gaps", "Liquidity implications for actions"],
    skills: [
      { name: "FD comparison", principle: "Compare the same tenor, payout basis and eligibility before comparing rates." },
      { name: "Portfolio principles", principle: "Preserve needed liquidity before locking money into a deposit." },
    ],
    references: [
      { label: "DICGC · Deposit insurance", url: "https://www.dicgc.org.in/guide-to-deposit-insurance" },
      { label: "RBI · Deposit interest FAQ", url: "https://www.rbi.org.in/commonman/Upload/English/FAQs/PDFs/FAQIRD01042025.pdf" },
      { label: "CFA Institute · Interest rate risk", url: "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/interest-rate-risk-and-return" },
    ],
    referenceCount: 6,
    href: "/fd",
  },
  {
    id: "goals",
    name: "Goals & FIRE",
    eyebrow: "Funding & time",
    description: "Test the path from your agreed contributions to future needs.",
    outputs: ["Goal scenarios and funding gaps", "FIRE spending and contribution plan"],
    receives: ["Goal targets, dates and saved assumptions", "Income, expenses and agreed contributions", "Risk willingness and financial capacity"],
    sends: ["Illustrative projections and gaps", "Contribution needs and constraints", "Trajectory or saved FIRE calculation"],
    skills: [
      { name: "Trajectory principles", principle: "Separate scenario assumptions from forecasts and outcome probabilities." },
      { name: "FIRE planning", principle: "Test inflation, spending and contribution limits without adding assets twice." },
    ],
    references: [
      { label: "SEBI · Retirement planning", url: "https://investor.sebi.gov.in/moneymatters-planforearlyretire.html" },
      { label: "NISM · Retirement objectives", url: "https://www.nism.ac.in/test-objectives-retirement-adviser" },
      { label: "CFA Institute · Suitability", url: "https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-iii-c" },
    ],
    referenceCount: 6,
    href: "/fire",
  },
];

export type OrchestrationStageId = "prepare" | "dispatch" | "reconcile" | "validate" | "publish";

export type OrchestrationStage = {
  id: OrchestrationStageId;
  label: string;
  short: string;
  description: string;
  receives: [string, string];
  checks: [string, string, string];
  sends: [string, string];
  modelNote: string;
};

export const orchestrationStages: OrchestrationStage[] = [
  {
    id: "prepare",
    label: "Prepare one snapshot",
    short: "Twin + objective + shared budget",
    description: "Assemble your financial Twin, select the decision objective and set the constraints every specialist must share.",
    receives: ["Your objective and recorded financial state", "Declared budget, goal and reserve commitments"],
    checks: ["One user-scoped financial snapshot", "Budget bounded by income minus expenses", "Other goals and reserve commitments confirmed"],
    sends: ["Independent copies of the same Twin", "Objective and one contribution policy"],
    modelNote: "Snapshot assembly and budget calculations are deterministic; no model is needed.",
  },
  {
    id: "dispatch",
    label: "Run specialists in parallel",
    short: "Six independent perspectives",
    description: "Equity, funds, bonds, tax, deposits and goals review their own scope together, using the same financial starting point.",
    receives: ["Shared Twin and decision constraints", "Relevant source and market evidence"],
    checks: ["Workers receive separate snapshot copies", "Unavailable sources remain explicit", "Database sessions stay outside workers"],
    sends: ["Specialist results and evidence coverage", "Findings, calculations and constraints"],
    modelNote: "Equity may use a configured model for equity or what-if reviews when holdings exist, with a deterministic fallback. The other specialists calculate deterministically. FIRE uses a saved goal planner and a recorded equity-exposure review.",
  },
  {
    id: "reconcile",
    label: "Reconcile the whole picture",
    short: "Join findings; resolve constraints",
    description: "Bring the specialist results together before suggesting any action, keeping cash, assets, costs and goals coherent.",
    receives: ["Joined specialist findings and source coverage", "Shared contribution and goal constraints"],
    checks: ["One budget across competing alternatives", "Fund-switch tax and cost coverage", "Bond quantity, price and suitability gates"],
    sends: ["Reconciled strategy and goal context", "Supported alternatives and unresolved gaps"],
    modelNote: "Cross-agent budget and readiness checks do not depend on model opinion. FIRE context does not add existing assets again or replace saved return assumptions.",
  },
  {
    id: "validate",
    label: "Apply skills and validate",
    short: "Evidence → principle → action",
    description: "Link supported facts to exact skill sections, check the authored proof and rank distinct, useful actions.",
    receives: ["Reconciled facts, calculations and constraints", "Relevant authored financial principles"],
    checks: ["Strategy amounts and request constraints", "Exact skill sections, file hashes and proof integrity", "Supported arithmetic and repeated actions"],
    sends: ["Focused findings with cited principles", "Deterministic priorities and qualifications"],
    modelNote: "A registered source is not proof it was applied. Accepted findings identify the exact principle used; integrity checks do not guarantee provider accuracy or future results.",
  },
  {
    id: "publish",
    label: "Explain and publish",
    short: "Focused decisions + audit trail",
    description: "Publish the coherent result with its actions, assumptions, source links and recorded execution checks.",
    receives: ["Accepted finding proofs and specialist statuses", "Shared budget policy and final constraints"],
    checks: ["Final strategy constraints remain satisfied", "Optional explanation uses allowed finding IDs", "Model text cannot replace amounts or actions"],
    sends: ["Decision cards and practical next steps", "Sources, applied skills and execution receipts"],
    modelNote: "An optional central model explains validated findings; unsupported explanations are rejected. What-if reviews may also explain calculated scenarios. FIRE uses its deterministic saved plan without central model synthesis.",
  },
];

export const sharedSkills: ArchitectureSkill[] = [
  { name: "Count exposure once", principle: "Look through fund holdings without adding the value of those holdings to the fund value again." },
  { name: "Assess the whole portfolio", principle: "Combine weights, overlap and correlation with your goals, liquidity and ability to bear loss." },
  { name: "Reconcile one shared budget", principle: "Specialist proposals share the same cash ceiling; resolve unsupported amounts and conflicting assumptions before ranking." },
];

export const sharedReferences: ArchitectureReference[] = [
  { label: "CFA Institute · Portfolio planning", url: "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/basics-of-portfolio-planning-and-construction" },
  { label: "CFA Institute · Portfolio risk and return", url: "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-risk-return-part-1" },
  { label: "CFA Institute · Performance evaluation", url: "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-performance-evaluation" },
];
