// Server-side helper for the homepage hero video settings.
//
// getHeroVideo() returns the admin-set list of videos (each { id, weight }) +
// optional poster url from the backend (DB-backed, Migration 019), or the owner
// default on any failure — so the hero never breaks if the API/table is
// unavailable. Fetched with ISR so admin edits go live within ~60s without a
// code deploy. Weighted per-visit rotation happens client-side in HeroPlayer.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

// Owner-supplied default (https://youtu.be/MVE91GRuDVs).
const DEFAULT_VIDEOS = [{ id: "MVE91GRuDVs", weight: 1 }];

export async function getHeroVideo() {
  const fallback = { videos: DEFAULT_VIDEOS, posterUrl: null };
  if (!API_BASE) return fallback;
  try {
    const res = await fetch(`${API_BASE}/api/site-settings/hero-video`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return fallback;
    const data = await res.json();
    const videos = Array.isArray(data.videos) && data.videos.length
      ? data.videos
          .filter((v) => v && v.id)
          .map((v) => ({ id: v.id, weight: Math.max(1, Number(v.weight) || 1) }))
      : DEFAULT_VIDEOS;
    return { videos: videos.length ? videos : DEFAULT_VIDEOS, posterUrl: data.poster_url || null };
  } catch {
    return fallback;
  }
}
