# Security

These skills can inspect local repositories, local media, and public network
sources. Treat them as executable software, not as passive prompt files.

- Read every `SKILL.md` and bundled script before installing.
- Never place API keys, cookies, private chat exports, or raw personal data in
  this repository or in a generated report intended for sharing.
- The Bilibili and arXiv collectors are read-only and make bounded public
  requests. They do not log in, post, like, download source video, or bypass an
  access control.
- The repository snapshot script is read-only. The video evidence extractor
  writes only to the explicit output directory and refuses a non-empty target
  unless `--force` is supplied.
- Community reports mask author names by default. Keeping names is an explicit
  local-only option.

Report a security concern privately through GitHub's security advisory flow.
Do not open a public issue containing credentials or personal records.
