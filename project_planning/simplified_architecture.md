# Simplified Architecture (No Columns)

## Core Components

### 1. **PumpUnit** (Pump + Process Slot)
```
PumpUnit:
- pump: Pump instance
- assigned_process: Process (or None)
- status: idle/running/completed/error
- unit_id: "pump1", "pump2", "pump3"
```

### 2. **Process** (Single Sample Purification)
```
Process:
- sample_id: "Sample_A_001"
- process_definition: ProcessDefinition (the recipe)
- status: pending/running/completed/failed
- assigned_pump_unit: PumpUnit reference
- start_time, end_time
```

### 3. **ProcessDefinition** (Recipe)
```
ProcessDefinition:
- name: "Protein A Purification"
- steps: [ProcessStep, ProcessStep, ...]
- estimated_time_min
```

### 4. **ProcessSet** (Batch of Samples)
```
ProcessSet:
- name: "Batch_001" 
- processes: [Process, Process, ...]
- status: pending/running/completed
- stats: {total: 8, completed: 5, running: 2, failed: 1}
```

### 5. **System** (Orchestrator)
```
System:
- pump_units: [PumpUnit1, PumpUnit2, PumpUnit3]
- active_process_set: ProcessSet
- process_queue: [ProcessSet, ProcessSet, ...]
```

## Simplified Workflow

### Example: 8 Samples on 3 PumpUnits
```
1. Create ProcessSet with 8 processes
2. System assigns first 3 processes to available PumpUnits
3. When PumpUnit1 completes → assign next process (process 4)
4. When PumpUnit2 completes → assign next process (process 5)
5. Continue until all 8 processes complete
```

## Key Classes

### PumpUnit
```python
class PumpUnit:
    def __init__(self, pump: Pump, unit_id: str):
        self.pump = pump
        self.unit_id = unit_id
        self.assigned_process = None
        self.status = "idle"
    
    def assign_process(self, process: Process):
        self.assigned_process = process
        process.assigned_pump_unit = self
    
    def start_process(self):
        # Execute all steps in process.process_definition
        pass
    
    def is_available(self) -> bool:
        return self.status == "idle" and self.assigned_process is None
```

### ProcessSet
```python
class ProcessSet:
    def __init__(self, name: str):
        self.name = name
        self.processes = []
        self.status = "pending"
    
    def add_process(self, process: Process):
        self.processes.append(process)
    
    def get_next_pending_process(self) -> Process:
        # Return next process that needs to run
        pass
    
    def get_stats(self) -> dict:
        # Return completion statistics
        pass
```

### System
```python
class System:
    def __init__(self):
        self.pump_units = [
            PumpUnit(Pump(config1), "pump1"),
            PumpUnit(Pump(config2), "pump2"), 
            PumpUnit(Pump(config3), "pump3")
        ]
        self.active_process_set = None
    
    def start_process_set(self, process_set: ProcessSet):
        self.active_process_set = process_set
        self._assign_next_processes()
    
    def _assign_next_processes(self):
        # Assign pending processes to available pump units
        pass
    
    def handle_pump_completion(self, pump_unit: PumpUnit):
        # When a pump finishes, assign next process
        pass
```

This is much cleaner and focuses on the essential functionality without column complexity!