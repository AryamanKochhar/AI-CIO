"use client";

import { useId } from "react";

/** Original artwork. Accessories mean recorded information, never investment performance. */
export function CompanionArt({
  known = {},
  className = "",
  decorative = false,
}: {
  known?: Record<string, boolean>;
  className?: string;
  decorative?: boolean;
}) {
  const uid = useId().replace(/:/g, "");
  const count = [
    "psychometric",
    "income",
    "liquid",
    "goals",
    "portfolio",
  ].filter((key) => known[key]).length;
  return (
    <svg
      viewBox="0 0 380 340"
      className={className}
      role={decorative ? undefined : "img"}
      aria-hidden={decorative || undefined}
      aria-label={
        decorative
          ? undefined
          : `Milo, your financial companion, with ${count} information accessories`
      }
    >
      <defs>
        <radialGradient id={`${uid}-halo`}>
          <stop stopColor="#bceee3" stopOpacity=".8" />
          <stop offset="1" stopColor="#d8f5ee" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${uid}-body`} x1=".2" y1="0" x2=".8" y2="1">
          <stop stopColor="#38b8a9" />
          <stop offset=".55" stopColor="#188e88" />
          <stop offset="1" stopColor="#0b646b" />
        </linearGradient>
        <linearGradient id={`${uid}-face`} x1="0" y1="0" x2=".7" y2="1">
          <stop stopColor="#f3fff9" />
          <stop offset="1" stopColor="#bde9dd" />
        </linearGradient>
        <linearGradient id={`${uid}-bag`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#f7c579" />
          <stop offset="1" stopColor="#d9943e" />
        </linearGradient>
        <linearGradient id={`${uid}-book`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#7199df" />
          <stop offset="1" stopColor="#3c5f9d" />
        </linearGradient>
      </defs>
      <circle cx="190" cy="169" r="166" fill={`url(#${uid}-halo)`} />
      <circle
        cx="190"
        cy="171"
        r="130"
        fill="none"
        stroke="#82c7b9"
        strokeOpacity=".22"
        strokeDasharray="3 9"
      />
      <circle
        cx="190"
        cy="171"
        r="103"
        fill="none"
        stroke="#93d4c6"
        strokeOpacity=".22"
      />
      <g className="companion-sparkles" fill="#72b4a9">
        <circle cx="64" cy="124" r="4" />
        <circle cx="300" cy="87" r="3" />
        <circle cx="319" cy="215" r="4" />
        <path
          d="M85 65v12m-6-6h12M296 265v14m-7-7h14"
          stroke="#8bbcc8"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </g>
      <ellipse cx="190" cy="302" rx="89" ry="12" fill="#134c5e" opacity=".12" />
      <g className="companion-float">
        <path
          d="M151 251l-8 31q-2 12 12 13h16q7-2 5-10l-4-31M207 254l-2 30q0 10 11 10h14q12-1 9-11l-9-31"
          fill="#15394d"
        />
        <path
          d="M148 186q-31 4-40 34-3 14 8 17 10 4 16-9l22-16M232 188q29 3 39 29 5 13-6 17-10 3-15-7l-22-16"
          fill={`url(#${uid}-body)`}
          stroke="#0c797b"
          strokeWidth="2"
        />
        <path
          d="M130 186q-14 22-9 48 6 36 63 39 60 3 75-33 8-24-8-55z"
          fill={`url(#${uid}-body)`}
        />
        <path
          d="M142 237q42 25 95 0"
          fill="none"
          stroke="#89d6c8"
          strokeOpacity=".32"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <path
          d="M183 54q-8-16 1-27 14 5 13 24"
          fill="#20998d"
          stroke="#117d78"
          strokeWidth="2"
        />
        <path
          d="M192 53q6-22 24-18 1 18-22 24"
          fill="#77cabc"
          stroke="#278e85"
          strokeWidth="2"
        />
        <ellipse cx="111" cy="131" rx="16" ry="23" fill="#168c87" />
        <ellipse cx="268" cy="131" rx="16" ry="23" fill="#168c87" />
        <path
          d="M111 106q4-53 80-53 73 0 80 56l-1 44q-6 57-79 61-75-3-82-60z"
          fill={`url(#${uid}-body)`}
          stroke="#0e7778"
          strokeWidth="2.5"
        />
        <path
          d="M126 111q2-38 64-39 63 0 65 40v34q-4 47-65 51-61-4-65-50z"
          fill={`url(#${uid}-face)`}
        />
        <path
          d="M136 99q17-17 42-18"
          fill="none"
          stroke="white"
          strokeWidth="4"
          strokeLinecap="round"
          opacity=".7"
        />
        <g className="companion-eyes">
          <ellipse cx="157" cy="131" rx="12" ry="17" fill="#143b4f" />
          <ellipse cx="221" cy="131" rx="12" ry="17" fill="#143b4f" />
          <circle cx="160" cy="125" r="4" fill="#fff" />
          <circle cx="224" cy="125" r="4" fill="#fff" />
          <circle cx="154" cy="139" r="2" fill="#9bd3d0" />
          <circle cx="218" cy="139" r="2" fill="#9bd3d0" />
        </g>
        <ellipse cx="139" cy="155" rx="12" ry="6" fill="#eeb7a1" opacity=".5" />
        <ellipse cx="240" cy="155" rx="12" ry="6" fill="#eeb7a1" opacity=".5" />
        <path
          d="M174 162q16 14 32-1"
          fill="none"
          stroke="#164b55"
          strokeWidth="4"
          strokeLinecap="round"
        />
        {known.psychometric ? (
          <g className="companion-accessory">
            <rect
              x="132"
              y="108"
              width="49"
              height="43"
              rx="17"
              fill="#8cc7d2"
              fillOpacity=".12"
              stroke="#2e5a77"
              strokeWidth="4"
            />
            <rect
              x="198"
              y="108"
              width="49"
              height="43"
              rx="17"
              fill="#8cc7d2"
              fillOpacity=".12"
              stroke="#2e5a77"
              strokeWidth="4"
            />
            <path
              d="M181 126q8-5 17 0M125 120h7m115 0h8"
              fill="none"
              stroke="#2e5a77"
              strokeWidth="4"
            />
          </g>
        ) : null}
        <path
          d="M147 204q43 14 86-1"
          fill="none"
          stroke="#d6eee3"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {known.income ? (
          <g className="companion-accessory">
            <path d="M159 204l-39 54" stroke="#b97c3e" strokeWidth="6" />
            <rect
              x="92"
              y="232"
              width="55"
              height="41"
              rx="12"
              fill={`url(#${uid}-bag)`}
              stroke="#b87f3e"
              strokeWidth="2"
            />
            <path
              d="M92 245q26 11 55 0"
              fill="none"
              stroke="#ffe2a8"
              strokeWidth="3"
            />
            <rect
              x="114"
              y="244"
              width="10"
              height="11"
              rx="3"
              fill="#fff3d1"
            />
          </g>
        ) : null}
        {known.liquid ? (
          <g className="companion-accessory">
            <path
              d="M237 213l21 7v16q-3 14-21 23-18-9-21-23v-16z"
              fill="#d3e6f2"
              stroke="#43799a"
              strokeWidth="2"
            />
            <path
              d="M228 235l6 6 11-14"
              fill="none"
              stroke="#43799a"
              strokeWidth="3"
              strokeLinecap="round"
            />
          </g>
        ) : null}
        {known.goals ? (
          <g className="companion-accessory">
            <circle
              cx="189"
              cy="224"
              r="15"
              fill="#ffedc7"
              stroke="#c7923f"
              strokeWidth="2"
            />
            <path d="M194 214l-2 13-9 7 2-13z" fill="#b77b35" />
            <circle cx="188" cy="224" r="2" fill="#fff" />
          </g>
        ) : null}
        {known.portfolio ? (
          <g className="companion-accessory" transform="rotate(10 297 167)">
            <rect
              x="270"
              y="132"
              width="54"
              height="68"
              rx="10"
              fill={`url(#${uid}-book)`}
              stroke="#3a628e"
              strokeWidth="2"
            />
            <path d="M282 133v66" stroke="#bdd7ed" strokeWidth="2" />
            <rect
              x="290"
              y="146"
              width="24"
              height="15"
              rx="4"
              fill="#d6e9f6"
            />
            <path
              d="M291 171h20m-20 8h14m-14 8h18"
              stroke="#d6e9f6"
              strokeWidth="3"
              strokeLinecap="round"
            />
            <path
              d="M279 128v9m12-9v9m12-9v9"
              stroke="#234e6f"
              strokeWidth="3"
              strokeLinecap="round"
            />
          </g>
        ) : null}
      </g>
    </svg>
  );
}
