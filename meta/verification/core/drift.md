# Verification

## Drift checks

At minimum the project must be able to check:

- workflow examples validate against schema;
- generated packs are in sync with source docs;
- public docs do not contradict core contract docs;
- connector contract changes are reflected in examples and schema where relevant.

## Review rule

If schema or runtime semantics change, corresponding `meta/` source docs must change in the same work.
