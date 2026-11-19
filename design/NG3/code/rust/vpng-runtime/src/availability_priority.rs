//! Pure sticky/reserve availability ordering.
//!
//! This mirrors the accepted Python AvailabilityPriorityCalculator contract.
//! Membership is never added or removed; availability changes only effective order.

use std::collections::HashSet;

use crate::logical_path::LogicalPathId;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum AvailabilityPriorityError {
    DuplicateConfiguredPath,
    DuplicateProblemPath,
    DuplicateReserveDevice,
    EmptyReserveDeviceId,
    ProblemPathOutsideMembership,
    ActivePathOutsideMembership,
}

pub fn calculate_effective_path_order(
    configured_paths: &[LogicalPathId],
    problem_paths: &[LogicalPathId],
    active_path: Option<&LogicalPathId>,
    reserve_device_ids: &[String],
) -> Result<Vec<LogicalPathId>, AvailabilityPriorityError> {
    ensure_unique_paths(
        configured_paths,
        AvailabilityPriorityError::DuplicateConfiguredPath,
    )?;
    ensure_unique_paths(
        problem_paths,
        AvailabilityPriorityError::DuplicateProblemPath,
    )?;

    let mut reserve_devices = HashSet::new();
    for device_id in reserve_device_ids {
        if device_id.is_empty() {
            return Err(AvailabilityPriorityError::EmptyReserveDeviceId);
        }
        if !reserve_devices.insert(device_id.as_str()) {
            return Err(AvailabilityPriorityError::DuplicateReserveDevice);
        }
    }

    let configured_set: HashSet<_> = configured_paths.iter().collect();
    if problem_paths
        .iter()
        .any(|path| !configured_set.contains(path))
    {
        return Err(AvailabilityPriorityError::ProblemPathOutsideMembership);
    }
    if active_path.is_some_and(|path| !configured_set.contains(path)) {
        return Err(AvailabilityPriorityError::ActivePathOutsideMembership);
    }

    let problems: HashSet<_> = problem_paths.iter().collect();
    let usable: Vec<_> = configured_paths
        .iter()
        .filter(|path| !problems.contains(path))
        .cloned()
        .collect();
    let problem_tail: Vec<_> = configured_paths
        .iter()
        .filter(|path| problems.contains(path))
        .cloned()
        .collect();

    let usable_order = match active_path {
        None => usable,
        Some(active) if problems.contains(active) => usable,
        Some(active) if !reserve_devices.contains(active.device_id()) => {
            sticky_first(active, &usable)
        }
        Some(active) => {
            let active_index = configured_paths
                .iter()
                .position(|path| path == active)
                .expect("active membership validated above");
            let higher_usable_exists = configured_paths
                .iter()
                .take(active_index)
                .any(|path| !problems.contains(path));
            if higher_usable_exists {
                usable
            } else {
                sticky_first(active, &usable)
            }
        }
    };

    Ok(usable_order
        .into_iter()
        .chain(problem_tail)
        .collect())
}

fn sticky_first(
    active: &LogicalPathId,
    usable: &[LogicalPathId],
) -> Vec<LogicalPathId> {
    std::iter::once(active.clone())
        .chain(usable.iter().filter(|path| *path != active).cloned())
        .collect()
}

