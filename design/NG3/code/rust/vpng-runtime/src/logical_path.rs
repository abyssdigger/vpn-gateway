#[derive(Clone, Debug, Eq, Hash, PartialEq)]
pub struct LogicalPathId {
    device_id: String,
    selector_index: u32,
    slot_index: u32,
}

impl LogicalPathId {
    pub fn new(
        device_id: impl Into<String>,
        selector_index: u32,
        slot_index: u32,
    ) -> Result<Self, LogicalPathError> {
        let device_id = device_id.into();
        if device_id.is_empty() {
            return Err(LogicalPathError::EmptyDeviceId);
        }
        Ok(Self {
            device_id,
            selector_index,
            slot_index,
        })
    }

    pub fn device_id(&self) -> &str {
        &self.device_id
    }

    pub fn selector_index(&self) -> u32 {
        self.selector_index
    }

    pub fn slot_index(&self) -> u32 {
        self.slot_index
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LogicalPathError {
    EmptyDeviceId,
}
