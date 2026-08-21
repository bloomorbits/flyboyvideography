import SEOLandingPage, { buildSeoMetadata } from "../components/SEOLandingPage";

const SLUG = "/wedding-videographer-leeds";
const TITLE = "Wedding Videographer Leeds | Flyboy Videography";
const DESCRIPTION =
  "Cinematic wedding videography in Leeds and across West Yorkshire. Real moments, honestly priced, delivered fast. From £250 — see packages and book your date.";

export const metadata = buildSeoMetadata({
  slug: SLUG,
  title: TITLE,
  description: DESCRIPTION,
});

const CONTENT = {
  kicker: "Leeds · West Yorkshire",
  h1: "Wedding Videographer Leeds",
  directAnswer:
    "Flyboy Videography is a Leeds-based wedding videographer covering ceremonies and receptions across Leeds, Sheffield, and West Yorkshire. Packages start at £250 for a 3-hour highlight film, up to full-day coverage from £700. Every wedding includes a pre-event consultation, cinematic editing, and delivery within 7–14 days.",
  body: [
    "Your wedding day moves fast. The vows, the room going quiet during the speeches, the moment your gran finally gets on the dance floor — most of it happens once, and most of it you won't fully catch while you're living it. That's the whole reason to have someone there whose only job is holding onto it.",
    "We've filmed weddings across Leeds and West Yorkshire for couples who wanted their day told honestly — not staged, not over-produced, just real. Every package includes a proper consultation beforehand, so we know your day, your people, and what actually matters to you before we ever pick up a camera.",
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
  serviceArea:
    "Serving Leeds, Sheffield, and West Yorkshire, with coverage further afield by arrangement.",
  faqs: [
    {
      q: "How much does a wedding videographer cost in Leeds?",
      a: "Our wedding packages start at £250 for 3 hours of coverage and a highlight film, up to £700 for full-day coverage with three separate edits. A 50% deposit secures your date.",
    },
    {
      q: "How far in advance should I book?",
      a: "As early as you can once your date's confirmed — wedding dates fill up, especially spring and summer weekends.",
    },
    {
      q: "Do you film naming ceremonies and cultural celebrations too?",
      // Second sibling landing page doesn't exist yet — inline link points at
      // /services in the meantime. When /naming-ceremony-videographer-leeds
      // ships, swap the URL here (the FAQPage JSON-LD picks up plain text
      // automatically — the [label](url) is stripped for schema).
      a: "Yes — alongside weddings, we regularly film naming ceremonies, gender reveals, and cultural celebrations across Leeds' diaspora community. [See our full services →](/services)",
    },
  ],
  cta: {
    href: "/book",
    label: "Book Your Date",
  },
};

export default function WeddingVideographerLeedsPage() {
  return <SEOLandingPage {...CONTENT} />;
}
