// Server-side helper for the SEO landing-page video hero.
//
// getCategoryHeroVideo(category) returns the FIRST active portfolio video for a
// category, or null. The backend /api/portfolio already returns only active
// rows ordered by (category, display_order, created_at), so the first match is
// the correct hero — same ordering the public portfolio grid respects. Any
// failure (no API base, network error, empty table) returns null, and the SEO
// page then renders its existing hero-less layout unchanged (honest fallback).

const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

export function heroThumb(v) {
  // Prefer the stored oEmbed thumbnail; fall back to YouTube's hqdefault.
  return v.thumbnail_url || `https://i.ytimg.com/vi/${v.youtube_video_id}/hqdefault.jpg`;
}

function isoDuration(s) {
  return s ? `PT${Math.floor(s / 60)}M${s % 60}S` : undefined;
}

export async function getCategoryHeroVideo(category) {
  if (!API_BASE) return null;
  try {
    const res = await fetch(`${API_BASE}/api/portfolio`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    const data = await res.json();
    const videos = Array.isArray(data.videos) ? data.videos : [];
    return videos.find((v) => v.category === category) || null;
  } catch {
    return null;
  }
}

// VideoObject JSON-LD from the real row metadata — mirrors the /portfolio page,
// so the hero is a genuine, crawlable video entity (not a decorative embed).
export function buildHeroVideoLd(video, { name, description }) {
  return {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: video.title || name,
    description: video.description || description,
    thumbnailUrl: heroThumb(video),
    embedUrl: `https://www.youtube.com/embed/${video.youtube_video_id}`,
    contentUrl: `https://www.youtube.com/watch?v=${video.youtube_video_id}`,
    ...(video.upload_date ? { uploadDate: video.upload_date } : {}),
    ...(isoDuration(video.duration_seconds) ? { duration: isoDuration(video.duration_seconds) } : {}),
    publisher: {
      "@type": "Organization",
      name: "Flyboy Videography",
      url: "https://flyboyvideography.com",
    },
  };
}
