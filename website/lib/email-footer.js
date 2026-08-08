// Email footer template used by transactional emails.
// Wired in later, once Resend is set up. This file exists now so the
// Bloomorbit Studio credit is already in the right slot on the day the
// email pipeline is switched on — no scramble later.
//
// Usage (future):
//   import { emailFooterHtml, emailFooterText } from "./email-footer";
//   await resend.emails.send({
//     from: process.env.RESEND_FROM_EMAIL,
//     to: recipient,
//     subject: "...",
//     html: `${bodyHtml}${emailFooterHtml()}`,
//     text: `${bodyText}\n\n${emailFooterText()}`,
//   });

import { BLOOMORBIT_NAME, BLOOMORBIT_URL } from "../app/components/BloomorbitCredit";

const STUDIO_NAME = "Flyboy Videography";
const STUDIO_EMAIL = "hello@flyboyvideography.com";
const STUDIO_URL = "https://flyboyvideography.com";

export function emailFooterHtml() {
  return `
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin-top:32px;border-top:1px solid #e9e1d2;padding-top:16px;font-family:Inter,Arial,sans-serif;font-size:12px;color:#6b6558;">
      <tr>
        <td style="padding:8px 0;">
          <strong style="color:#17140f;">${STUDIO_NAME}</strong><br />
          <a href="mailto:${STUDIO_EMAIL}" style="color:#6b6558;text-decoration:underline;">${STUDIO_EMAIL}</a> ·
          <a href="${STUDIO_URL}" style="color:#6b6558;text-decoration:underline;">${STUDIO_URL}</a>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 0;font-size:11px;letter-spacing:0.05em;text-transform:uppercase;">
          Built by
          <a href="${BLOOMORBIT_URL}" style="color:#17140f;text-decoration:underline;text-decoration-style:dotted;">${BLOOMORBIT_NAME}</a>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 0;font-size:11px;color:#8a8478;">
          <a href="${STUDIO_URL}/privacy" style="color:#8a8478;text-decoration:underline;">Privacy</a> ·
          <a href="${STUDIO_URL}/terms" style="color:#8a8478;text-decoration:underline;">Terms</a>
        </td>
      </tr>
    </table>
  `;
}

export function emailFooterText() {
  return [
    ``,
    `--`,
    `${STUDIO_NAME}`,
    `${STUDIO_EMAIL} · ${STUDIO_URL}`,
    `Built by ${BLOOMORBIT_NAME} — ${BLOOMORBIT_URL}`,
    `Privacy: ${STUDIO_URL}/privacy · Terms: ${STUDIO_URL}/terms`,
  ].join("\n");
}