fn ensure_unique_paths(
    paths: &[LogicalPathId],
    duplicate_error: AvailabilityPriorityError,
) -> Result<(), AvailabilityPriorityError> {
    let mut seen = HashSet::new();
    for path in paths {
        if !seen.insert(path) {
            return Err(duplicate_error);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(device: &str, selector: u32, slot: u32) -> LogicalPathId {
        LogicalPathId::new(device, selector, slot).unwrap()
    }

    fn fixtures() -> (LogicalPathId, LogicalPathId, LogicalPathId, LogicalPathId) {
        (p("oc", 0, 0), p("oc", 0, 1), p("wg", 0, 0), p("wg", 1, 0))
    }

    #[test]
    fn no_state_preserves_configured_order() {
        let (a, b, c, _) = fixtures();
        let configured = vec![a, b, c];
        assert_eq!(
            calculate_effective_path_order(&configured, &[], None, &[]).unwrap(),
            configured
        );
    }

    #[test]
    fn one_problem_moves_after_nonproblem_paths() {
        let (a, b, c, _) = fixtures();
        assert_eq!(
            calculate_effective_path_order(
                &[a.clone(), b.clone(), c.clone()],
                std::slice::from_ref(&a),
                None,
                &[],
            )
            .unwrap(),
            vec![b, c, a]
        );
    }

    #[test]
    fn multiple_problems_preserve_relative_order_in_both_groups() {
        let (a, b, c, d) = fixtures();
        assert_eq!(
            calculate_effective_path_order(
                &[a.clone(), b.clone(), c.clone(), d.clone()],
                &[d.clone(), b.clone()],
                None,
                &[],
            )
            .unwrap(),
            vec![a, c, b, d]
        );
    }

    #[test]
    fn ordinary_recovery_does_not_preempt_active_path() {
        let (a, b, c, _) = fixtures();
        let configured = vec![a.clone(), b.clone(), c.clone()];
        assert_eq!(
            calculate_effective_path_order(
                &configured,
                std::slice::from_ref(&a),
                Some(&b),
                &[],
            )
            .unwrap(),
            vec![b.clone(), c.clone(), a.clone()]
        );
        assert_eq!(
            calculate_effective_path_order(
                &configured,
                &[],
                Some(&b),
                &[],
            )
            .unwrap(),
            vec![b, a, c]
        );
    }

    #[test]
    fn reserve_active_yields_to_higher_usable_path() {
        let (a, b, c, _) = fixtures();
        assert_eq!(
            calculate_effective_path_order(
                &[a.clone(), b.clone(), c.clone()],
                &[],
                Some(&b),
                &["oc".to_string()],
            )
            .unwrap(),
            vec![a, b, c]
        );
    }

    #[test]
    fn reserve_active_stays_first_when_higher_paths_are_problematic() {
        let (a, b, c, _) = fixtures();
        assert_eq!(
            calculate_effective_path_order(
                &[a.clone(), b.clone(), c.clone()],
                std::slice::from_ref(&a),
                Some(&b),
                &["oc".to_string()],
            )
            .unwrap(),
            vec![b, c, a]
        );
    }

    #[test]
    fn problematic_active_loses_sticky_position() {
        let (a, b, c, _) = fixtures();
        assert_eq!(
            calculate_effective_path_order(
                &[a.clone(), b.clone(), c.clone()],
                std::slice::from_ref(&b),
                Some(&b),
                &[],
            )
            .unwrap(),
            vec![a, c, b]
        );
    }

    #[test]
    fn all_problem_paths_preserve_configured_order() {
        let (a, b, c, _) = fixtures();
        let configured = vec![a.clone(), b.clone(), c.clone()];
        assert_eq!(
            calculate_effective_path_order(
                &configured,
                &[c, a, b.clone()],
                Some(&b),
                &[],
            )
            .unwrap(),
            configured
        );
    }

    #[test]
    fn empty_membership_is_valid() {
        assert_eq!(
            calculate_effective_path_order(&[], &[], None, &[]).unwrap(),
            Vec::<LogicalPathId>::new()
        );
    }

    #[test]
    fn invalid_membership_inputs_are_rejected() {
        let (a, b, c, _) = fixtures();
        assert_eq!(
            calculate_effective_path_order(
                &[a.clone(), a.clone()],
                &[],
                None,
                &[],
            ),
            Err(AvailabilityPriorityError::DuplicateConfiguredPath)
        );
        assert_eq!(
            calculate_effective_path_order(
                &[a.clone(), b.clone()],
                &[a.clone(), a],
                None,
                &[],
            ),
            Err(AvailabilityPriorityError::DuplicateProblemPath)
        );
        assert_eq!(
            calculate_effective_path_order(
                &[b.clone()],
                std::slice::from_ref(&c),
                None,
                &[],
            ),
            Err(AvailabilityPriorityError::ProblemPathOutsideMembership)
        );
        assert_eq!(
            calculate_effective_path_order(
                &[b],
                &[],
                Some(&c),
                &[],
            ),
            Err(AvailabilityPriorityError::ActivePathOutsideMembership)
        );
    }

    #[test]
    fn reserve_device_inputs_are_strict() {
        let (a, _, _, _) = fixtures();
        assert_eq!(
            calculate_effective_path_order(
                std::slice::from_ref(&a),
                &[],
                None,
                &["".to_string()],
            ),
            Err(AvailabilityPriorityError::EmptyReserveDeviceId)
        );
        assert_eq!(
            calculate_effective_path_order(
                std::slice::from_ref(&a),
                &[],
                None,
                &["oc".to_string(), "oc".to_string()],
            ),
            Err(AvailabilityPriorityError::DuplicateReserveDevice)
        );
    }
}
