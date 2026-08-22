import Link from "next/link";

/**
 * SEOLandingPage — reusable server-rendered template for city/service SEO pages.
 *
 * This is deliberately a Server Component (no "use client" directive). Every
 * word of content, every FAQ, and the FAQPage JSON-LD block are emitted in
 * the initial HTML response — verifiable via `curl <url> | grep`. No content
 * lives behind hydration; nothing on this page requires JS to be readable
 * by users, crawlers, or LLMs.
 *
 * Content model (props):
 *   kicker         — short uppercase label above the H1 (e.g. "SEO landing")
 *   h1             — the single H1 for the page
 *   directAnswer   — first visible paragraph. Written as a direct answer to
 *                    "who/what/where is this?" for LLM/AI-overview harvest.
 *   body           — array of paragraph strings for the human narrative.
 *   included       — array of {title, detail?} — the "what's included" list.
 *   inlineLink     — {href, label} rendered as a subtle "read more" link
 *                    between body and included, keeps internal linking dense.
 *   serviceArea    — single-line service area statement.
 *   faqs           — array of {q, a} — rendered visually AND emitted as
 *                    FAQPage JSON-LD in the same template call.
 *   cta            — {href, label} — final primary CTA.
 *
 * To add a new page: create /app/<slug>/page.js, `export const metadata`,
 * pass content into <SEOLandingPage />. Do NOT hand-write JSON-LD per page —
 * this component builds it from the FAQ array so schema stays in sync
 * with what's on the page.
 */

function buildFaqJsonLd(faqs) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map(({ q, a }) => ({
      "@type": "Question",
      name: q,
      acceptedAnswer: {
        "@type": "Answer",
        // Strip full [label](url) markdown-style links from the answer text —
        // schema.org Answer.text is plain-text for LLMs/crawlers, so both
        // the [label] wrapper AND the (url) tail need to go.
        text: a.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1"),
      },
    })),
  };
}

