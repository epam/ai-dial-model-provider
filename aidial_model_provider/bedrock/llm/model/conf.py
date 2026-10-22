from aidial_model_provider.bedrock.utils.env import get_env_int

CLAUDE_DEFAULT_MAX_TOKENS = get_env_int("CLAUDE_DEFAULT_MAX_TOKENS", 1536)
