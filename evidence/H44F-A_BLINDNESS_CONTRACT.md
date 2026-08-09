# H44F-A blindness contract

Before reconstruction completes, all configuration headers, commands and
runtime inputs prohibit:

- binding phrase;
- UID0 through UID5;
- CRC initializer;
- FHSS seed;
- FHSS sequence;
- active-profile oracle.

The profile-selection stage receives only the six tuples derived from the
pinned ExpressLRS 4.1 source. GPIO47 carries only synthetic CRSF channel
stimulus generated from the runner challenge; it carries no ExpressLRS
identity.

After cold profile confirmation, the sweep identity, classifier and radio state
are purged. Only the selected public radio profile crosses into the core. The
core must obtain a fresh SYNC before it may infer UID4/UID5, derive the CRC
initializer or constrain UID2/UID3 from positive frequency observations.

The binding phrase is neither supplied nor recovered. It is not required for
the controlled substitution demonstrated within the test-bench scope.
