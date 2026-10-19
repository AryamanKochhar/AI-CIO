/** Public product identity. Keep package, API and database identifiers independent. */
const PRODUCT_NAME = "AI-cio";
const PRODUCT_PROVIDER = "Orbix";

export const BRAND = {
  name: PRODUCT_NAME,
  provider: PRODUCT_PROVIDER,
  attribution: `Powered by ${PRODUCT_PROVIDER}`,
  description: `Your personal financial decision companion. Build your financial twin, compare insights and plan your next step. Powered by ${PRODUCT_PROVIDER}.`,
  mark: "/brand/ai-cio-mark.svg",
  wordmark: "/brand/ai-cio-logo.svg",
  themeColor: "#0b1f3a",
  backgroundColor: "#f5f8fc",
} as const;
