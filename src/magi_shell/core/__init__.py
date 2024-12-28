"""
MAGI Shell core components.
"""

print("Loading core/__init__.py")

try:
    from .panel import MAGIPanel
    print("Successfully imported MAGIPanel")
except Exception as e:
    print(f"Error importing MAGIPanel: {e}")
    raise

try:
    from .application import MAGIApplication, main
    print("Successfully imported MAGIApplication and main")
except Exception as e:
    print(f"Error importing MAGIApplication: {e}")
    raise

__all__ = [
    'MAGIPanel',
    'MAGIApplication',
    'main'
]
