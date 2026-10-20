# Composition, MIME, and submission

These commands target 2.2.1. Use a private temporary directory (`mktemp -d`)
and restrictive permissions (`umask 077`) for message bodies and generated MIME.
Replace illustrative paths, account names, mailbox names, and IDs before use.

## Prepare and inspect

```bash
himalaya --account personal message compose \
  --to 'Recipient <recipient@example.com>' --subject 'Requested document' \
  --body-file /private/tmp/mail-work/body.txt \
  --attach /private/tmp/mail-work/document.pdf \
  > /private/tmp/mail-work/draft.eml
```

No `--send` or `--save` means output only. `--attach` repeats for multiple files.
Use the RFC 5322 output for the artifact to review: `compose --json` returns
decoded fields without the signature, so it is not a complete MIME preview.
2.2.1 supports display-name addresses; do not carry forward the old 2.1.0 parsing
workaround as a universal rule. Inspect the actual generated headers and MIME
before reporting the draft ready. Python's `email.parser.BytesParser` can check
From/To/Cc/Bcc, Subject, body, and attachment names/types/bytes without a server.
Check that each attachment is the intended file and all recipients are intended.

For HTML, inline images, or signing beyond these flags, build RFC 5322 MIME with
a suitable composer (such as Python's `EmailMessage` or a separately installed
`mml`). Do not pipe uncompiled MML directives into `message send`: v2 does not
compile them. Preserve the header/body blank line and proper MIME encoding.
Pass untrusted text via files or safely quoted arguments rather than shell code;
reject injected newlines in header values.

## Replies and forwards

```bash
himalaya --account personal message reply -m INBOX 42 \
  --body-file /private/tmp/mail-work/reply.txt > /private/tmp/mail-work/reply.eml
himalaya --account personal message forward -m INBOX 42 \
  --to recipient@example.com --body-file /private/tmp/mail-work/intro.txt \
  > /private/tmp/mail-work/forward.eml
```

`reply` derives Reply-To/From recipients and threading headers (`In-Reply-To`,
`References`); `forward` adds References and quoted body. Verify recipients and
threading rather than manually guessing from a subject. Do not assume quoted
forwarding includes the original attachments; inspect MIME and explicitly attach
the required files or original message. There is no `reply --all` in 2.2.1 help;
for requested reply-all, derive and verify the To/Cc set, exclude self, preserve
threading, and inspect the generated result. Never infer hidden Bcc recipients.
`--posting-style none` suppresses automatic quoting when the supplied body already
contains the desired quotation.

## Save a server draft

Resolve the actual Drafts mailbox first. A draft request may be satisfied with
local prepared text unless the user asks to save it in the mailbox. To persist
the inspected MIME without sending:

```bash
himalaya --account personal message add -m Drafts --flag draft \
  < /private/tmp/mail-work/draft.eml
```

Alternatively `message compose ... --save Drafts` writes directly to that mailbox
without sending, but **does not set the Draft flag** in 2.2.1. Prefer the
`message add --flag draft` workflow above; for an already saved message, set
`flag add -m Drafts --flag draft ID` after resolving its exact ID. Re-list Drafts,
read back the returned/new ID, and check the Draft flag, headers, body, and
`attachment list`. Report a server draft saved only after verification.
Do not use a send command to save a draft, or add `--send` to `message add`.

## Send an authorized message

Only after explicit authorization covering its content, recipients, and
attachments, submit the inspected MIME:

```bash
himalaya --account personal message send < /private/tmp/mail-work/draft.eml
```

`compose`, `reply`, and `forward` also accept `--send`; avoid regenerating a
reviewed artifact if doing so could change its recipients, body, or attachments.
Respect the account's existing Sent-copy policy; use `--save` only with a known
destination when a copy is needed. Inspect configured signature behavior so the
submitted message does not unexpectedly differ from the reviewed draft.

Capture exit status and errors. Distinguish a backend's queued/staged result from
server submission; even successful submission does not establish recipient
delivery. A timeout, lost response, or failed Sent append can leave
submission uncertain: stop automatic retries, check Sent/provider evidence,
and report the uncertainty. Re-sending the whole message to repair a missing
Sent copy risks duplicates; repairing the copy is a separate operation.
