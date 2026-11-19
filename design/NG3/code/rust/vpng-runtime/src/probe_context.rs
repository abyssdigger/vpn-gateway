use std::net::Ipv4Addr;

use crate::availability_confirmation::AvailabilityOutcome;
use crate::logical_path::LogicalPathId;

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct ProbePolicyOwner {
    profile_id: String,
    path_id: LogicalPathId,
}

impl ProbePolicyOwner {
    pub fn new(
        profile_id: impl Into<String>,
        path_id: LogicalPathId,
    ) -> Result<Self, ProbeContextError> {
        let profile_id = profile_id.into();
        if profile_id.is_empty() {
            return Err(ProbeContextError::EmptyProfileId);
        }
        Ok(Self {
            profile_id,
            path_id,
        })
    }

    pub fn profile_id(&self) -> &str {
        &self.profile_id
    }

    pub fn path_id(&self) -> &LogicalPathId {
        &self.path_id
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct InterfaceIdentity {
    ifname: String,
    ifindex: u32,
}

impl InterfaceIdentity {
    pub fn new(ifname: impl Into<String>, ifindex: u32) -> Result<Self, ProbeContextError> {
        let ifname = ifname.into();
        if ifname.is_empty() {
            return Err(ProbeContextError::EmptyInterfaceName);
        }
        if ifindex == 0 {
            return Err(ProbeContextError::ZeroInterfaceIndex);
        }
        Ok(Self { ifname, ifindex })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AvailabilityProbeMechanism {
    Icmp,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AvailabilityProbeIntent {
    owner: ProbePolicyOwner,
    mechanism: AvailabilityProbeMechanism,
    target: Ipv4Addr,
}

impl AvailabilityProbeIntent {
    pub fn icmp(owner: ProbePolicyOwner, target: Ipv4Addr) -> Self {
        Self {
            owner,
            mechanism: AvailabilityProbeMechanism::Icmp,
            target,
        }
    }

    pub fn owner(&self) -> &ProbePolicyOwner {
        &self.owner
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProbeObservationContext {
    intent: AvailabilityProbeIntent,
    endpoint: InterfaceIdentity,
    generation: u64,
}

impl ProbeObservationContext {
    pub fn new(
        intent: AvailabilityProbeIntent,
        endpoint: InterfaceIdentity,
        generation: u64,
    ) -> Result<Self, ProbeContextError> {
        if generation == 0 {
            return Err(ProbeContextError::ZeroGeneration);
        }
        Ok(Self {
            intent,
            endpoint,
            generation,
        })
    }

    pub fn owner(&self) -> &ProbePolicyOwner {
        self.intent.owner()
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProbeEvidence {
    pub context: ProbeObservationContext,
    pub outcome: AvailabilityOutcome,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProbeContextError {
    EmptyProfileId,
    EmptyInterfaceName,
    ZeroInterfaceIndex,
    ZeroGeneration,
}
