import SEOLandingPage, { buildSeoMetadata } from "../components/SEOLandingPage";
import { getCategoryHeroVideo } from "../../lib/portfolio-hero";

const SLUG = "/birthday-videographer-leeds";
const TITLE = "Birthday Videographer Leeds | Flyboy Videography";
const DESCRIPTION =
  "Cinematic birthday & celebration videography in Leeds and West Yorkshire. Milestone parties, surprises and family moments — honestly priced from £250. See packages and book your date.";

export const metadata = buildSeoMetadata({
  slug: SLUG,
  title: TITLE,
  description: DESCRIPTION,
});

const CONTENT = {
  kicker: "Birthday Celebrations",
  h1: "Birthday Videographer Leeds",
  directAnswer:
    "Flyboy Videography films birthday celebrations across Leeds and West Yorkshire, with packages from £250 up to £700 for fuller coverage and complete deliverables. Every booking includes a pre-event consultation, cinematic editing, and fast delivery — so the day you spent months planning isn't gone by the morning after.",
  body: [
    "A big birthday only happens once — the surprise entrance, the speeches nobody rehearsed, the dance floor at 11pm. Leeds knows how to throw a party, and we film them the way they actually feel: warm, loud, and over far too quickly. A highlight film gives it back to you.",
    "We cover birthdays across Leeds and the wider West Yorkshire area — milestone parties, surprise dos, kids' celebrations and everything between. Same approach every time: a proper chat before the day so we know the running order, the key people and the moments you can't afford to miss, then we stay out of the way and let it happen.",
  ],
  included: [
    { title: "Pre-event consultation", detail: "we learn your celebration before we film it" },
    { title: "Cinematic highlight film", detail: "every package" },
    { title: "High-resolution delivery" },
    { title: "Online gallery for easy sharing with family and friends" },
    { title: "Fast turnaround", detail: "so the memories land while they're still fresh" },
  ],
  inlineLink: {
    href: "/services#birthday",
    label: "See full Birthday Celebration packages & pricing",
  },
  serviceArea: "Serving Leeds, Sheffield, and West/South Yorkshire.",
  faqs: [
    {
      q: "How much does a birthday videographer cost in Leeds?",
      a: "Our birthday packages start at £250, with the £400 Classic package our most popular, and a £700 Royale option for fuller coverage and the complete set of deliverables. A 50% deposit secures your date.",
    },
    {
      q: "What kinds of birthdays do you film?",
      a: "Milestone birthdays, surprise parties, children's celebrations and family gatherings — anything worth keeping. If you're not sure which package fits, tell us about the day and we'll point you to the right one.",
    },
    {
      q: "Do you only cover Leeds, or nearby areas too?",
      a: "We're Leeds-based and cover the wider West Yorkshire area, alongside Sheffield and South Yorkshire. If you're just outside these areas, get in touch — we're often happy to travel, quoted in advance.",
    },
    {
      q: "How soon do we get the film back?",
      a: "We turn birthday films around quickly and will confirm the exact timeline for your package during your consultation, so you know precisely when to expect it.",
    },
  ],
  cta: { href: "/book", label: "Book Your Date" },
};

export const revalidate = 60;

export default async function BirthdayVideographerLeedsPage() {
  const heroVideo = await getCategoryHeroVideo("birthdays");
  return <SEOLandingPage {...CONTENT} heroVideo={heroVideo} heroLabel="Birthday" />;
}
