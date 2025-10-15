r"""
Process Runner with Progress Tracking
Executes chromatography processes with real-time progress monitoring
"""

import time
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

# Handle imports for both direct execution and module import
if __name__ == "__main__":
    # Add parent directory to path for direct execution
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from system_configuration.system_config import System
    from system_configuration.process import ChromatographyProcess, ProcessLibrary
else:
    # Relative imports when used as a module
    from .system_config import System
    from .process import ChromatographyProcess, ProcessLibrary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """Status of individual process steps"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepProgress:
    """Progress tracking for a single step"""
    step_number: int
    step_name: str
    status: StepStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_duration_sec: float = 0
    actual_duration_sec: Optional[float] = None
    error_message: Optional[str] = None

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds"""
        if self.start_time:
            end = self.end_time or datetime.now()
            return (end - self.start_time).total_seconds()
        return 0

    def get_progress_percent(self) -> float:
        """Get progress percentage for this step"""
        if self.status == StepStatus.COMPLETED:
            return 100.0
        elif self.status == StepStatus.IN_PROGRESS:
            if self.estimated_duration_sec > 0:
                elapsed = self.get_elapsed_time()
                return min(100.0, (elapsed / self.estimated_duration_sec) * 100)
        return 0.0


@dataclass
class ProcessProgress:
    """Progress tracking for entire process"""
    process_name: str
    pump_name: str
    total_steps: int
    current_step: int = 0
    steps: List[StepProgress] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_total_time_sec: float = 0

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

    def get_overall_progress_percent(self) -> float:
        """Calculate overall progress percentage"""
        if self.total_steps == 0:
            return 0.0

        completed_steps = sum(1 for step in self.steps if step.status == StepStatus.COMPLETED)
        current_step_progress = 0.0

        if self.current_step < len(self.steps):
            current_step_progress = self.steps[self.current_step].get_progress_percent() / 100

        return ((completed_steps + current_step_progress) / self.total_steps) * 100

    def get_elapsed_time(self) -> float:
        """Get total elapsed time in seconds"""
        if self.start_time:
            end = self.end_time or datetime.now()
            return (end - self.start_time).total_seconds()
        return 0

    def get_estimated_remaining_time(self) -> float:
        """Estimate remaining time in seconds"""
        if self.estimated_total_time_sec > 0:
            elapsed = self.get_elapsed_time()
            return max(0, self.estimated_total_time_sec - elapsed)
        return 0


