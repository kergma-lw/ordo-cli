# ADR 0003: packs are derived

## Decision

`meta/packs/**` is generated from source docs under `meta/{requirements,domain,model,data,scenarios,adr,verification}`.

## Why

This keeps source-of-truth documents editable while allowing compact derived packs for agents and later tooling.
