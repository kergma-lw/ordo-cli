# Git tag inspection requirements

- `git.tag` observes one exact local tag name. It reports the tag ref's stored object as `oid` and whether that object is an annotated tag object through `annotated`.
- `target_oid` and `target_type` describe the tag after Git peels any annotated-tag layers. They are distinct from `oid`: an annotated tag's stored object is a tag object while its target can be a commit, tree, or blob.
- A missing tag is normal success with `exists: false` and null object/target facts. An existing tag with unreadable or unsupported object facts is a probe failure, not a weakened result.
- Workflows that release commits must require `annotated: true`, `target_type: commit`, and an exact expected `target_oid`. A local observation is not an atomic guarantee against a later remote tag change.