class ProcessRunner:
    """
    Executes chromatography processes with progress tracking

    Features:
    - Real-time progress monitoring
    - Step-by-step status tracking
    - Time estimation and remaining time calculation
    - Visual progress indicators
    - Error handling and recovery
    """

    def __init__(self, system: System):
        self.system = system
        self.active_processes: Dict[str, ProcessProgress] = {}

    def run_process(
        self,
        process: ChromatographyProcess,
        pump_names: List[str],
        show_progress: bool = True,
        progress_update_interval: float = 1.0
    ) -> Dict[str, bool]:
        """
        Run a process on specified pumps with progress tracking

        Args:
            process: ChromatographyProcess to execute
            pump_names: List of pump names to run process on
            show_progress: Display progress updates to console
            progress_update_interval: How often to update progress (seconds)

        Returns:
            Dict mapping pump_name to success status
        """
        if not self.system.is_initialized:
            logger.error("System not initialized")
            return {pump: False for pump in pump_names}

        # Initialize progress tracking for each pump
        results = {}
        for pump_name in pump_names:
            logger.info(f"\n{'='*70}")
            logger.info(f"Starting process '{process.config.name}' on {pump_name}")
            logger.info(f"{'='*70}\n")

            progress = self._initialize_progress(process, pump_name)
            self.active_processes[pump_name] = progress

            if show_progress:
                self._display_process_overview(progress, process)

            # Execute the process
            success = self._execute_process_with_tracking(
                process,
                pump_name,
                progress,
                show_progress,
                progress_update_interval
            )

            results[pump_name] = success

            # Display final summary
            if show_progress:
                self._display_final_summary(progress)

        return results

    def _initialize_progress(
        self,
        process: ChromatographyProcess,
        pump_name: str
    ) -> ProcessProgress:
        """Initialize progress tracking for a process"""
        total_steps = len(process.config.steps)

        # Create step progress trackers
        step_progresses = []
        estimated_total_time = 0

        for i, step in enumerate(process.config.steps):
            estimated_duration = (step.volume_ml / step.flow_rate_ml_min) * 60
            estimated_duration += step.delay_after_sec
            estimated_total_time += estimated_duration

            step_progress = StepProgress(
                step_number=i + 1,
                step_name=step.name,
                status=StepStatus.PENDING,
                estimated_duration_sec=estimated_duration
            )
            step_progresses.append(step_progress)

        progress = ProcessProgress(
            process_name=process.config.name,
            pump_name=pump_name,
            total_steps=total_steps,
            steps=step_progresses,
            estimated_total_time_sec=estimated_total_time
        )

        return progress

    def _execute_process_with_tracking(
        self,
        process: ChromatographyProcess,
        pump_name: str,
        progress: ProcessProgress,
        show_progress: bool,
        update_interval: float
    ) -> bool:
        """Execute process with real-time progress tracking"""
        pump = self.system.get_pump(pump_name)
        if not pump or not pump.is_connected():
            logger.error(f"Pump {pump_name} not available")
            return False

        progress.start_time = datetime.now()

        try:
            # Execute each step
            for i, step in enumerate(process.config.steps):
                progress.current_step = i
                step_progress = progress.steps[i]

                # Update step status to in progress
                step_progress.status = StepStatus.IN_PROGRESS
                step_progress.start_time = datetime.now()

                if show_progress:
                    self._display_step_start(step_progress, progress)

                # Execute the step
                success = self.system.process_step(
                    pump_name=pump_name,
                    inlet=step.inlet,
                    outlet=step.outlet,
                    volume_ml=step.volume_ml,
                    flow_rate_ml_min=step.flow_rate_ml_min,
                    prime=step.prime,
                    wait=False  # Don't block - we'll monitor progress
                )

                if not success:
                    step_progress.status = StepStatus.FAILED
                    step_progress.error_message = "Failed to start step"
                    logger.error(f"Failed to start step: {step.name}")
                    return False

                # Monitor step progress
                self._monitor_step_progress(
                    pump,
                    step_progress,
                    progress,
                    show_progress,
                    update_interval
                )

                # Mark step as completed
                step_progress.status = StepStatus.COMPLETED
                step_progress.end_time = datetime.now()
                step_progress.actual_duration_sec = step_progress.get_elapsed_time()

                if show_progress:
                    self._display_step_complete(step_progress)

                # Handle delay after step
                if step.delay_after_sec > 0:
                    logger.info(f"Waiting {step.delay_after_sec}s after {step.name}...")
                    time.sleep(step.delay_after_sec)

            progress.end_time = datetime.now()
            logger.info(f"\n{pump_name} - Process completed successfully!")
            return True

        except Exception as e:
            logger.error(f"Error executing process on {pump_name}: {e}")
            if progress.current_step < len(progress.steps):
                progress.steps[progress.current_step].status = StepStatus.FAILED
                progress.steps[progress.current_step].error_message = str(e)
            return False

    def _monitor_step_progress(
        self,
        pump,
        step_progress: StepProgress,
        process_progress: ProcessProgress,
        show_progress: bool,
        update_interval: float
    ):
        """Monitor step execution progress"""
        last_update_time = time.time()

        while not pump.is_ready():
            current_time = time.time()

            # Update progress display
            if show_progress and (current_time - last_update_time) >= update_interval:
                self._display_progress_update(step_progress, process_progress)
                last_update_time = current_time

            time.sleep(0.1)  # Small sleep to avoid busy waiting

    def _display_process_overview(self, progress: ProcessProgress, process: ChromatographyProcess):
        """Display process overview before starting"""
        print(f"\n{'='*70}")
        print(f"Process: {progress.process_name}")
        print(f"Pump: {progress.pump_name}")
        print(f"Total Steps: {progress.total_steps}")
        print(f"Estimated Time: {self._format_time(progress.estimated_total_time_sec)}")
        print(f"{'='*70}\n")

        print("Steps:")
        for i, step in enumerate(process.config.steps):
            step_time = (step.volume_ml / step.flow_rate_ml_min) * 60
            print(f"  {i+1}. {step.name}")
            print(f"     Volume: {step.volume_ml}mL @ {step.flow_rate_ml_min}mL/min")
            print(f"     Time: ~{self._format_time(step_time)}")
        print()

    def _display_step_start(self, step: StepProgress, process: ProcessProgress):
        """Display step start message"""
        print(f"\n{'-'*70}")
        print(f"Step {step.step_number}/{process.total_steps}: {step.step_name}")
        print(f"Status: {step.status.value.upper()}")
        print(f"Estimated Duration: {self._format_time(step.estimated_duration_sec)}")
        print(f"{'-'*70}")

    def _display_progress_update(self, step: StepProgress, process: ProcessProgress):
        """Display real-time progress update"""
        step_percent = step.get_progress_percent()
        overall_percent = process.get_overall_progress_percent()
        elapsed = step.get_elapsed_time()

        # Create progress bar
        bar_length = 40
        filled_length = int(bar_length * step_percent / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)

        print(f"\r  [{bar}] {step_percent:.1f}% | "
              f"Elapsed: {self._format_time(elapsed)} | "
              f"Overall: {overall_percent:.1f}%", end='', flush=True)

    def _display_step_complete(self, step: StepProgress):
        """Display step completion message"""
        print(f"\n✓ Step {step.step_number} completed in {self._format_time(step.actual_duration_sec)}")

    def _display_final_summary(self, progress: ProcessProgress):
        """Display final process summary"""
        total_time = progress.get_elapsed_time()

        print(f"\n{'='*70}")
        print(f"PROCESS COMPLETE: {progress.process_name}")
        print(f"Pump: {progress.pump_name}")
        print(f"{'='*70}")
        print(f"Total Time: {self._format_time(total_time)}")
        print(f"Estimated Time: {self._format_time(progress.estimated_total_time_sec)}")

        time_diff = total_time - progress.estimated_total_time_sec
        if abs(time_diff) > 1:
            diff_str = f"{'faster' if time_diff < 0 else 'slower'}"
            print(f"Difference: {abs(time_diff):.1f}s {diff_str} than estimated")

        print(f"\nStep Summary:")
        for step in progress.steps:
            status_icon = "✓" if step.status == StepStatus.COMPLETED else "✗"
            print(f"  {status_icon} {step.step_name}: {self._format_time(step.actual_duration_sec or 0)}")

        print(f"{'='*70}\n")

    def get_process_status(self, pump_name: str) -> Optional[ProcessProgress]:
        """Get current process status for a pump"""
        return self.active_processes.get(pump_name)

    def get_all_statuses(self) -> Dict[str, ProcessProgress]:
        """Get status of all active processes"""
        return self.active_processes.copy()

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format time in seconds to readable string"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def run_process_by_name(
    system: System,
    process_name: str,
    pump_names: List[str],
    show_progress: bool = True
) -> Dict[str, bool]:
    """
    Load and run a pre-defined process by name

    Args:
        system: System instance
        process_name: Name of process from ProcessLibrary
        pump_names: List of pumps to run on
        show_progress: Show progress tracking

    Returns:
        Dict mapping pump names to success status
    """
    process = ProcessLibrary.get_process(process_name)
    if not process:
        logger.error(f"Process '{process_name}' not found")
        return {pump: False for pump in pump_names}

    runner = ProcessRunner(system)
    return runner.run_process(process, pump_names, show_progress=show_progress)


