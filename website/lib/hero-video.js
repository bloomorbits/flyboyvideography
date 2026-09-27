// Server-side helper for the homepage hero YouTube video.
//
// getHeroVideoId() returns the admin-set hero video id from the backend
// (DB-backed, Migration 019), or the owner default on any failure — so the
// hero never breaks if the API/table is unavailable. Fetched with ISR so an
// admin edit goes live within ~60s without a code deploy.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

// Owner-supplied default (https://youtu.be/MVE91GRuDVs).
export const DEFAULT_HERO_VIDEO_ID = "MVE91GRuDVs";

export async function getHeroVideoId() {
  if (!API_BASE) return DEFAULT_HERO_VIDEO_ID;
  try {
    const res = await fetch(`${API_BASE}/api/site-settings/hero-video`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return DEFAULT_HERO_VIDEO_ID;
    const data = await res.json();
    return data.youtube_video_id || DEFAULT_HERO_VIDEO_ID;
  } catch {
    return DEFAULT_HERO_VIDEO_ID;
  }
}
