# src/magi_shell/widgets/system.py
"""
System monitoring widgets for MAGI Shell.

Provides components for displaying system resource usage including
CPU, RAM, GPU, and VRAM utilization.
"""

from gi.repository import Gtk, GLib
import psutil
from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo
from pynvml import nvmlDeviceGetUtilizationRates
from ..utils.cache import Cache

class SystemMonitor(Gtk.Box):
    """
    Widget displaying system resource utilization.
    
    Shows real-time statistics for CPU, RAM, and NVIDIA GPU usage if available.
    Updates periodically to reflect current system state.
    
    Attributes:
        _update_manager: UpdateManager instance for scheduling updates
        _prophecy_label: Label widget displaying the statistics
        _nvidia: NVIDIA GPU handle if available
        _cpu_cache: Cache instance for CPU statistics
    """
    
    def __init__(self, update_manager):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        
        self._update_manager = update_manager
        self._prophecy_label = Gtk.Label()
        self._prophecy_label.add_css_class('monitor-label')
        self.append(self._prophecy_label)
        
        self._setup_monitoring()
    
    def _setup_monitoring(self):
        """Initialize system monitoring and NVIDIA GPU detection."""
        self._nvidia = None
        try:
            nvmlInit()
            self._nvidia = nvmlDeviceGetHandleByIndex(0)
        except Exception:
            print("NVIDIA GPU not available")
        
        self._cpu_cache = Cache(timeout=1000)
        self._divine_resource_usage()
        GLib.timeout_add(3000, self._divine_resource_usage)
    
    def _divine_resource_usage(self):
        """Update system resource usage statistics."""
        try:
            cpu_load = psutil.cpu_percent(interval=None)
            memory_state = psutil.virtual_memory()
            ram_usage = memory_state.percent
            
            if self._nvidia:
                try:
                    gpu_prophecy = nvmlDeviceGetUtilizationRates(self._nvidia)
                    gpu_memory = nvmlDeviceGetMemoryInfo(self._nvidia)
                    gpu_load = gpu_prophecy.gpu
                    vram_usage = (gpu_memory.used / gpu_memory.total) * 100
                except:
                    gpu_load = vram_usage = 0
                
                self._prophecy_label.set_label(
                    f"CPU: {cpu_load:>5.1f}% | RAM: {ram_usage:>5.1f}% | "
                    f"GPU: {gpu_load:>5.1f}% | VRAM: {vram_usage:>5.1f}%"
                )
            else:
                self._prophecy_label.set_label(
                    f"CPU: {cpu_load:>5.1f}% | RAM: {ram_usage:>5.1f}%"
                )
            
        except Exception as e:
            print(f"Resource monitoring error: {e}")
        
        return True
