# Playbook discovery model

## Default discovery rule

When the caller does not provide an explicit playbook path, CLI should look for:

```text
.ordo/ordo.yaml
```

relative to the current working directory.

## Explicit playbook path

When the caller provides an explicit playbook path, that path becomes the discovery result and default discovery is skipped.

## Initial simplicity rule

The initial model should prefer a small and predictable discovery rule over aggressive filesystem search.

Implications:

- no silent fallback from `.ordo/ordo.yaml` to alternate filenames such as `playbook.yml` or `playbook.yaml`;
- no broad directory crawling as a hidden convenience mechanism;
- no dependence on shell aliases or external wrappers for the canonical discovery rule.

## Failure rule

If default discovery does not find `.ordo/ordo.yaml`, runtime should return a structured missing-playbook outcome rather than guessing a workflow file.

## Future extensions

Possible future behaviors such as parent-directory search or alternate filenames should remain explicit additions to the model rather than being assumed by convention.
