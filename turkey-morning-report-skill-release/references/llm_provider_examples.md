# LLM Provider Examples

This skill is model-agnostic. You must provide an OpenAI-compatible chat-completions endpoint. The model must be able to read Turkish text and produce Chinese output in the requested format.

## Generic Configuration Shape

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "base_url": null,
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.4,
    "max_tokens": 2500
  }
}
```

## OpenAI

```bash
export OPENAI_API_KEY="sk-..."
```

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "base_url": null,
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.4
  }
}
```

## Anthropic (via OpenAI-compatible proxy)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

```json
{
  "llm": {
    "provider": "anthropic",
    "model": "claude-sonnet-4",
    "base_url": "https://api.anthropic.com/v1",
    "api_key_env": "ANTHROPIC_API_KEY",
    "temperature": 0.4
  }
}
```

## MiniMax

```bash
export MINIMAX_API_KEY="..."
```

```json
{
  "llm": {
    "provider": "minimax",
    "model": "MiniMax-M3",
    "base_url": "https://api.minimaxi.com/v1",
    "api_key_env": "MINIMAX_API_KEY",
    "temperature": 0.4
  }
}
```

## GLM (Zhipu / ZAI)

```bash
export GLM_API_KEY="..."
```

```json
{
  "llm": {
    "provider": "zhipu",
    "model": "glm-5v-turbo",
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
    "api_key_env": "GLM_API_KEY",
    "temperature": 0.4
  }
}
```

## xAI / Grok

```bash
export XAI_API_KEY="..."
```

```json
{
  "llm": {
    "provider": "xai",
    "model": "grok-4.5",
    "base_url": "https://api.x.ai/v1",
    "api_key_env": "XAI_API_KEY",
    "temperature": 0.4
  }
}
```

## Local / OpenAI-compatible Server

```bash
export LOCAL_API_KEY="dummy"
```

```json
{
  "llm": {
    "provider": "local",
    "model": "local-model",
    "base_url": "http://localhost:8000/v1",
    "api_key_env": "LOCAL_API_KEY",
    "temperature": 0.4
  }
}
```

## Model Capability Requirement

The model must be able to:

1. Read Turkish financial text (e.g., BloombergHT article).
2. Extract or summarize key numbers, sectors, stocks, and macro drivers.
3. Write Chinese in the exact structure requested by the prompt.
4. Follow strict formatting rules (no separators, no tables, no bullets, no emojis).

If the model does not read Turkish, the briefing will be generic or hallucinated. Test with a short Turkish article before relying on the skill.
