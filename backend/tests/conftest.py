import os
import sys
import tempfile

_tmp = tempfile.mkdtemp(prefix="rftg-test-")
os.environ.setdefault("ARTIFACT_DIR", os.path.join(_tmp, "artifacts"))
os.environ.setdefault("CACHE_DIR", os.path.join(_tmp, "cache"))
os.environ["TASK_MODE"] = "inline"
os.environ["GRAPH_STORE"] = "file"
os.environ.pop("RABBITMQ_URL", None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
