//! Bounded availability Manager semantic core.
//!
//! This module consumes already-normalized current Profile/path membership and current
//! probe observation contexts. Configuration parsing and enabled-Profile set validation
//! remain outside this core until the Rust ConfigurationAdapter is ported.

use std::collections::{HashMap, HashSet};

use crate::availability_confirmation::{
    AvailabilityConfirmationError, AvailabilityConfirmationState, apply_availability_evidence,
};
use crate::availability_routing_state::{AvailabilityRoutingState, project_availability_routing};
use crate::logical_path::LogicalPathId;
use crate::probe_context::{ProbeEvidence, ProbeObservationContext, ProbePolicyOwner};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AvailabilityManagerPolicy {
    degradation_threshold: u32,
    recovery_threshold: u32,
}

impl AvailabilityManagerPolicy {
    pub fn new(
        degradation_threshold: u32,
        recovery_threshold: u32,
    ) -> Result<Self, AvailabilityManagerError> {
        if degradation_threshold == 0 {
            return Err(AvailabilityManagerError::ZeroDegradationThreshold);
        }
        if recovery_threshold == 0 {
            return Err(AvailabilityManagerError::ZeroRecoveryThreshold);
        }
        Ok(Self {
            degradation_threshold,
            recovery_threshold,
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AvailabilityProfileInput {
    profile_id: String,
    ordered_paths: Vec<LogicalPathId>,
    reserve_device_ids: Vec<String>,
}

impl AvailabilityProfileInput {
    pub fn new(
        profile_id: impl Into<String>,
        ordered_paths: Vec<LogicalPathId>,
        reserve_device_ids: Vec<String>,
    ) -> Result<Self, AvailabilityManagerError> {
        let profile_id = profile_id.into();
        if profile_id.is_empty() {
            return Err(AvailabilityManagerError::EmptyProfileId);
        }
        Ok(Self {
            profile_id,
            ordered_paths,
            reserve_device_ids,
        })
    }

    pub fn profile_id(&self) -> &str {
        &self.profile_id
    }

    pub fn ordered_paths(&self) -> &[LogicalPathId] {
        &self.ordered_paths
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct AvailabilitySubjectState {
    context: ProbeObservationContext,
    confirmation: AvailabilityConfirmationState,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EffectiveAvailabilityProfile {
    pub profile_id: String,
    pub ordered_paths: Vec<LogicalPathId>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AvailabilityManagerProjection {
    pub effective_profiles: Vec<EffectiveAvailabilityProfile>,
    pub problem_owners: HashSet<ProbePolicyOwner>,
}

#[derive(Debug)]
pub struct AvailabilityManager {
    policy: AvailabilityManagerPolicy,
    subjects: HashMap<ProbePolicyOwner, AvailabilitySubjectState>,
    routing: HashMap<String, AvailabilityRoutingState>,
}

impl AvailabilityManager {
    pub fn new(policy: AvailabilityManagerPolicy) -> Self {
        Self {
            policy,
            subjects: HashMap::new(),
            routing: HashMap::new(),
        }
    }

    pub fn synchronize(
        &mut self,
        contexts: &[ProbeObservationContext],
        profiles: &[AvailabilityProfileInput],
    ) -> Result<AvailabilityManagerProjection, AvailabilityManagerError> {
        validate_profiles(profiles)?;
        validate_contexts(contexts, profiles)?;

        let mut next_subjects = HashMap::new();
        for context in contexts {
            let owner = context.owner().clone();
            let state = match self.subjects.get(&owner) {
                Some(previous) if previous.context == *context => previous.clone(),
                _ => AvailabilitySubjectState {
                    context: context.clone(),
                    confirmation: AvailabilityConfirmationState::default(),
                },
            };
            next_subjects.insert(owner, state);
        }
        self.subjects = next_subjects;
        self.project(profiles)
    }

    pub fn apply_evidence(
        &mut self,
        evidence: &ProbeEvidence,
        profiles: &[AvailabilityProfileInput],
    ) -> Result<AvailabilityManagerProjection, AvailabilityManagerError> {
        validate_profiles(profiles)?;

        let owner = evidence.context.owner();
        let current = self
            .subjects
            .get(owner)
            .ok_or(AvailabilityManagerError::StaleEvidence)?;
        if current.context != evidence.context {
            return Err(AvailabilityManagerError::StaleEvidence);
        }

        let confirmation = apply_availability_evidence(
            current.confirmation,
            evidence.outcome,
            self.policy.degradation_threshold,
            self.policy.recovery_threshold,
        )
        .map_err(AvailabilityManagerError::Confirmation)?;

        self.subjects.insert(
            owner.clone(),
            AvailabilitySubjectState {
                context: current.context.clone(),
                confirmation,
            },
        );
        self.project(profiles)
    }

    fn project(
        &mut self,
        profiles: &[AvailabilityProfileInput],
    ) -> Result<AvailabilityManagerProjection, AvailabilityManagerError> {
        let problem_owners: HashSet<_> = self
            .subjects
            .iter()
            .filter(|(_, state)| state.confirmation.availability_problem())
            .map(|(owner, _)| owner.clone())
            .collect();

        let mut ordered_profiles: Vec<_> = profiles.iter().collect();
        ordered_profiles.sort_by(|left, right| left.profile_id.cmp(&right.profile_id));

        let mut effective_profiles = Vec::with_capacity(ordered_profiles.len());
        let mut next_routing = HashMap::new();

        for profile in ordered_profiles {
            let problem_paths: Vec<_> = profile
                .ordered_paths
                .iter()
                .filter(|path| {
                    let owner = ProbePolicyOwner::new(profile.profile_id.clone(), (*path).clone())
                        .expect("validated non-empty Profile ID");
                    problem_owners.contains(&owner)
                })
                .cloned()
                .collect();

            let previous = self
                .routing
                .get(&profile.profile_id)
                .cloned()
                .unwrap_or_default();

            let projected = project_availability_routing(
                &profile.ordered_paths,
                &problem_paths,
                &previous,
                &profile.reserve_device_ids,
            )
            .map_err(AvailabilityManagerError::Priority)?;

            next_routing.insert(profile.profile_id.clone(), projected.next_state);
            effective_profiles.push(EffectiveAvailabilityProfile {
                profile_id: profile.profile_id.clone(),
                ordered_paths: projected.effective_order,
            });
        }

        self.routing = next_routing;
        Ok(AvailabilityManagerProjection {
            effective_profiles,
            problem_owners,
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum AvailabilityManagerError {
    ZeroDegradationThreshold,
    ZeroRecoveryThreshold,
    EmptyProfileId,
    DuplicateProfile,
    DuplicateContextOwner,
    ContextOutsideProfileMembership,
    StaleEvidence,
    Confirmation(AvailabilityConfirmationError),
    Priority(crate::availability_priority::AvailabilityPriorityError),
}

fn validate_profiles(
    profiles: &[AvailabilityProfileInput],
) -> Result<(), AvailabilityManagerError> {
    let mut seen = HashSet::new();
    for profile in profiles {
        if !seen.insert(profile.profile_id.as_str()) {
            return Err(AvailabilityManagerError::DuplicateProfile);
        }
    }
    Ok(())
}

fn validate_contexts(
    contexts: &[ProbeObservationContext],
    profiles: &[AvailabilityProfileInput],
) -> Result<(), AvailabilityManagerError> {
    let by_profile: HashMap<_, _> = profiles
        .iter()
        .map(|profile| (profile.profile_id.as_str(), profile))
        .collect();

    let mut owners = HashSet::new();
    for context in contexts {
        if !owners.insert(context.owner()) {
            return Err(AvailabilityManagerError::DuplicateContextOwner);
        }
        let owner = context.owner();
        let Some(profile) = by_profile.get(owner.profile_id()) else {
            return Err(AvailabilityManagerError::ContextOutsideProfileMembership);
        };
        if !profile.ordered_paths.contains(owner.path_id()) {
            return Err(AvailabilityManagerError::ContextOutsideProfileMembership);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::net::Ipv4Addr;

    use super::*;
    use crate::availability_confirmation::AvailabilityOutcome;
    use crate::probe_context::{AvailabilityProbeIntent, InterfaceIdentity, ProbeEvidence};

    fn path(device: &str) -> LogicalPathId {
        LogicalPathId::new(device, 0, 0).unwrap()
    }

    fn profile(reserve: bool) -> AvailabilityProfileInput {
        AvailabilityProfileInput::new(
            "corp",
            vec![path("wg"), path("oc")],
            if reserve {
                vec!["oc".to_string()]
            } else {
                vec![]
            },
        )
        .unwrap()
    }

    fn context(
        path_id: LogicalPathId,
        ifname: &str,
        ifindex: u32,
        generation: u64,
    ) -> ProbeObservationContext {
        let owner = ProbePolicyOwner::new("corp", path_id).unwrap();
        ProbeObservationContext::new(
            AvailabilityProbeIntent::icmp(owner, Ipv4Addr::new(198, 51, 100, 10)),
            InterfaceIdentity::new(ifname, ifindex).unwrap(),
            generation,
        )
        .unwrap()
    }

    fn evidence(context: ProbeObservationContext, outcome: AvailabilityOutcome) -> ProbeEvidence {
        ProbeEvidence { context, outcome }
    }

    #[test]
    fn degradation_requires_threshold_then_reorders() {
        let mut manager = AvailabilityManager::new(AvailabilityManagerPolicy::new(2, 2).unwrap());
        let p = profile(false);
        let a = context(path("wg"), "wg0", 10, 1);
        let b = context(path("oc"), "oc0", 20, 1);
        manager
            .synchronize(&[a.clone(), b], std::slice::from_ref(&p))
            .unwrap();

        let one = manager
            .apply_evidence(
                &evidence(a.clone(), AvailabilityOutcome::Negative),
                std::slice::from_ref(&p),
            )
            .unwrap();
        assert_eq!(
            one.effective_profiles[0].ordered_paths,
            vec![path("wg"), path("oc")]
        );

        let two = manager
            .apply_evidence(
                &evidence(a, AvailabilityOutcome::Negative),
                std::slice::from_ref(&p),
            )
            .unwrap();
        assert_eq!(
            two.effective_profiles[0].ordered_paths,
            vec![path("oc"), path("wg")]
        );
        assert_eq!(two.problem_owners.len(), 1);
    }

    #[test]
    fn recovery_is_sticky_for_ordinary_active_path() {
        let mut manager = AvailabilityManager::new(AvailabilityManagerPolicy::new(1, 2).unwrap());
        let p = profile(false);
        let a = context(path("wg"), "wg0", 10, 1);
        let b = context(path("oc"), "oc0", 20, 1);
        manager
            .synchronize(&[a.clone(), b], std::slice::from_ref(&p))
            .unwrap();

        manager
            .apply_evidence(
                &evidence(a.clone(), AvailabilityOutcome::Negative),
                std::slice::from_ref(&p),
            )
            .unwrap();
        manager
            .apply_evidence(
                &evidence(a.clone(), AvailabilityOutcome::Positive),
                std::slice::from_ref(&p),
            )
            .unwrap();
        let recovered = manager
            .apply_evidence(
                &evidence(a, AvailabilityOutcome::Positive),
                std::slice::from_ref(&p),
            )
            .unwrap();

        assert!(recovered.problem_owners.is_empty());
        assert_eq!(
            recovered.effective_profiles[0].ordered_paths,
            vec![path("oc"), path("wg")]
        );
    }

    #[test]
    fn reserve_active_yields_on_recovery() {
        let mut manager = AvailabilityManager::new(AvailabilityManagerPolicy::new(1, 1).unwrap());
        let p = profile(true);
        let a = context(path("wg"), "wg0", 10, 1);
        let b = context(path("oc"), "oc0", 20, 1);
        manager
            .synchronize(&[a.clone(), b], std::slice::from_ref(&p))
            .unwrap();

        manager
            .apply_evidence(
                &evidence(a.clone(), AvailabilityOutcome::Negative),
                std::slice::from_ref(&p),
            )
            .unwrap();
        let recovered = manager
            .apply_evidence(
                &evidence(a, AvailabilityOutcome::Positive),
                std::slice::from_ref(&p),
            )
            .unwrap();

        assert_eq!(
            recovered.effective_profiles[0].ordered_paths,
            vec![path("wg"), path("oc")]
        );
    }

    #[test]
    fn context_change_resets_confirmation_and_stale_evidence_is_rejected() {
        let mut manager = AvailabilityManager::new(AvailabilityManagerPolicy::new(2, 2).unwrap());
        let p = profile(false);
        let a1 = context(path("wg"), "wg0", 10, 1);
        let a2 = context(path("wg"), "wg0", 10, 2);
        let b = context(path("oc"), "oc0", 20, 1);

        manager
            .synchronize(&[a1.clone(), b.clone()], std::slice::from_ref(&p))
            .unwrap();
        manager
            .apply_evidence(
                &evidence(a1.clone(), AvailabilityOutcome::Negative),
                std::slice::from_ref(&p),
            )
            .unwrap();

        manager
            .synchronize(&[a2.clone(), b], std::slice::from_ref(&p))
            .unwrap();

        assert_eq!(
            manager.apply_evidence(
                &evidence(a1, AvailabilityOutcome::Negative),
                std::slice::from_ref(&p),
            ),
            Err(AvailabilityManagerError::StaleEvidence)
        );

        let projected = manager
            .apply_evidence(
                &evidence(a2, AvailabilityOutcome::Negative),
                std::slice::from_ref(&p),
            )
            .unwrap();
        assert!(projected.problem_owners.is_empty());
    }

    #[test]
    fn no_evidence_is_neutral() {
        let mut manager = AvailabilityManager::new(AvailabilityManagerPolicy::new(1, 1).unwrap());
        let p = profile(false);
        let a = context(path("wg"), "wg0", 10, 1);
        let b = context(path("oc"), "oc0", 20, 1);
        manager
            .synchronize(&[a.clone(), b], std::slice::from_ref(&p))
            .unwrap();

        let projected = manager
            .apply_evidence(
                &evidence(a, AvailabilityOutcome::NoEvidence),
                std::slice::from_ref(&p),
            )
            .unwrap();

        assert!(projected.problem_owners.is_empty());
        assert_eq!(
            projected.effective_profiles[0].ordered_paths,
            vec![path("wg"), path("oc")]
        );
    }
}
