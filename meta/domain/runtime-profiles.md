# Runtime profiles

Runtime profiles are named operational contexts for playbook runs.

They exist to answer questions such as:

- which repository-facing inputs should this run use;
- which workflow-entry execution location should this run activate;
- which approved runtime-facing modifiers belong to this run.

Historically this made profiles the natural project-local place to bind execution-facing context such as launcher selection inputs, while still keeping launcher usage explicit at the step level.

With routine publication available, launcher-centric profile context is now legacy-oriented rather than the preferred steady-state path.

It also makes profile switching a plausible runtime-owned context surface, as long as switching remains explicit, inspectable, and separate from workflow-owned business state.

When a workflow invokes a project-local routine, profile-carried workflow values may still influence that local process, but only through explicit workflow-owned forwarding such as `with.env` rather than through an automatic profile-name environment variable.

That switching should be modeled as an engine-level construct such as `profile_switch`, not as an ordinary connector action.

Profiles should stay declarative and reviewable.

They are not meant to become a shadow workflow language or a place to hide unrelated business policy.
