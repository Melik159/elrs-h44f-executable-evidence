# ELRS 4.1 and H44F Evidence Summary

## Associated preprint

The preprint PDFs are distributed separately through HAL and are intentionally
excluded from this executable-evidence repository. `CITATION.cff` retains the
associated bibliographic metadata.

| Campaign | Public UUID | Nature | Main result | Verdict |
|---|---|---|---|---|
| ELRS 1–4.0 multiversion | — | family-specific software validation | 31,981,568 entries, negative control, and 64/64 deterministic round trips | PASS |
| ELRS 4.1 exhaustive | — | software validation against pinned upstream sources | 32,768 classes × 240 positions: 7,864,320 comparisons without divergence | PASS |
| H44F-A | `5e47158c-14cb-4395-a803-47ea468e8e8a` | complete blind hardware campaign | unique 50 Hz profile, UID2/UID3 reconstruction, 960/960 following, controlled substitution and recovery | PASS |
| H44F-B | `583431a1-9948-4173-9b9b-14954169cb33` | fast RX-only validation | one class selected among 32,768 from five hops, followed by 20/20 packet following | PASS |

## Offline reproduction results

The ELRS 4.1 validation is pinned to tag `4.1.0`, commit
`a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6`. The upstream C++ reference and
the distributed Python implementation produce identical matrices with
SHA-256:

```text
a82024c1f89fcde103406c633fa8495b0bd6cea50c5762ef5cd51d8eb02ff303
```

Together with the 31,981,568 entries from the earlier multiversion validation,
the additional 7,864,320 ELRS 4.1 positions bring the combined offline
coverage to 39,845,888 positions.

H44F-A and H44F-B independently reproduce the following operational state:

- profile: `LORA_900_50HZ`, `enum_rate=1`;
- FHSS-equivalent UID2 values: `3F|BF`;
- UID3–5: `35:59:F0`;
- base CRC initializer: `0x5DF0`;
- seeds: `0x3F3559F4` and `0xBF3559F4`;
- FHSS-table SHA-256:
  `51e295622b4d8e769f9920301ad4759f9b0a9d0af207341e4ae99fa02e118f57`;
- binding phrase recovered: no.

## What each hardware record establishes

H44F-A establishes the integrated chain: passive profile selection, state
purging, blind reconstruction of the operational radio state, following all
240 positions over 960 slots, controlled substitution on a stock receiver,
source retention, and legitimate-source recovery. All 5,671 RAW records replay
without CRC, shape, or sequence errors.

H44F-B is a shorter, strictly RX-only proof. Five positive observations reduce
the 32,768 canonical classes to one class. The retained model contains four
exact matches and one adjacent-channel observation. A fresh acquisition then
confirms five hops through 20 valid packets without CRC errors or channel
divergence.

## Limitations

The exhaustive ELRS 4.1 result covers the FCC915/SX127X FHSS model and is not a
universal RF validation. The hardware logs prove the selected runs, not every
ExpressLRS version, band, radio, or configuration. H44F-B performs no
substitution. The binding phrase is neither supplied nor recovered; recovering
it is unnecessary for the operational radio-state reconstruction demonstrated
here.
