# ADR 0001: separate evidence ranking from financial authority

**Status:** accepted

## Context

Damaged bank references create ambiguity that deterministic exact joins cannot resolve. A probabilistic model can rank candidates, but granting the model direct closing authority would allow similarity to override financial truth.

## Decision

The model emits only a candidate score, feature evidence, and version. A deterministic policy independently evaluates source composition, amount, direction, booking window, confidence, score separation, and review requirements. Human review may approve/reject evidence but cannot mutate source facts.

## Consequences

- model outages fail safely into abstention;
- financial invariants remain unit-testable without ML;
- the product exposes why an item is in review;
- coverage is intentionally lower than an unconstrained classifier;
- production policy calibration becomes an explicit governance problem rather than a hidden model threshold.
