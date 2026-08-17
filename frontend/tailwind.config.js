module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Public-site tokens (session 9 portal restyle) — the portal is now
        // light-themed to match the public marketing site.
        cream: "#FAF8F4",  // page bg
        sand: "#F1EBE0",   // subtle raise (hover states, secondary tint)
        dune: "#E9E1D2",   // borders, dividers
        ink: "#17140F",    // primary text / primary CTA
        coal: "#141210",   // active/pressed state on ink CTAs
        accent: "#0E7490", // reserved portal accent (active nav, focus rings,
                           // "in progress" status). Accessible on cream.

        // Legacy dark tokens — kept ONLY for the /admin/security page
        // (user directive c2: back-of-house stays dark). Do NOT use for
        // new client-facing surfaces.
        surface: "#121214",
        raise: "#18181b",
        line: "#27272a",
        warn: "#FFB020",
        ok: "#00D26A",
      },
      fontFamily: {
        // Aligned with public site (session 9 restyle).
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