export default function SEOLandingPage({
  kicker,
  h1,
  directAnswer,
  body = [],
  included = [],
  inlineLink,
  serviceArea,
  faqs = [],
  cta,
}) {
  const faqJsonLd = buildFaqJsonLd(faqs);

  return (
    <>
      {/* Emit the FAQPage schema as a real <script> element in the SSR
          HTML. Using dangerouslySetInnerHTML here (rather than a JSON literal
          in JSX) keeps the payload compact and lets crawlers parse it
          without additional escaping. */}
      <script
        type="application/ld+json"
        data-testid="faq-jsonld"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      <main className="bg-cream text-ink">
        <article className="mx-auto max-w-3xl px-6 pb-24 pt-32 md:pt-40">
          {kicker && (
            <p
              data-testid="seo-kicker"
              className="font-mono text-xs uppercase tracking-[0.35em] text-ink/70"
            >
              {kicker}
            </p>
          )}

          <h1
            data-testid="seo-h1"
            className="mt-4 font-display text-4xl font-bold leading-[1.05] tracking-tight md:text-5xl"
          >
            {h1}
          </h1>

          {/* Direct-answer intro — first paragraph, distinct treatment so
              LLM overviews and Google's AI panels have a clean, self-
              contained answer block. */}
          <p
            data-testid="seo-direct-answer"
            className="mt-8 rounded-2xl border border-ink/10 bg-sand p-6 font-body text-lg leading-relaxed"
          >
            {directAnswer}
          </p>

          {/* Body paragraphs. Rendered with generous line-height for
              readability; no clever markup, just prose. */}
          {body.length > 0 && (
            <div
              data-testid="seo-body"
              className="mt-10 space-y-6 font-body text-base leading-relaxed text-ink/90"
            >
              {body.map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          )}

          {inlineLink && (
            <p className="mt-8 font-body text-base">
              <Link
                href={inlineLink.href}
                data-testid="seo-inline-link"
                className="inline-flex min-h-[44px] items-center underline decoration-dotted underline-offset-4 hover:decoration-solid"
              >
                {inlineLink.label} →
              </Link>
            </p>
          )}

          {included.length > 0 && (
            <section
              data-testid="seo-included"
              className="mt-12 rounded-2xl bg-dune p-6 md:p-8"
            >
              <h2 className="font-display text-xl font-bold tracking-tight md:text-2xl">
                What&rsquo;s included
              </h2>
              <ul className="mt-5 space-y-3">
                {included.map((item, i) => {
                  // A string entry is treated as a single-line item;
                  // {title, detail} splits into a bold lead + supporting text.
                  const isString = typeof item === "string";
                  const title = isString ? item : item.title;
                  const detail = isString ? null : item.detail;
                  return (
                    <li
                      key={i}
                      data-testid={`seo-included-${i}`}
                      className="flex gap-3 font-body text-base leading-relaxed"
                    >
                      <span aria-hidden className="mt-2 h-1.5 w-1.5 flex-none rounded-full bg-ink" />
                      <span>
                        <span className="font-medium">{title}</span>
                        {detail && <span className="text-ink/70"> — {detail}</span>}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {serviceArea && (
            <p
              data-testid="seo-service-area"
              className="mt-10 font-mono text-sm uppercase tracking-[0.2em] text-ink/70"
            >
              {serviceArea}
            </p>
          )}

          {faqs.length > 0 && (
            <section
              data-testid="seo-faqs"
              className="mt-16 border-t border-ink/10 pt-12"
            >
              <h2 className="font-display text-2xl font-bold tracking-tight md:text-3xl">
                Common questions
              </h2>
              <dl className="mt-8 space-y-8">
                {faqs.map(({ q, a }, i) => (
                  <div key={i} data-testid={`seo-faq-${i}`}>
                    <dt className="font-display text-base font-semibold md:text-lg">
                      {q}
                    </dt>
                    <dd className="mt-2 font-body text-base leading-relaxed text-ink/90">
                      {renderAnswerWithInlineLinks(a)}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {cta && (
            <div className="mt-16">
              <Link
                href={cta.href}
                data-testid="seo-cta"
                className="inline-flex min-h-[52px] items-center justify-center rounded-full bg-ink px-8 font-medium text-cream transition-colors hover:bg-ink/85"
              >
                {cta.label} →
              </Link>
            </div>
          )}
        </article>
      </main>
    </>
  );
}

/**
 * Renders answer text with support for [label](/url) markdown-style inline
 * links. Kept intentionally simple — no full markdown parser, just this
 * one pattern, because that's all the FAQ answer content actually needs.
 */
function renderAnswerWithInlineLinks(answer) {
  const parts = [];
  const regex = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(answer)) !== null) {
    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index));
    }
    parts.push(
      <Link
        key={match.index}
        href={match[2]}
        className="underline decoration-dotted underline-offset-4 hover:decoration-solid"
      >
        {match[1]}
      </Link>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < answer.length) parts.push(answer.slice(lastIndex));
  return parts;
}

/**
 * Helper to build a page's `metadata` export from the same content that
 * feeds the template — keeps title/description/canonical/OG in sync with
 * what's on the page without hand-repeating the strings.
 *
 * Usage in a page.js:
 *   export const metadata = buildSeoMetadata({
 *     slug: "/wedding-videographer-leeds",
 *     title: "Wedding Videographer Leeds | Flyboy Videography",
 *     description: "...",
 *   });
 *
 * The site's root layout sets metadataBase to https://flyboyvideography.com,
 * so `alternates.canonical` can be a path.
 */
export function buildSeoMetadata({ slug, title, description }) {
  return {
    // `absolute` bypasses the root layout's `title.template` — the pages
    // here already include the "| Flyboy Videography" suffix in their
    // exact SEO-approved copy, so we don't want the template appending it
    // a second time.
    title: { absolute: title },
    description,
    alternates: { canonical: slug },
    openGraph: {
      type: "article",
      url: slug,
      title,
      description,
      images: [{ url: "/og.jpg", width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/og.jpg"],
    },
  };
}
