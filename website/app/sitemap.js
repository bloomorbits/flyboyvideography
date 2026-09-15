// Next.js App Router native sitemap (served at /sitemap.xml).
// Covers every public, indexable route. Legal pages (privacy/terms/model-release/
// safeguarding-consent) and transactional book success/cancel pages are
// deliberately excluded — they add no search value and dilute crawl budget.
//
// When a new SEO landing page ships, add its slug to SEO_PAGES below. That is
// the ONLY change needed — the route auto-appears in /sitemap.xml on next build.
const SITE_URL = "https://flyboyvideography.com";

// Four Priority-1 SEO landing pages currently live.
const SEO_PAGES = [
  "/wedding-videographer-leeds",
  "/wedding-videographer-sheffield",
  "/naming-ceremony-videographer-leeds",
  "/birthday-videographer-leeds",
  "/birthday-videographer-sheffield",
  "/naming-ceremony-videographer-sheffield",
  "/lifestyle-videographer-leeds",
  "/corporate-event-videographer-leeds",
];

export default function sitemap() {
  const lastModified = new Date();

  const core = [
    { path: "/", priority: 1.0, changeFrequency: "weekly" },
    { path: "/services", priority: 0.9, changeFrequency: "weekly" },
    { path: "/portfolio", priority: 0.8, changeFrequency: "weekly" },
    { path: "/book", priority: 0.8, changeFrequency: "monthly" },
    { path: "/contact", priority: 0.7, changeFrequency: "monthly" },
    { path: "/faq", priority: 0.6, changeFrequency: "monthly" },
  ];

  const seo = SEO_PAGES.map((path) => ({
    path,
    priority: 0.9,
    changeFrequency: "monthly",
  }));

  return [...core, ...seo].map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified,
    changeFrequency: r.changeFrequency,
    priority: r.priority,
  }));
}
