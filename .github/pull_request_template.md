<!--
Thanks for opening a pull request! A few notes before you submit:

- For substantive feature changes (especially anything touching the request
  path: auth, DLP, routing, audit), please open an issue first to discuss the
  approach. See CONTRIBUTING.md.
- Keep the PR scoped to a single concern. If you find yourself fixing
  multiple unrelated things, split into multiple PRs.
- Make sure your commits are signed off (`git commit -s`). See CONTRIBUTING.md
  for the DCO requirement.
-->

## Summary

<!-- One or two sentences: what does this PR do, and why? -->

## Related issues

<!-- "Fixes #123", "Refs #456", or "N/A" if there's no linked issue. -->

## Type of change

<!-- Tick the applicable box. -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (would cause existing functionality to behave differently)
- [ ] Documentation only
- [ ] Build / CI / tooling
- [ ] Refactor with no behaviour change

## Testing

<!-- How did you verify this works? Include exact commands where possible. -->

- [ ] Added or updated pytest tests
- [ ] `ruff check .` clean
- [ ] `bandit -r . -c .bandit -lll` clean
- [ ] `pytest --cov=. -rs` passes locally
- [ ] Manual verification — describe what you tested below

<!-- Manual verification notes: -->

## Documentation

- [ ] README / docs updated (if user-facing behaviour changed)
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] `.env.example` updated (if a new environment variable was added)
- [ ] N/A — no documentation impact

## Security and governance impact

<!--
Does this PR touch:
- The authentication path?
- The DLP scanner?
- The routing decision?
- The audit log schema or writes?
- API key handling?

If yes, describe the impact and reasoning. If no, write "None".
-->

## Checklist before merging

- [ ] Commits are signed off (`git commit -s`) — DCO
- [ ] PR title follows the convention (`type: short description`, e.g.
      `feat: add per-team daily token budget headers`)
- [ ] CI is green
- [ ] At least one maintainer approval
