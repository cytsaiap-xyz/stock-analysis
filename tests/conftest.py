import sys
from pathlib import Path

# Make project root importable so `import agentcore` works from tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
