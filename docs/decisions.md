# Architecture Decision Records

## ADR-001: Aggregate CPU is the primary autoscaling metric

**Decision:** Aggregate CPU is the arithmetic mean of CPU utilization across active, healthy application replicas.

**Rationale:** The mean makes utilization comparable when replica counts change and supplies a single explainable target for all policies. It is used consistently in monitoring, data preparation, prediction, decisions, feedback, and evaluation.

**Consequence:** A no-healthy-replica state has no valid mean; it is not reported as zero CPU.

## ADR-002: Five-second sampling and thirty-second prediction horizon

**Decision:** Sample every five seconds and initially predict aggregate CPU 30 seconds ahead.

**Rationale:** This gives a clear six-step forecast target without introducing a complex model or ambiguous target horizon.

**Consequence:** Features must be limited to information at or before the prediction timestamp. The future observation is the label; chronological validation is mandatory.

## ADR-003: Docker API access is scoped by labels

**Decision:** The scaling controller will use the Docker Engine API through the Python Docker SDK and control only containers carrying the required project, role, and managed labels.

**Rationale:** Docker socket/API access is powerful. Label filtering creates a project-level management boundary and prevents selecting unrelated containers.

**Consequence:** This is appropriate only for the controlled local research environment and must be documented as privileged access.

## ADR-004: Nginx membership changes are validated before graceful reload

**Decision:** Use discovery → upstream generation → validation → graceful reload for every membership change.

**Rationale:** A configuration error must not replace a working load-balancer configuration. Graceful reload preserves service continuity where possible.

**Consequence:** Scale-in is ordered: update valid upstream membership first, then stop/remove the excluded replica.

## ADR-005: Adaptive replacement requires validated candidates

**Decision:** Persistent prediction error can trigger training, but a candidate replaces the active model only after it passes validation.

**Rationale:** Error alone does not establish that new training data yields a safer/better model. This prevents automatic activation of an unvalidated candidate.

**Consequence:** Adaptive retraining has five gates: error threshold, consecutive breaches, enough recent samples, elapsed cooldown, and successful candidate validation.

## ADR-006: Policy comparisons require controlled equivalence

**Decision:** Reactive, predictive, and adaptive-predictive trials must share the stated environment and starting conditions.

**Rationale:** Differences in workload, limits, or collection procedures would confound policy comparison.

**Consequence:** Experiment records must retain a configuration snapshot and environment/initial-condition metadata.
