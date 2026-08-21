/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      // /admin → portal login. Permanent (308) so it's crawler-friendly and
      // works pre-JS (edge-level redirect, no client hydration required).
      // Kept in the marketing site's config rather than requiring a client-
      // side handler on the portal.
      {
        source: "/admin",
        destination: "https://app.flyboyvideography.com/auth",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
