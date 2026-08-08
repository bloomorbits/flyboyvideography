// Portfolio placeholder items. No real footage is claimed here — every card
// is styled and labelled as a Placeholder tile until the client supplies
// actual work samples. The `src` fields point at generic free-licence stock
// stills sourced from Pexels (Free Pexels License, no attribution required,
// no visible logos or recognisable venues). Video-kind cards use the still
// as a poster frame and keep the play glyph + duration badge to preview the
// "would-be" video state.

const px = (id) =>
  `https://images.pexels.com/photos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&w=1600`;

export const CATEGORIES = [
  { id: "all", label: "All work" },
  { id: "weddings", label: "Weddings" },
  { id: "birthdays", label: "Birthday Celebrations" },
  { id: "naming", label: "Naming & Gender Reveal" },
  { id: "corporate", label: "Corporate Events" },
  { id: "lifestyle", label: "Lifestyle Reels" },
];

// Each tile carries a `src` (Pexels still) and, for video-kind cards, a
// duration badge. `span` controls the bento grid rhythm.
export const items = [
  {
    id: "w-01",
    category: "weddings",
    kind: "video",
    title: "Highlight Film · Placeholder",
    meta: "Wedding · Cinematic Highlight",
    duration: "01:24",
    src: px(26673556),
  },
  {
    id: "w-02",
    category: "weddings",
    kind: "still",
    title: "Ceremony Still · Placeholder",
    meta: "Wedding · Still Frame",
    src: px(13456843),
  },
  {
    id: "w-03",
    category: "weddings",
    kind: "video",
    title: "Reception Reel · Placeholder",
    meta: "Wedding · Social Reel",
    duration: "00:58",
    src: px(15305396),
  },

  {
    id: "b-01",
    category: "birthdays",
    kind: "video",
    title: "Milestone Birthday · Placeholder",
    meta: "Birthday · Highlight",
    duration: "01:12",
    src: px(15211704),
  },
  {
    id: "b-02",
    category: "birthdays",
    kind: "still",
    title: "Candid Moment · Placeholder",
    meta: "Birthday · Still Frame",
    src: px(6515979),
  },
  {
    id: "b-03",
    category: "birthdays",
    kind: "video",
    title: "Party Reel · Placeholder",
    meta: "Birthday · Social Reel",
    duration: "00:42",
    src: px(137485),
  },

  {
    id: "n-01",
    category: "naming",
    kind: "video",
    title: "Naming Ceremony · Placeholder",
    meta: "Naming · Highlight",
    duration: "01:36",
    src: px(21581547),
  },
  {
    id: "n-02",
    category: "naming",
    kind: "still",
    title: "Family Portrait · Placeholder",
    meta: "Naming · Still Frame",
    src: px(16475067),
  },
  {
    id: "n-03",
    category: "naming",
    kind: "video",
    title: "Gender Reveal · Placeholder",
    meta: "Gender Reveal · Highlight",
    duration: "00:47",
    src: px(28680700),
  },

  {
    id: "c-01",
    category: "corporate",
    kind: "video",
    title: "Brand Launch · Placeholder",
    meta: "Corporate · Event Film",
    duration: "01:52",
    src: px(9275222),
  },
  {
    id: "c-02",
    category: "corporate",
    kind: "still",
    title: "Keynote Still · Placeholder",
    meta: "Corporate · Still Frame",
    src: px(8463151),
  },
  {
    id: "c-03",
    category: "corporate",
    kind: "video",
    title: "Conference Recap · Placeholder",
    meta: "Corporate · Recap Reel",
    duration: "01:08",
    src: px(26202153),
  },

  {
    id: "l-01",
    category: "lifestyle",
    kind: "video",
    title: "Lifestyle Reel · Placeholder",
    meta: "Lifestyle · Social Reel",
    duration: "00:38",
    src: px(19871471),
  },
  {
    id: "l-02",
    category: "lifestyle",
    kind: "still",
    title: "Editorial Still · Placeholder",
    meta: "Lifestyle · Still Frame",
    src: px(9026864),
  },
  {
    id: "l-03",
    category: "lifestyle",
    kind: "video",
    title: "Everyday Motion · Placeholder",
    meta: "Lifestyle · Cinematic",
    duration: "01:04",
    src: px(37201825),
  },
];
