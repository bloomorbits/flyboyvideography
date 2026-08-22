import SEOLandingPage, { buildSeoMetadata } from "../components/SEOLandingPage";

const SLUG = "/wedding-videographer-sheffield";
const TITLE = "Wedding Videographer Sheffield | Flyboy Videography";
const DESCRIPTION =
  "Cinematic wedding videography in Sheffield and South Yorkshire. Real moments, honestly priced, delivered fast. From £250 — see packages and book your date.";

export const metadata = buildSeoMetadata({
  slug: SLUG,
  title: TITLE,
  description: DESCRIPTION,
});

const CONTENT = {
  kicker: "Weddings",
  h1: "Wedding Videographer Sheffield",
  directAnswer:
    "Flyboy Videography films weddings across Sheffield and South Yorkshire, with packages from £250 for a 3-hour highlight film up to full-day coverage from £700. Every wedding includes a pre-event consultation, cinematic editing, and delivery within 7–14 days.",
  body: [
    "Sheffield weddings move at their own pace — the walk from the ceremony venue, the room going up when the doors open on the reception, the bits in between that nobody plans for but everyone remembers. That's what we film for.",
    "We cover weddings across Sheffield and into South Yorkshire, working the same way every time: a proper consultation before the day, so we know your running order, your people, and what actually matters to you — not just a stranger with a camera turning up on the day.",
  ],
  included: [
    { title: "Pre-event consultation", detail: "we learn your day before we film it" },
    { title: "Cinematic highlight film", detail: "every package" },
    { title: "High-resolution delivery" },
    { title: "Online gallery for easy sharing with family" },
    { title: "Delivery within 7–14 days", detail: "depending on package" },
  ],
  inlineLink: {
    href: "/services#wedding",
    label: "See full Wedding Videography packages & pricing",
  },
  serviceArea: "Serving Sheffield, Leeds, and South/West Yorkshire.",
  faqs: [
    {
      q: "How much does a wedding videographer cost in Sheffield?",
      a: "Our wedding packages start at £250 for 3 hours of coverage and a highlight film, up to £700 for full-day coverage with three separate edits. A 50% deposit secures your date.",
    },
    {
      q: "Do you only cover Sheffield, or nearby areas too?",
      a: "We cover Sheffield and the wider South Yorkshire area, alongside our Leeds and West Yorkshire base — get in touch if you're just outside these areas, we're often happy to travel.",
    },
    {
      q: "How long before we get our wedding film back?",
      a: "Delivery is 7–14 days depending on your package, and we'll always confirm the expected timeline during your consultation.",
    },
  ],
  cta: { href: "/book", label: "Book Your Date" },
};

export default function WeddingVideographerSheffieldPage() {
  return <SEOLandingPage {...CONTENT} />;
}
