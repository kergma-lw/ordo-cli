# Runtime profiles

Runtime profiles are named operational contexts for playbook runs.

They exist to answer questions such as:

- which repository-facing inputs should this run use;
- which workflow-entry execution location should this run activate;
- which approved runtime-facing modifiers belong to this run.

This makes profiles the natural project-local place to bind execution-facing context such as launcher selection inputs, while still keeping launcher usage explicit at the step level.

Profiles should stay declarative and reviewable.

They are not meant to become a shadow workflow language or a place to hide unrelated business policy.
