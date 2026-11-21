# Security policy

## Reporting a vulnerability

Please report security problems **privately**. Do not open a public issue or pull request.

1. Use GitHub private vulnerability reporting: open <https://github.com/dnviti/dentalcraft/security/advisories/new> (Security tab, "Report a vulnerability"). Or
2. Send an email to hello@dentalcraft.app with the subject `Security: dentalcraft`.

Please include the version (or commit), your operating system, steps to reproduce, and what you think the impact is. **Never send real patient data, scans or project files.** If a sample is needed, make a synthetic one.

This is a one-person project. Reports are handled on a best-effort basis, with no guaranteed response time. Please give a reasonable time to fix a problem before you disclose it in public. You will be credited in the fix unless you prefer not to be.

## Where to report what

This repository holds documentation, design files, hardware designs and the local CI and release scripts. Report a problem in one of the code repositories in that repository:

| Problem in | Report to |
| --- | --- |
| Engine, scanner and Bluetooth drivers, project files | [`dentalcraft-core`](https://github.com/dnviti/dentalcraft-core/security/advisories/new) |
| Aligner algorithms and export | [`dentalcraft-aligners`](https://github.com/dnviti/dentalcraft-aligners/security/advisories/new) |
| The application, sign-in client, updater, installers | [`dentalcraft-app`](https://github.com/dnviti/dentalcraft-app/security/advisories/new) |
| The website and the download and update feed | [`dentalcraft-web`](https://github.com/dnviti/dentalcraft-web/security/advisories/new) |
| The closed account server (`dentalcraft-server`) | Email hello@dentalcraft.app |

## Scope

In scope here: the scripts in `scripts/` (for example one that could run unwanted code, leak a token or sign a wrong file) and the documents when they expose something that should not be public.

Out of scope: third-party software and services. A problem in a dependency should be reported to its own project.

## Supported versions

DentalCraft is in alpha. Only the latest release receives fixes.

## Medical-device disclaimer

DentalCraft is **not a certified medical device**. It has no regulatory clearance and has not been validated for clinical use. Do not use it on patients, or to make clinical decisions, without independent professional validation. The software is provided as is, without warranty, as the [licence](LICENSE.md) says. A flaw in the output of an algorithm is a bug to report as an issue; a flaw that exposes data, runs unwanted code or bypasses a check is a security problem to report as described above.
