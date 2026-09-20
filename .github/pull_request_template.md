Thanks for contributing to Swift!

## Summary

<!-- What does this PR do, and why? -->

## Related issue

<!-- Fixes #123 / Closes #123 -- if applicable -->

## Checklist

Nothing below is checked automatically -- this is a self-check for you before requesting review.

- [ ] PR title follows [Conventional Commits](https://www.conventionalcommits.org/) (`type: description`)
- [ ] Python tests pass locally (`pytest tests/ -v`)
- [ ] JS unit tests pass locally, if `src/swift/public/js/**` changed (`node --test src/swift/public/js/*.test.js`)
- [ ] If `src/swift/public/**` changed: `npm run build:vendor` in `src/swift/public/` produces no diff against the committed `js/vendor/` tree (see `vendor-check.yml`)
- [ ] Added/updated tests for this change, if applicable
- [ ] New/changed Python code is type-hinted with modern syntax (`X | Y`, `list[X]`, not `Union`/`Optional`/`List`)
- [ ] Docstrings updated (reST style: `:param:`, `:returns:`; type hints in the signature cover types now, `:type:`/`:rtype:` are rarely needed)
- [ ] PR is as small/focused as practical -- if it tackles several unrelated things, consider splitting it so each can be reviewed and accepted independently

<!-- Target branch is `main` -- see #149 if you're wondering about `future`. -->
