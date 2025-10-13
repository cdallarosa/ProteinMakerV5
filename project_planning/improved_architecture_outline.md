# Improved System Architecture Outline

## Core Concept
Scale from 1 process to multiple processes running in parallel, handling variable sample numbers efficiently.

## Key Components

### 1. **PumpUnit** 
```
Each PumpUnit = Pump + Column + Process (1:1:1 relationship)

PumpUnit:
- pump: Pump instance
- column: Column instance  
- assigned_process: Process instance (or None)
- status: idle/running/error
- sample_id: unique identifier for current sample
```

### 2. **Process** (Single Purification)
```
Process:
- sample_id: unique identifier
- process_definition: ProcessDefinition (the recipe)
- pump_unit_id: which PumpUnit will run this
- status: pending/running/completed/failed
- start_time, end_time
- results: yield, purity, etc.
```

### 3. **ProcessDefinition** (Recipe/Template)
```
ProcessDefinition:
- name: "Protein A Purification"
- steps: [ProcessStep, ProcessStep, ...]
- expected_time_min
- buffer_requirements: {inlet_1: "buffer_A", inlet_2: "sample", ...}

ProcessStep:
- name, inlet, outlet, volume_ml, flow_rate_ml_min, prime, delay
```

### 4. **ProcessSet** (Batch of Processes)
```
ProcessSet:
- name: "Batch_2024_001"
- processes: [Process, Process, Process, ...] 
- start_time, estimated_completion_time
- status: pending/running/completed
- completion_stats: {completed: 8, failed: 0, running: 4}
```

### 5. **System** (Orchestrator)
```
System:
- pump_units: [PumpUnit1, PumpUnit2, PumpUnit3, ...]
- process_queue: [ProcessSet, ProcessSet, ...]
- current_process_set: ProcessSet
- resource_manager: handles inlet assignments, buffer management
```

## Workflow Examples

### Example 1: 8 Samples (Full Utilization)
```
ProcessSet_A:
- 8 processes total
- Uses all available pump units
- Round 1: Run 3 processes on PumpUnit1, 2, 3
- Round 2: Run 3 more processes on PumpUnit1, 2, 3  
- Round 3: Run final 2 processes on PumpUnit1, 2
```

### Example 2: 4 Samples (Partial Utilization)  
```
ProcessSet_B:
- 4 processes total
- Can use any combination of pump units
- Option A: Use PumpUnit1, 2, 3 + one more round
- Option B: Use all pump units once with some idle
```

### Example 3: Mixed Sample Types
```
ProcessSet_C:
- 6 Protein A samples (use ProcessDefinition_A)
- 3 Buffer exchange samples (use ProcessDefinition_B)
- System assigns optimal pump units based on availability
```

## Resource Management

### Buffer/Inlet Management
```
System tracks:
- Which inlets have which buffers
- Sample positions (inlet_1: Sample_A, inlet_2: Sample_B, etc.)
- Buffer volumes and when to refill
- Cleaning/changeover requirements between sample types
```

### Smart Scheduling
```
System optimizes:
- Which pump units to use for which processes
- Minimize idle time
- Balance wear across pump units
- Handle failures gracefully (reassign to available pump unit)
```

## Class Hierarchy

```
System
├── PumpUnits: List[PumpUnit]
│   └── PumpUnit
│       ├── pump: Pump
│       ├── column: Column
│       ├── assigned_process: Process
│       └── status, sample_id
├── ProcessQueue: List[ProcessSet]
│   └── ProcessSet
│       ├── processes: List[Process]
│       ├── status, timing
│       └── completion_stats
└── ResourceManager
    ├── inlet_assignments: Dict
    ├── buffer_levels: Dict
    └── scheduling_logic
```

## Key Methods

### System Level
```python
# High-level operations
system.submit_process_set(process_set)
system.start_next_batch()
system.get_system_status()
system.handle_pump_failure(pump_unit_id)

# Resource management  
system.assign_inlets(sample_mapping)
system.check_buffer_levels()
system.optimize_pump_assignment()
```

### ProcessSet Level
```python
# Batch management
process_set.add_process(process)
process_set.start_execution(available_pump_units)
process_set.get_completion_status()
process_set.reschedule_failed_processes()
```

### PumpUnit Level
```python
# Individual pump operations
pump_unit.assign_process(process)
pump_unit.start_process()
pump_unit.get_progress()
pump_unit.handle_error()
```

## Benefits of This Architecture

1. **Clear Scalability**: Easy to go from 1 to N processes
2. **Flexible Resource Usage**: Handle variable sample numbers efficiently  
3. **Fault Tolerance**: Reassign processes if pump units fail
4. **Resource Optimization**: Smart scheduling and inlet management
5. **Real-World Modeling**: Matches actual lab workflows
6. **Separation of Concerns**: 
   - ProcessDefinition = Recipe (reusable)
   - Process = Single run instance  
   - ProcessSet = Batch management
   - PumpUnit = Hardware abstraction
   - System = Orchestration

## Implementation Priority

1. **Phase 1**: PumpUnit, Process, ProcessDefinition classes
2. **Phase 2**: ProcessSet and basic batch management
3. **Phase 3**: Smart scheduling and resource optimization
4. **Phase 4**: Advanced features (failure handling, reporting)

This architecture clearly separates concerns and scales naturally from single processes to complex batch operations while handling the real-world constraints you described.