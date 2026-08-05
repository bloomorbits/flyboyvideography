export const packages = [
  {
    id: "wedding",
    title: "Wedding Videography",
    tiers: [
      {
        name: "Basic",
        price: 250,
        coverage: "3 hours coverage",
        features: [
          "Pre-event consultation",
          "1 highlight film (60–90 seconds)",
          "High-resolution delivery",
          "Delivered within 7 days",
        ],
      },
      {
        name: "Classic",
        price: 400,
        coverage: "6 hours coverage",
        popular: true,
        leadIn: "Everything in Basic, plus:",
        features: [
          "An additional 3–5 minute cinematic highlight film (alongside your 60–90 second social reel)",
          "Key moments captured — ceremony, speeches, cake cutting, and more",
          "Online gallery delivery",
        ],
      },
      {
        name: "Royale",
        price: 700,
        coverage: "Full-day coverage (10–12 hours)",
        leadIn: "Everything in Classic, plus:",
        features: [
          "Extended full-day coverage",
          "A third film — a 5–8 minute highlight film",
          "Delivered within 7–14 days",
        ],
      },
    ],
  },
  {
    id: "birthday",
    title: "Birthday Celebration",
    tiers: [
      {
        name: "Basic",
        price: 250,
        coverage: "3 hours coverage",
        features: [
          "Pre-event consultation",
          "1 highlight film (60–90 seconds)",
          "High-resolution delivery",
          "Delivered within 7 days",
        ],
      },
      {
        name: "Classic",
        price: 400,
        coverage: "6 hours coverage",
        popular: true,
        leadIn: "Everything in Basic, plus:",
        features: [
          "An additional 3–5 minute cinematic highlight film",
          "Key moments captured — cake cutting, speeches, entrances, and more",
          "Online gallery delivery",
        ],
      },
      {
        name: "Royale",
        price: 700,
        coverage: "Full-day coverage (10–12 hours)",
        leadIn: "Everything in Classic, plus:",
        features: [
          "Extended full-day coverage",
          "A third film — a 5–8 minute highlight film",
          "Delivered within 7–14 days",
        ],
      },
    ],
  },
  {
    id: "naming-ceremony",
    title: "Naming Ceremony & Gender Reveal",
    hoursOnly: true,
    tiers: [
      { name: "Basic", price: 200, coverage: "2 hours coverage" },
      { name: "Classic", price: 300, coverage: "4 hours coverage" },
      { name: "Royale", price: 450, coverage: "6 hours coverage" },
    ],
  },
  {
    id: "lifestyle",
    title: "Lifestyle Shoot",
    hoursOnly: true,
    tiers: [
      { name: "Basic", price: 200, coverage: "2 hours coverage" },
      { name: "Classic", price: 300, coverage: "4 hours coverage" },
      { name: "Royale", price: 450, coverage: "6 hours coverage" },
    ],
  },
];

export const graduation = {
  id: "graduation",
  title: "Graduation Reels",
  price: 150,
  coverage: "1.5 hours coverage",
  features: ["1 edited 30–45 second video", "5 edited photos"],
};

export const extras = {
  title: "Extra Reels",
  subtitle: "Add to any package",
  items: [
    { label: "60–90 second reel", price: 50 },
    { label: "3–5 minute reel", price: 100 },
    { label: "5–8 minute reel", price: 200 },
  ],
};

export const bookingTerms =
  "A 50% deposit secures your date. The remaining balance is due 3–5 days before your event.";
