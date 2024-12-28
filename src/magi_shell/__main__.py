"""
MAGI Shell main entry point.
"""

print("Loading main...")

try:
    from magi_shell.core import main
    print("Successfully imported main from core")
except Exception as e:
    print(f"Error importing main: {e}")
    raise

if __name__ == '__main__':
    print("Starting main...")
    main()
