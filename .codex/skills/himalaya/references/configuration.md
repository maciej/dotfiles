# Configuration and version drift

Read this for setup, auth failures, or v1 migration. Do not reconfigure a working
account merely because an example command fails.

Himalaya 2.2.1 discovers `$XDG_CONFIG_HOME/himalaya/config.toml`,
`~/.config/himalaya/config.toml`, or `~/.himalayarc`. `HIMALAYA_CONFIG`/`--config`
can override discovery. `--config base.toml:private.toml` merges files in order.
Inspect paths and selected nonsecret fields without printing secret values.

For requested installation, the usual macOS route is `brew install himalaya`;
check upstream instructions for another platform. For requested setup, inspect
`himalaya configure --help`; the wizard needs interactive input. Generate into
a temporary file and inspect/merge it rather than redirecting onto an existing
configuration, which can truncate it before discovery runs.

## v2 IMAP/SMTP shape

This is an illustrative account, not a provider-specific configuration. Replace
servers, identity, helper lookup, and mailbox names with the intended values:

```toml
[accounts.personal]
default = true
email = "user@example.com"
display-name = "Your Name"

imap.server = "imaps://imap.example.com:993"
imap.sasl.plain.username = "user@example.com"
imap.sasl.plain.password.command = "pass show email/imap"

smtp.server = "smtp://smtp.example.com:587"
smtp.starttls = true
smtp.sasl.plain.username = "user@example.com"
smtp.sasl.plain.password.command = "pass show email/smtp"

mailbox.alias.inbox = "INBOX"
mailbox.alias.sent = "Sent"
mailbox.alias.drafts = "Drafts"
mailbox.alias.trash = "Trash"
```

Use existing secret helpers; `.password.command` and `.token.command` can obtain
secrets from a password manager or platform keychain. Never execute a helper
just to display its returned secret. Keep secrets out of tracked files and chat.
v2 uses external helpers for OAuth tokens as well; do not transplant old built-in
keyring/OAuth settings. Preserve TLS and certificate validation.

v1 `backend.type`, `backend.auth.cmd`, `message.send.backend.*`, and
`folder.aliases.*` are not v2 configuration. TOML parsing alone does not establish
that backend settings were recognized. An empty `backends` list in
`himalaya --config candidate.toml account list --json` is a diagnostic clue.
After a requested configuration edit, run
`himalaya --config candidate.toml --account personal account check` before
replacing the live file. This authenticates with configured services; it is not
an offline syntax check. Keep a private backup when migrating.

`mailbox.alias.<name>` is v2 syntax. Alias lookup is case-insensitive, then role
lookup is tried, then the given value is passed through. Servers/backends may
report only some roles. Use `mailbox list` and actual names instead of assuming
`sent`, `drafts`, or `trash` resolves everywhere.

Sent-copy policy is separate from sending: `message.send.save-copy = "Sent"`
sets a default destination, `--save Sent` overrides it, and `--no-save` skips the
configured copy. Some providers file sent mail themselves, so check existing
behavior before adding copies. A copy failure after submission is not evidence
that sending failed.

For other backends or provider setup, consult the
[upstream sample](https://github.com/pimalaya/himalaya/blob/master/config.sample.toml)
matching the installed version and local `--help`. Do not infer ManageSieve
support from the CLI having a `sieve` command; verify the provider supports it.
