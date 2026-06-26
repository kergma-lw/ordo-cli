# Resolution policy

## Baseline

Workflow references are resolved against public connector operations.

## Default policy

- same-name silent shadowing is not default behavior
- base public connector semantics must remain stable
- local adaptation must be explicit

## Allowed local adaptation

- local namespaces such as `local.*` or `project.*`
- explicit override mechanisms, if the runtime exposes them
- profiles as composition/preset layer

## Not allowed by default

- silent replacement of `gh.*`, `git.*`, or `shell.*`
- same-name semantic drift hidden from workflow readers

## Why

Workflow readability and portability depend on visible resolution semantics.
