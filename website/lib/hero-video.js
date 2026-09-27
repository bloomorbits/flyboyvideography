// Server-side helper for the homepage hero video settings.
//
// getHeroVideo() returns the admin-set queue of YouTube ids + optional poster
// url from the backend (DB-backed, Migration 019), or the owner default on any
// failure — so the hero never breaks if the API/table is unavailable. Fetched
// with ISR so admin edits go live within ~60s without a code deploy.
// Per-visit rotation through the queue happens client-side in HeroPlayer.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

// Owner-supplied default (https://youtu.be/MVE91GRuDVs).
export const DEFAULT_HERO_VIDEO_IDS = ["MVE91GRuDVs"];

export async function getHeroVideo() {
  const fallback = { videoIds: DEFAULT_HERO_VIDEO_IDS, posterUrl: null };
  if (!API_BASE) return fallback;
  try {
    const res = await fetch(`${API_BASE}/api/site-settings/hero-video`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return fallback;
    const data = await res.json();
    const videoIds = Array.isArray(data.youtube_video_ids) && data.youtube_video_ids.length
      ? data.youtube_video_ids
      : DEFAULT_HERO_VIDEO_IDS;
    return { videoIds, posterUrl: data.poster_url || null };
  } catch {
    return fallback;
  }
}
