"""Load .env file from the project root into os.environ."""
import os

def load_dotenv() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value

    # Resolve OUTPUT_PATH to an absolute path relative to project root
    output_path = os.environ.get("OUTPUT_PATH", "")
    if output_path and not os.path.isabs(output_path):
        os.environ["OUTPUT_PATH"] = os.path.normpath(
            os.path.join(project_root, output_path)
        )
