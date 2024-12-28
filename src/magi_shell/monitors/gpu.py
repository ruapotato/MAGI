# src/magi_shell/monitors/gpu.py
"""
GPU monitoring utilities for MAGI Shell.
"""

import pynvml

class GPUMonitor:
    """Monitor for NVIDIA GPU status"""
    def __init__(self):
        self.initialized = False
        try:
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.initialized = True
        except:
            pass
    
    def get_status(self):
        """Get current GPU status"""
        if not self.initialized:
            return "Power Meter: Unplugged"
        
        try:
            memory = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            watts_used = memory.used / 1024**3
            total_capacity = memory.total / 1024**3
            
            temperature = pynvml.nvmlDeviceGetTemperature(
                self.handle, 
                pynvml.NVML_TEMPERATURE_GPU
            )
            
            return f"Power Draw: {watts_used:.1f}GB/{total_capacity:.1f}GB | Temp: {temperature}°C"
        except:
            return "Power Meter: Error reading values"
