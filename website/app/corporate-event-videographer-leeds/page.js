import SEOLandingPage, { buildSeoMetadata } from "../components/SEOLandingPage";

const SLUG = "/corporate-event-videographer-leeds";
const TITLE = "Corporate Event Videographer Leeds | Flyboy Videography";
const DESCRIPTION =
  "Corporate event videography in Leeds and West Yorkshire — conferences, launches, awards and brand films. Every corporate project is quoted to scope. Tell us your event and we'll send a tailored quote.";

export const metadata = buildSeoMetadata({
  slug: SLUG,
  title: TITLE,
  description: DESCRIPTION,
});

// Quote-based variant (owner directive, option b): corporate is not a fixed-price
// package in lib/pricing.js — it's quoted per project. So this page carries NO
// pricing and NO /services#corporate anchor (that anchor doesn't exist). It omits
// `inlineLink` entirely and sends the CTA to /contact for a tailored quote. The
// shared SEOLandingPage needs no change — every block is already conditional.
const CONTENT = {
  kicker: "Corporate & Brand Events",
  h1: "Corporate Event Videographer Leeds",
  directAnswer:
    "Flyboy Videography films corporate events across Leeds and West Yorkshire — conferences, product launches, awards nights, team days and brand films. Corporate work is quoted per project rather than sold as a fixed package, because scope varies enormously: tell us the event, the length, and where the footage is going, and we'll send a tailored quote.",
  body: [
    "Corporate footage has a job to do. A launch reel has to sell, a conference recap has to prove the day was worth it, an internal film has to actually get watched. That's a different brief to filming a party — it starts with what the video is for, then works backwards to what we shoot on the day.",
    "We cover corporate events across Leeds and the wider West Yorkshire area, and we scope every job around the outcome: the deliverables you need, the formats for the platforms they'll live on, and the turnaround your campaign or comms actually run to. No off-the-shelf package — a plan built for your event, quoted up front so there are no surprises.",
  ],
  included: [
    { title: "Pre-event consultation", detail: "we scope the deliverables and the goal before the day" },
    { title: "Cinematic coverage", detail: "conferences, launches, awards, brand films and more" },
    { title: "Formats for your platforms", detail: "internal, web and social cuts as needed" },
    { title: "High-resolution delivery" },
    { title: "Turnaround agreed up front", detail: "to fit your campaign or comms timeline" },
  ],
  serviceArea: "Serving Leeds, Sheffield, and West Yorkshire.",
  faqs: [
    {
      q: "How much does a corporate event videographer cost in Leeds?",
      a: "Corporate projects are quoted individually because scope varies — a half-day recap is very different to a multi-camera conference or a produced brand film. [Tell us about your event](/contact) and we'll send a tailored quote with no obligation.",
    },
    {
      q: "What kinds of corporate work do you film?",
      a: "Conferences, product launches, awards ceremonies, team and away days, testimonial and brand films, and event recaps. If you're not sure what you need, tell us the outcome you're after and we'll suggest an approach.",
    },
    {
      q: "Can you deliver different cuts for different platforms?",
      a: "Yes — we plan formats around where the footage is going, so you can get a longer recap alongside short vertical cuts for social from the same shoot. We'll confirm the exact deliverables in your quote.",
    },
    {
      q: "How quickly can we get the footage back?",
      a: "Turnaround is agreed up front and built around your campaign or internal comms timeline. Tell us your deadline when you enquire and we'll confirm what's achievable.",
    },
  ],
  cta: { href: "/contact", label: "Request a Quote" },
};

export default function CorporateEventVideographerLeedsPage() {
  return <SEOLandingPage {...CONTENT} />;
}
