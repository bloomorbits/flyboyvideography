// Shared client-side package catalogue for /book — mirrors /app/backend/packages.py.
// If you edit prices here you MUST update both files (see PRD schema-mirror rule).
export const BOOKABLE_PACKAGES = [
  {
    id: "wedding",
    title: "Wedding Videography",
    tiers: [
      { name: "Basic",   price: 250, coverage: "3 hours coverage" },
      { name: "Classic", price: 400, coverage: "6 hours coverage" },
      { name: "Royale",  price: 700, coverage: "Full-day coverage (10–12 hours)" },
    ],
  },
  {
    id: "birthday",
    title: "Birthday Celebration",
    tiers: [
      { name: "Basic",   price: 250, coverage: "3 hours coverage" },
      { name: "Classic", price: 400, coverage: "6 hours coverage" },
      { name: "Royale",  price: 700, coverage: "Full-day coverage (10–12 hours)" },
    ],
  },
  {
    id: "naming-ceremony",
    title: "Naming Ceremony & Gender Reveal",
    tiers: [
      { name: "Basic",   price: 200, coverage: "2 hours coverage" },
      { name: "Classic", price: 300, coverage: "4 hours coverage" },
      { name: "Royale",  price: 450, coverage: "6 hours coverage" },
    ],
  },
  {
    id: "lifestyle",
    title: "Lifestyle Shoot",
    tiers: [
      { name: "Basic",   price: 200, coverage: "2 hours coverage" },
      { name: "Classic", price: 300, coverage: "4 hours coverage" },
      { name: "Royale",  price: 450, coverage: "6 hours coverage" },
    ],
  },
  // Single-tier packages get one tier with name "" so the (packageId, tierName)
  // contract is uniform across single- and multi-tier bookings.
  {
    id: "graduation",
    title: "Graduation Reels",
    tiers: [
      { name: "",  price: 150, coverage: "1.5 hours coverage" },
    ],
  },
];

export const DEPOSIT_PERCENTAGE = 0.5;

export function findPackage(id) {
  return BOOKABLE_PACKAGES.find((p) => p.id === id) || null;
}

export function findTier(packageId, tierName) {
  const pkg = findPackage(packageId);
  if (!pkg) return { pkg: null, tier: null };
  const tier = pkg.tiers.find((t) => t.name === (tierName ?? "")) || null;
  return { pkg, tier };
}
