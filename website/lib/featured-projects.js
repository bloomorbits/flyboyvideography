// Server-side helper for the homepage "Recent Work" section.
//
// getFeaturedProjects() returns the admin-curated featured projects (Migration
// 020), ordered by featured_order. The homepage renders the first 4. Returns []
// on any failure so the homepage falls back to its placeholder set and never
// breaks. Fetched with ISR so admin changes go live within ~60s.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

export async function getFeaturedProjects() {
  if (!API_BASE) return [];
  try {
    const res = await fetch(`${API_BASE}/api/portfolio/featured`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.projects) ? data.projects : [];
  } catch {
    return [];
  }
}
