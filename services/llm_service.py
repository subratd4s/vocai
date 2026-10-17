"""Future LLM adapter: isolate provider-specific calls and environment-based configuration.

Agents will depend on this boundary so replacing OpenAI does not require UI or
workflow changes. No client initialization or API requests occur in Phase 1.
"""
