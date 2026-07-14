# CI deploy key setup

`rebuild-data.yml` and `sync-zoho-abn-webhook.yml` both push straight to
`main` (no PR). Once `main` requires pull requests (branch protection /
ruleset), those direct pushes get rejected — the built-in `github-actions[bot]`
identity behind the default `GITHUB_TOKEN` can't be added to a ruleset's
bypass list (it's a system account, not an installable GitHub App or a
deploy key), so both workflows' `Checkout` steps instead check the repo out
using an SSH deploy key (`ssh-key: ${{ secrets.DEPLOY_KEY }}`), and that
deploy key — not the default token — is what goes on the bypass list.
Deploy keys don't belong to any one person's account, so this doesn't carry
the "credential only one person holds" risk a personal PAT would (see
CLAUDE.md's Ownership context section).

## One-time setup

A keypair for this has already been generated (ed25519). The **public**
half is safe to share and is below; the **private** half was handed to you
directly in chat when this was set up, not committed anywhere in this repo
— if you don't have it, generate a fresh pair instead of hunting for it:

```
ssh-keygen -t ed25519 -f tech_vector_ci_deploy_key -C "tech_vector-ci-deploy-key" -N ""
```

Public key (already generated for this repo):
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOnpoKPJ45iJc8l8JAKtSSNKcZIhMD2PMqBY5Qryi+GV tech_vector-ci-deploy-key
```

1. **Add the public key as a deploy key** — repo → Settings → Deploy keys →
   Add deploy key → paste the public key above → check **Allow write
   access** → Add key.
2. **Add the private key as a secret** — repo → Settings → Secrets and
   variables → Actions → New repository secret → name it exactly
   `DEPLOY_KEY` (both workflows reference `secrets.DEPLOY_KEY`) → paste the
   full private key (including the `-----BEGIN/END OPENSSH PRIVATE KEY-----`
   lines) → Add secret.
3. **Add the deploy key to the ruleset's bypass list** (only relevant once
   `main`'s ruleset requires PRs) — Settings → Rules → Rulesets → your
   ruleset → Bypass list → Add bypass → search for the deploy key you just
   added in step 1 (deploy keys are their own selectable actor type,
   distinct from Apps) → Add Selected → set mode to **Always allow**.

## Verifying it worked

Trigger `sync-zoho-abn-webhook.yml` manually via `workflow_dispatch` (or
wait for `rebuild-data.yml`'s next 8-week gate, or force it with
`workflow_dispatch`'s `force: true`) and confirm the run's final push step
actually lands a commit on `main` rather than being rejected — that's the
one failure mode this whole setup exists to prevent, so it's worth
confirming directly rather than assuming the settings took effect.

## If this ever needs rotating

Generate a new keypair, repeat steps 1–3 above with the new public/private
halves, then remove the old deploy key from Settings → Deploy keys (this
automatically drops it from any bypass list it was on).
