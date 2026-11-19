//! Pure bounded sticky/reserve routing-state projection for one Profile.

use std::collections::HashSet;

use crate::availability_priority::{AvailabilityPriorityError, calculate_effective_path_order};
use crate::logical_path::LogicalPathId;

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct AvailabilityRoutingState {
    active_path: Option<LogicalPathId>,
}

impl AvailabilityRoutingState {
    pub fn new(active_path: Option<LogicalPathId>) -> Self {
        Self { active_path }
    }

    pub fn active_path(&self) -> Option<&LogicalPathId> {
        self.active_path.as_ref()
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AvailabilityRoutingProjection {
    pub next_state: AvailabilityRoutingState,
    pub effective_order: Vec<LogicalPathId>,
}

pub fn project_availability_routing(
    configured_paths: &[LogicalPathId],
    problem_paths: &[LogicalPathId],
    previous: &AvailabilityRoutingState,
    reserve_device_ids: &[String],
) -> Result<AvailabilityRoutingProjection, AvailabilityPriorityError> {
    let configured_set: HashSet<_> = configured_paths.iter().collect();
    let current_active = previous
        .active_path()
        .filter(|path| configured_set.contains(path));

    let effective_order = calculate_effective_path_order(
        configured_paths,
        problem_paths,
        current_active,
        reserve_device_ids,
    )?;

    let problem_set: HashSet<_> = problem_paths.iter().collect();
    let next_active = effective_order
        .iter()
        .find(|path| !problem_set.contains(path))
        .cloned();

    Ok(AvailabilityRoutingProjection {
        next_state: AvailabilityRoutingState::new(next_active),
        effective_order,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(device: &str) -> LogicalPathId {
        LogicalPathId::new(device, 0, 0).unwrap()
    }

    #[test]
    fn initial_projection_selects_first_usable_baseline_path() {
        let a = p("primary");
        let b = p("backup");
        let c = p("other");
        let result = project_availability_routing(
            &[a.clone(), b.clone(), c.clone()],
            &[],
            &AvailabilityRoutingState::default(),
            &[],
        )
        .unwrap();

        assert_eq!(result.effective_order, vec![a.clone(), b, c]);
        assert_eq!(result.next_state.active_path(), Some(&a));
    }

    #[test]
    fn failure_moves_active_to_next_usable_path() {
        let a = p("primary");
        let b = p("backup");
        let c = p("other");
        let result = project_availability_routing(
            &[a.clone(), b.clone(), c.clone()],
            std::slice::from_ref(&a),
            &AvailabilityRoutingState::new(Some(a.clone())),
            &[],
        )
        .unwrap();

        assert_eq!(result.effective_order, vec![b.clone(), c, a]);
        assert_eq!(result.next_state.active_path(), Some(&b));
    }

    #[test]
    fn recovery_keeps_ordinary_active_sticky() {
        let a = p("primary");
        let b = p("backup");
        let c = p("other");
        let result = project_availability_routing(
            &[a.clone(), b.clone(), c.clone()],
            &[],
            &AvailabilityRoutingState::new(Some(b.clone())),
            &[],
        )
        .unwrap();

        assert_eq!(result.effective_order, vec![b.clone(), a, c]);
        assert_eq!(result.next_state.active_path(), Some(&b));
    }

    #[test]
    fn recovery_preempts_reserve_active() {
        let a = p("primary");
        let b = p("backup");
        let c = p("other");
        let result = project_availability_routing(
            &[a.clone(), b.clone(), c.clone()],
            &[],
            &AvailabilityRoutingState::new(Some(b)),
            &["backup".to_string()],
        )
        .unwrap();

        assert_eq!(result.effective_order, vec![a.clone(), p("backup"), c]);
        assert_eq!(result.next_state.active_path(), Some(&a));
    }

    #[test]
    fn disappeared_active_is_replaced_without_error() {
        let a = p("primary");
        let b = p("backup");
        let result = project_availability_routing(
            &[a.clone(), b.clone()],
            &[],
            &AvailabilityRoutingState::new(Some(p("gone"))),
            &[],
        )
        .unwrap();

        assert_eq!(result.effective_order, vec![a.clone(), b]);
        assert_eq!(result.next_state.active_path(), Some(&a));
    }

    #[test]
    fn all_paths_problematic_clear_active_identity() {
        let a = p("primary");
        let b = p("backup");
        let result = project_availability_routing(
            &[a.clone(), b.clone()],
            &[a.clone(), b.clone()],
            &AvailabilityRoutingState::new(Some(a.clone())),
            &[],
        )
        .unwrap();

        assert_eq!(result.effective_order, vec![a, b]);
        assert_eq!(result.next_state.active_path(), None);
    }

    #[test]
    fn empty_membership_clears_stale_active_identity() {
        let result = project_availability_routing(
            &[],
            &[],
            &AvailabilityRoutingState::new(Some(p("gone"))),
            &[],
        )
        .unwrap();

        assert!(result.effective_order.is_empty());
        assert_eq!(result.next_state.active_path(), None);
    }
}
