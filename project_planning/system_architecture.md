# Purification System Architecture

## Overview
Multi-pump purification system with OPC UA interface for remote control and monitoring.

## Class Structure

### 1. Device Layer
```
Pump (Base Class)
├── CavroXLP6000
├── [Future pump models]

FractionCollector (Base Class)
├── [Specific collector models]
```

### 2. System Layer
```
PurificationSystem
├── pumps: List[Pump]
├── fraction_collector: FractionCollector
├── run_method()
├── coordinate_devices()
└── get_system_status()
```

### 3. Communication Layer (OPC UA)
```
OPCUAServer
├── Exposes PurificationSystem methods
├── Real-time status monitoring
├── Remote control interface
└── Data logging/historian
```

## Architecture Flow

```
[HMI/Client Apps] <--OPC UA--> [OPC UA Server] <--> [PurificationSystem]
                                                           |
                                    [Pump1] [Pump2] [Pump3] [FractionCollector]
                                       |       |       |            |
                                    [Serial] [Serial] [Serial]  [Serial/USB]
```

## Key Design Decisions

### Why OPC UA?
- **Standard Protocol**: Works with any OPC UA client (LabVIEW, WinCC, custom apps)
- **Scalability**: Easy to add new devices without changing client code
- **Security**: Built-in authentication and encryption
- **Real-time Updates**: Subscription model for status changes

### Class Responsibilities

**Pump Class**
- Serial communication
- Command translation
- Status reporting
- Error handling

**PurificationSystem Class**
- Device coordination
- Method execution (recipes)
- Flow path control
- Safety interlocks
- Process state management

**OPC UA Server**
- External interface
- Data model definition
- Event notifications
- Historical data

## Implementation Phases

### Phase 1: Single Pump Control
- Pump driver class
- Basic serial communication
- Manual control methods

### Phase 2: System Integration
- PurificationSystem class
- Multi-pump coordination
- Fraction collector integration

### Phase 3: OPC UA Interface
- OPC UA server setup
- Node structure definition
- Client subscription handling

### Phase 4: Advanced Features
- Method recipes
- Automated runs
- Data logging
- Alarms/events

## Example OPC UA Node Structure
```
Root
├── System
│   ├── Status (Running/Idle/Error)
│   ├── CurrentMethod
│   └── Commands
│       ├── StartMethod
│       └── StopMethod
├── Pumps
│   ├── Pump1
│   │   ├── Status
│   │   ├── Position
│   │   ├── FlowRate
│   │   └── Commands
│   │       ├── Aspirate
│   │       └── Dispense
│   └── Pump2...
└── FractionCollector
    ├── CurrentPosition
    ├── CollectionMode
    └── Commands
```

## Benefits of This Architecture

1. **Modularity**: Easy to add/remove devices
2. **Flexibility**: Multiple control interfaces possible
3. **Scalability**: From 1 to N pumps without major changes
4. **Industry Standard**: OPC UA widely supported
5. **Maintainability**: Clear separation of concerns