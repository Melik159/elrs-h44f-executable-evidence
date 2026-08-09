# H44F-A preregistered acceptance criteria

## Profile selection

- Exactly six pinned FCC915 profile records.
- Exactly one CRC-valid SYNC profile winner.
- Cold confirmation of the same rate and UID4/UID5.
- No RF TX during sweep or confirmation.
- GPIO47 stimulus active during sweep and stopped before handoff.
- Sweep identity and classifier state purged; radio reinitialized.
- OTA8 and DVDA handoff prohibited.

## Blind reconstruction and follow

- No binding phrase, target UID, CRC initializer, FHSS seed or table supplied.
- At least two consistent OTA4 SYNC packets.
- At least three positive `(fhss_index, channel)` observations.
- Exactly one effective radio-equivalence class; any UID2 bit-7 aliases must
  produce identical 240-position tables.
- Fresh runtime SYNC after the purge.
- Complete 240-hop tour, at least 500 valid packets, no CRC or channel error.

## Controlled active phase

- Physical Aeris-off confirmation before Heltec TX.
- Bounded minimum-power TX, zero TX timeout and zero retune failure.
- Aeris return confirmed within the preregistered slot window.
- Source attribution, incumbent persistence and final Aeris recovery pass.
- Complete RAW capture without overflow, CRC, shape or sequence error.
- Final RF and GPIO state safe.

## Verdict

`H44F_CORE_RESULT ... verdict=PASS`, `H44F_RESULT ... verdict=PASS`,
`H44F_CORE_OFFLINE_VERDICT=PASS`, `H44F_OFFLINE_VERDICT=PASS` and
`H44F_PUBLIC_SANITIZATION_PASS=YES` are all required. Host tests and a build
alone never establish a hardware PASS.
