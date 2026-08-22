import SEOLandingPage, { buildSeoMetadata } from "../components/SEOLandingPage";

const SLUG = "/naming-ceremony-videographer-leeds";
const TITLE = "Naming Ceremony Videographer Leeds | Flyboy Videography";
const DESCRIPTION =
  "Naming ceremony and cultural celebration videography in Leeds and West Yorkshire. From £200 — honest pricing, cinematic delivery, and real understanding of what your day means.";

export const metadata = buildSeoMetadata({
  slug: SLUG,
  title: TITLE,
  description: DESCRIPTION,
});

const CONTENT = {
  kicker: "Naming Ceremonies & Culture",
  h1: "Naming Ceremony Videographer Leeds",
  directAnswer:
    "Flyboy Videography films naming ceremonies, gender reveals, and cultural celebrations across Leeds and West Yorkshire, with packages from £200 for 2 hours of coverage up to £450 for full celebrations. We understand the significance of these moments within West African and wider diaspora traditions, and we film them with that understanding, not as generic event coverage.",
  body: [
    "A naming ceremony isn't just an event — it's a family's history being spoken out loud. The elders' blessings, the names given and what they mean, the aso-oke and the colour and the noise of a room full of people who came specifically for this. That's not something a generic videographer walks into cold and captures properly.",
    "We've filmed naming ceremonies and cultural celebrations across Leeds' diaspora community, and we know the difference between filming an event and understanding what's actually happening in front of the camera — the order of the traditions, who needs to be in frame when, what moments matter even if they're quiet.",
  ],
  included: [
    { title: "Pre-event consultation", detail: "so we understand your specific traditions before the day" },
    { title: "Cinematic coverage of the ceremony" },
    { title: "High-resolution delivery" },
    { title: "Delivery within 7 days" },
  ],
  // Anchor is #naming-ceremony (the actual id in lib/pricing.js). Option A
  // discipline: match the existing anchor rather than renaming the section.
  inlineLink: {
    href: "/services#naming-ceremony",
    label: "See Naming Ceremony & Gender Reveal packages",
  },
  serviceArea: "Serving Leeds, Sheffield, and West Yorkshire.",
  faqs: [
    {
      q: "How much does a naming ceremony videographer cost in Leeds?",
      a: "Packages start at £200 for 2 hours, up to £450 for 6 hours of full celebration coverage.",
    },
    {
      q: "Do you understand West African and diaspora naming traditions?",
      a: "Yes — this is a core part of what we film regularly, not an unfamiliar booking. We take the time in consultation to understand your specific family's traditions rather than assuming they're all the same.",
    },
    {
      q: "Can you film weddings and naming ceremonies as part of the same celebration weekend?",
      a: "Yes, absolutely — [get in touch to discuss your event](/contact) and we'll put together a package that covers everything.",
    },
  ],
  cta: { href: "/book", label: "Book Your Date" },
};

export default function NamingCeremonyVideographerLeedsPage() {
  return <SEOLandingPage {...CONTENT} />;
}
