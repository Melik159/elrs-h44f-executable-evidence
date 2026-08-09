# ELRS 4.1 and H44F Executable Evidence — Compact Package

This repository is the concise entry point for the evidence package. It
contains the multiversion and ELRS 4.1 exhaustive validations, the two retained
H44F campaigns, anonymized logs, and the programs required for offline
verification.

## One-command verification

```bash
./verify.sh
```

GitHub-generated ZIP archives may not preserve executable permission bits. In
that case, run the identical entry point explicitly through Bash:

```bash
bash verify.sh
```

The command verifies every distributed file against the SHA-256 manifest,
checks the public records for private paths, host identifiers and absolute
timestamps, validates the exhaustive ELRS 4.1 evidence, replays the H44F-A and
H44F-B campaign verifiers, reproduces the 5,671 H44F-A RAW records in a
temporary directory, and independently recomputes both FHSS reconstructions.
No large derived output is retained.

Success is identified by the final line:

```text
COMPACT_EVIDENCE_VERDICT=PASS
```

Run `./verify.sh --verbose` to display the detailed output of each verifier.

## Repository contents

- `EVIDENCE_SUMMARY.md`: one-page result and limitation summary;
- `evidence/`: sanitized multiversion and ELRS 4.1 exhaustive records, two
  anonymized hardware logs, their metadata, and the H44F-A contract;
- `scripts/`: verifiers, RAW parser, independent reconstruction programs, and
  the optional upstream-source replay;
- `scripts/elrs41_reference/host_stubs/`: minimal host-build declarations
  required by upstream `FHSS.cpp`; no FHSS or radio behavior is mocked;
- `MANIFEST_SHA256.txt`: SHA-256 digest of every evidence, verifier,
  documentation, and license payload file except the manifest itself.
  Repository packaging metadata such as `.gitignore` is intentionally outside
  the evidence integrity boundary.

The package contains no binding phrase, flashable active firmware, hardware
runner, or RF transmission tool.

## Licensing and citation

Original software is licensed under Apache License 2.0. Documentation,
sanitized evidence records, and logs are licensed under Creative Commons
Attribution 4.0 International. See `LICENSE` and `LICENSES/`. Citation metadata
are provided in `CITATION.cff`.

The preprint PDFs are intentionally not distributed in this repository. They
are deposited separately through HAL; this repository contains only the
executable and anonymized evidence package.

## Full replay against the ExpressLRS 4.1 sources

The one-command verification checks the sanitized validation record and its
cryptographic anchors. To recompute all 7,864,320 positions directly from the
pinned upstream sources, run:

```bash
./scripts/replay_elrs41_upstream.sh /path/to/ExpressLRS-4.1.0
```

The supplied checkout must be clean and positioned exactly at commit
`a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6`. The script also verifies the
four FHSS source-file digests, compiles a host-only executable, generates the
upstream and Python matrices in a temporary directory, and requires byte-for-
byte equality. It neither builds nor flashes embedded firmware.
