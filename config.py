import os
from dotenv import load_dotenv

load_dotenv()

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
K3S_NAMESPACE = os.getenv("K3S_NAMESPACE", "all")

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])

NVIDIA_API_KEY = os.environ["NVIDIA_API_KEY"]
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL_DIAGNOSIS = os.getenv("NVIDIA_MODEL_DIAGNOSIS", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
NVIDIA_MODEL_TOOLCALL = os.getenv("NVIDIA_MODEL_TOOLCALL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

POSTGRES_DSN = os.environ["POSTGRES_DSN"]

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 60))
BREACH_THRESHOLD_COUNT = int(os.getenv("BREACH_THRESHOLD_COUNT", 3))

CPU_PERCENT_THRESHOLD = float(os.getenv("CPU_PERCENT_THRESHOLD", 85))
MEM_PERCENT_THRESHOLD = float(os.getenv("MEM_PERCENT_THRESHOLD", 85))
DISK_PERCENT_THRESHOLD = float(os.getenv("DISK_PERCENT_THRESHOLD", 90))
