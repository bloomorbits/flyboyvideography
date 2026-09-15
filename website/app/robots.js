// Next.js App Router native robots.txt (served at /robots.txt).
// Allows all crawlers and points them at the sitemap so Google/Bing can
// discover every indexable route. Legal + transactional paths are disallowed
// to keep them out of the index (they are also absent from the sitemap).
const SITE_URL = "https://flyboyvideography.com";

export default function robots() {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/book/success",
        "/book/cancel",
        "/privacy",
        "/terms",
        "/model-release",
        "/safeguarding-consent",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