def list_available_processes() -> List[str]:
    """Get list of available processes"""
    return ProcessLibrary.list_available_processes()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("Process Runner - Example Usage\n")

    # Initialize system
    print("Initializing system...")
    system = System()

    # Connect and initialize (in real use, uncomment these)
    # if not system.connect_all():
    #     print("Failed to connect to pumps")
    #     exit(1)
    #
    # if not system.initialize_all():
    #     print("Failed to initialize pumps")
    #     exit(1)

    # List available processes
    print("\nAvailable processes:")
    for name in list_available_processes():
        print(f"  - {name}")

    # Load a process
    process_name = "protein_a_purification"
    process = ProcessLibrary.get_process(process_name)

    if process:
        print(f"\nProcess: {process.config.name}")
        print(f"Description: {process.config.description}")
        print(f"Total steps: {len(process.config.steps)}")
        print(f"Estimated time: {process.get_total_time_estimate():.1f} minutes")

    # Run process with progress tracking (commented out for demo)
    # runner = ProcessRunner(system)
    # results = runner.run_process(process, ["pump1"], show_progress=True)
    #
    # print("\nResults:")
    # for pump_name, success in results.items():
    #     status = "SUCCESS" if success else "FAILED"
    #     print(f"  {pump_name}: {status}")

    print("\nDemo complete!")