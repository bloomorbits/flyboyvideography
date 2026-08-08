"use client";
// ChatWidget — placeholder slot for Tawk.to (or equivalent) integration.
//
// This component is INTENTIONALLY inert until CHAT_WIDGET_ENABLED flips
// to true. The Bloomorbit Studio credit line is already in the right
// slot so on the day the chat widget goes live, the credit is
// automatically shown alongside it — no scramble later.
//
// Wire-up steps for the future:
//   1. Set CHAT_WIDGET_ENABLED = true (or gate it behind a
//      NEXT_PUBLIC_TAWK_ID env var — remember to add the env var to
//      docs/CREDENTIAL_ROTATION.md at that point).
//   2. Inject the Tawk.to script (respect cookie consent — do NOT load
//      Tawk before hasAnalyticsConsent() returns true, or before adding
//      a dedicated "chat" cookie category).
//   3. On Tawk.to's ready event, call attachBloomorbitCredit() to inject
//      the credit line into the widget's chat window footer via Tawk's
//      onLoad/customStyle hook.
//
// Until step 1 flips, this component renders nothing.

import { BLOOMORBIT_NAME, BLOOMORBIT_URL } from "./BloomorbitCredit";

const CHAT_WIDGET_ENABLED = false;

// Exported so the future Tawk.to onLoad hook can call this once the chat
// window's DOM is available.
export function bloomorbitChatCreditHtml() {
  return `Powered by <a href="${BLOOMORBIT_URL}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;">${BLOOMORBIT_NAME}</a>`;
}

export default function ChatWidget() {
  if (!CHAT_WIDGET_ENABLED) return null;

  // Placeholder markup — replaced by real Tawk.to widget when wired in.
  return (
    <div data-testid="chat-widget-placeholder" aria-hidden style={{ display: "none" }}>
      {/* When live, this renders the Tawk.to iframe/root. The credit
          below is injected into the widget's footer via the exported
          bloomorbitChatCreditHtml() helper. */}
    </div>
  );
}
