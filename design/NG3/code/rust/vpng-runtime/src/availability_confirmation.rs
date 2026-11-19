//! Rust production-boundary implementation of the accepted availability
//! confirmation state machine.
//!
//! Semantics mirror the executable Python reference contract. This module owns no
//! scheduling, probing, routing, I/O, or user-facing timing policy.

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AvailabilityOutcome {
    Positive,
    Negative,
    NoEvidence,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct AvailabilityConfirmationState {
    availability_problem: bool,
    degradation_progress: u32,
    recovery_progress: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AvailabilityConfirmationError {
    ZeroDegradationThreshold,
    ZeroRecoveryThreshold,
    DegradationProgressWhileProblemEstablished,
    RecoveryProgressWhileNoProblemEstablished,
    DegradationProgressExceedsThreshold,
    RecoveryProgressExceedsThreshold,
}

impl AvailabilityConfirmationState {
    pub fn new(
        availability_problem: bool,
        degradation_progress: u32,
        recovery_progress: u32,
    ) -> Result<Self, AvailabilityConfirmationError> {
        let state = Self {
            availability_problem,
            degradation_progress,
            recovery_progress,
        };
        state.validate_shape()?;
        Ok(state)
    }

    pub fn availability_problem(self) -> bool {
        self.availability_problem
    }

    pub fn degradation_progress(self) -> u32 {
        self.degradation_progress
    }

    pub fn recovery_progress(self) -> u32 {
        self.recovery_progress
    }

    fn validate_shape(self) -> Result<(), AvailabilityConfirmationError> {
        if self.availability_problem && self.degradation_progress != 0 {
            return Err(
                AvailabilityConfirmationError::DegradationProgressWhileProblemEstablished,
            );
        }
        if !self.availability_problem && self.recovery_progress != 0 {
            return Err(
                AvailabilityConfirmationError::RecoveryProgressWhileNoProblemEstablished,
            );
        }
        Ok(())
    }
}

pub fn apply_availability_evidence(
    state: AvailabilityConfirmationState,
    outcome: AvailabilityOutcome,
    degradation_threshold: u32,
    recovery_threshold: u32,
) -> Result<AvailabilityConfirmationState, AvailabilityConfirmationError> {
    if degradation_threshold == 0 {
        return Err(AvailabilityConfirmationError::ZeroDegradationThreshold);
    }
    if recovery_threshold == 0 {
        return Err(AvailabilityConfirmationError::ZeroRecoveryThreshold);
    }
    state.validate_shape()?;
    if state.degradation_progress > degradation_threshold {
        return Err(
            AvailabilityConfirmationError::DegradationProgressExceedsThreshold,
        );
    }
    if state.recovery_progress > recovery_threshold {
        return Err(
            AvailabilityConfirmationError::RecoveryProgressExceedsThreshold,
        );
    }

    match outcome {
        AvailabilityOutcome::NoEvidence => Ok(state),
        AvailabilityOutcome::Positive if !state.availability_problem => Ok(
            AvailabilityConfirmationState::default(),
        ),
        AvailabilityOutcome::Negative if !state.availability_problem => {
            let progress = state.degradation_progress + 1;
            if progress >= degradation_threshold {
                Ok(AvailabilityConfirmationState {
                    availability_problem: true,
                    ..AvailabilityConfirmationState::default()
                })
            } else {
                Ok(AvailabilityConfirmationState {
                    degradation_progress: progress,
                    ..AvailabilityConfirmationState::default()
                })
            }
        }
        AvailabilityOutcome::Negative => Ok(AvailabilityConfirmationState {
            availability_problem: true,
            ..AvailabilityConfirmationState::default()
        }),
        AvailabilityOutcome::Positive => {
            let progress = state.recovery_progress + 1;
            if progress >= recovery_threshold {
                Ok(AvailabilityConfirmationState::default())
            } else {
                Ok(AvailabilityConfirmationState {
                    availability_problem: true,
                    recovery_progress: progress,
                    ..AvailabilityConfirmationState::default()
                })
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(
        availability_problem: bool,
        degradation_progress: u32,
        recovery_progress: u32,
    ) -> AvailabilityConfirmationState {
        AvailabilityConfirmationState::new(
            availability_problem,
            degradation_progress,
            recovery_progress,
        )
        .unwrap()
    }

    #[test]
    fn negative_evidence_establishes_problem_at_threshold() {
        let first = apply_availability_evidence(
            AvailabilityConfirmationState::default(),
            AvailabilityOutcome::Negative,
            2,
            2,
        )
        .unwrap();
        assert_eq!(first.degradation_progress(), 1);
        assert!(!first.availability_problem());

        let second = apply_availability_evidence(
            first,
            AvailabilityOutcome::Negative,
            2,
            2,
        )
        .unwrap();
        assert_eq!(second, state(true, 0, 0));
    }

    #[test]
    fn positive_clears_degradation_progress() {
        let next = apply_availability_evidence(
            state(false, 1, 0),
            AvailabilityOutcome::Positive,
            3,
            2,
        )
        .unwrap();
        assert_eq!(next, AvailabilityConfirmationState::default());
    }

    #[test]
    fn positive_evidence_recovers_at_threshold() {
        let first = apply_availability_evidence(
            state(true, 0, 0),
            AvailabilityOutcome::Positive,
            2,
            2,
        )
        .unwrap();
        assert_eq!(first.recovery_progress(), 1);

        let second = apply_availability_evidence(
            first,
            AvailabilityOutcome::Positive,
            2,
            2,
        )
        .unwrap();
        assert_eq!(second, AvailabilityConfirmationState::default());
    }

    #[test]
    fn negative_clears_recovery_progress() {
        let next = apply_availability_evidence(
            state(true, 0, 1),
            AvailabilityOutcome::Negative,
            2,
            3,
        )
        .unwrap();
        assert_eq!(next, state(true, 0, 0));
    }

    #[test]
    fn no_evidence_is_neutral() {
        for current in [state(false, 1, 0), state(true, 0, 1)] {
            let next = apply_availability_evidence(
                current,
                AvailabilityOutcome::NoEvidence,
                3,
                3,
            )
            .unwrap();
            assert_eq!(next, current);
        }
    }

    #[test]
    fn zero_thresholds_are_rejected() {
        assert_eq!(
            apply_availability_evidence(
                AvailabilityConfirmationState::default(),
                AvailabilityOutcome::Negative,
                0,
                1,
            ),
            Err(AvailabilityConfirmationError::ZeroDegradationThreshold)
        );
        assert_eq!(
            apply_availability_evidence(
                AvailabilityConfirmationState::default(),
                AvailabilityOutcome::Negative,
                1,
                0,
            ),
            Err(AvailabilityConfirmationError::ZeroRecoveryThreshold)
        );
    }

    #[test]
    fn invalid_state_shape_is_rejected() {
        assert_eq!(
            AvailabilityConfirmationState::new(true, 1, 0),
            Err(
                AvailabilityConfirmationError::DegradationProgressWhileProblemEstablished
            )
        );
        assert_eq!(
            AvailabilityConfirmationState::new(false, 0, 1),
            Err(
                AvailabilityConfirmationError::RecoveryProgressWhileNoProblemEstablished
            )
        );
    }

    #[test]
    fn progress_outside_current_threshold_is_rejected() {
        assert_eq!(
            apply_availability_evidence(
                state(false, 3, 0),
                AvailabilityOutcome::NoEvidence,
                2,
                2,
            ),
            Err(
                AvailabilityConfirmationError::DegradationProgressExceedsThreshold
            )
        );
        assert_eq!(
            apply_availability_evidence(
                state(true, 0, 3),
                AvailabilityOutcome::NoEvidence,
                2,
                2,
            ),
            Err(
                AvailabilityConfirmationError::RecoveryProgressExceedsThreshold
            )
        );
    }
}
