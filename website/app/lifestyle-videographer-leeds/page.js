import SEOLandingPage, { buildSeoMetadata } from "../components/SEOLandingPage";

const SLUG = "/lifestyle-videographer-leeds";
const TITLE = "Lifestyle & Brand Content Videographer Leeds | Flyboy Videography";
const DESCRIPTION =
  "Lifestyle and brand content videography in Leeds and West Yorkshire. Personal brand films, content days and social reels — honestly priced from £200. See packages and book your shoot.";

export const metadata = buildSeoMetadata({
  slug: SLUG,
  title: TITLE,
  description: DESCRIPTION,
});

const CONTENT = {
  kicker: "Lifestyle & Brand Content",
  h1: "Lifestyle & Brand Content Videographer Leeds",
  directAnswer:
    "Flyboy Videography shoots lifestyle and brand content across Leeds and West Yorkshire, with sessions from £200 for 2 hours up to £450 for a full 6-hour shoot. It's built for people who need a batch of real, cinematic footage — personal brand films, content days, product and social reels — planned around what you actually want to post, then delivered fast.",
  body: [
    "Most people don't need a film crew for a week — they need a focused half-day that gives them months of content. That's what a lifestyle shoot is: we plan the looks, the setups and the shots you actually want beforehand, then get through them properly on the day so you walk away with a real library, not one lucky clip.",
    "We shoot lifestyle and brand content across Leeds and West Yorkshire — founders and creators building a personal brand, small businesses that need social-ready footage, and anyone tired of stiff, stock-looking video. Same approach every time: a proper chat first so we know your brand, your platforms and what you're trying to say, then footage that looks like you on your best day.",
  ],
  included: [
    { title: "Pre-shoot consultation", detail: "we plan the shots and looks before the day" },
    { title: "Cinematic coverage", detail: "shot for the platforms you actually use" },
    { title: "High-resolution delivery" },
    { title: "Online gallery for easy sharing and reposting" },
    { title: "Fast turnaround", detail: "so you can post while it's current" },
  ],
  inlineLink: {
    href: "/services#lifestyle",
    label: "See full Lifestyle Shoot packages & pricing",
  },
  serviceArea: "Serving Leeds, Sheffield, and West Yorkshire.",
  faqs: [
    {
      q: "How much does a lifestyle or brand content videographer cost in Leeds?",
      a: "Sessions start at £200 for 2 hours, £300 for 4 hours, and £450 for a full 6-hour shoot. A 50% deposit secures your date.",
    },
    {
      q: "What can I use a lifestyle shoot for?",
      a: "Personal brand films, content days, product and social reels, launch footage, and general lifestyle content. If you tell us where you'll be posting, we'll shoot it in the right format from the start.",
    },
    {
      q: "Do you plan the shots or do I turn up with ideas?",
      a: "Both work — we run a consultation beforehand to lock down the looks and shot list, so the day is efficient. Bring references if you have them; if you don't, we'll build the plan with you.",
    },
    {
      q: "How soon do I get the footage back?",
      a: "We turn lifestyle and brand content around quickly and confirm the exact timeline for your session during your consultation, so you know when to expect the files.",
    },
  ],
  cta: { href: "/book", label: "Book Your Shoot" },
};

export default function LifestyleVideographerLeedsPage() {
  return <SEOLandingPage {...CONTENT} />;
}
