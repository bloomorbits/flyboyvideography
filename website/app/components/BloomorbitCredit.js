// Bloomorbit Studio credit — single source of truth.
// Used in every public page footer, the 404 page, the loading screen,
// the portal login footer, and (once wired) the chat-widget + email
// footers. Studio name is "Bloomorbit Studio" (one word: "Bloomorbit"),
// always rendered as a hyperlink to https://bloomorbit.tech, never
// plain text.
//
// Editing rule: if the studio name or URL ever changes, change it here
// and here alone — every consumer picks it up automatically.

import Link from "next/link";

export const BLOOMORBIT_NAME = "Bloomorbit Studio";
export const BLOOMORBIT_URL = "https://bloomorbit.tech";

/**
 * Inline credit link. Renders "<prefix> <link>Bloomorbit Studio</link>".
 *
 * @param {object} props
 * @param {string} [props.prefix="Built by"] — text before the link
 * @param {string} [props.className] — passed to the <span> wrapper
 * @param {string} [props.linkClassName] — passed to the <a>
 * @param {string} [props.testId="bloomorbit-credit"]
 */
export default function BloomorbitCredit({
  prefix = "Built by",
  className = "",
  linkClassName = "underline decoration-dotted underline-offset-4 hover:decoration-solid",
  testId = "bloomorbit-credit",
}) {
  return (
    <span data-testid={testId} className={className}>
      {prefix}{" "}
      <a
        href={BLOOMORBIT_URL}
        target="_blank"
        rel="noopener noreferrer"
        data-testid={`${testId}-link`}
        className={linkClassName}
      >
        {BLOOMORBIT_NAME}
      </a>
    </span>
  );
}
