# LLM Options for Sentence Generation (German + Polish)

**Use case**: ~100-200 requests/day, each generating 1-2 German sentences using a specific vocabulary word + Polish translation. ~300 tokens per request, ~60K tokens/day.

---

## Free API Options

### Gemini 2.5 Flash-Lite (Google) ⭐

- **Free tier**: 1,000 requests/day, 15 RPM, 250K TPM. No credit card
- **Access**: API key from [aistudio.google.com](https://aistudio.google.com), `google-genai` Python package
- **German/Polish**: Strong multilingual (100+ languages). German excellent, Polish good
- **Latency**: <1s for short generations
- **Gotchas**: Free tier data may be used by Google. Limits could change

### Gemini 2.5 Flash (Google)

- **Free tier**: 250 requests/day, 10 RPM — tight for 200/day
- **Quality**: Better than Flash-Lite
- **Could combine with Flash-Lite as fallback**

### Groq ⭐

- **Models**: `llama-3.3-70b-versatile`, `llama-4-scout-17b-16e-instruct`
- **Free tier**: ~6,000 requests/day on larger models, 14,400 on 8B. No credit card, no time limit
- **Access**: [console.groq.com](https://console.groq.com), OpenAI-compatible endpoint
- **German/Polish**: Llama 3.3 70B solid German, decent Polish
- **Latency**: Extremely fast (sub-second, 500-750 tok/s)
- **Gotchas**: Model selection may change. Llama 4 Scout has EU license restrictions

### Mistral Free Tier

- **Models**: Any, including `mistral-large-3` and `ministral-8b`
- **Free tier**: 1 billion tokens/month (enormous for this use case)
- **Access**: [console.mistral.ai](https://console.mistral.ai), requires phone verification
- **German/Polish**: "Strongest for European languages" — excellent German, good Polish
- **Gotchas**: Rate limits not clearly documented. Phone verification required

### OpenRouter Free Models

- **Models**: Various `:free` models (e.g., `meta-llama/llama-3.3-70b-instruct:free`)
- **Free tier**: ~20 RPM, ~200 requests/day
- **Access**: [openrouter.ai](https://openrouter.ai), OpenAI-compatible
- **Gotchas**: 200 RPD is at the limit. Variable latency. Good as backup

### Cloudflare Workers AI

- **Free tier**: 100K requests/day — very generous
- **Models**: Llama 3.3 70B, Mistral 7B, others
- **Gotchas**: Non-standard API (not OpenAI-compatible), more setup friction

### Hugging Face Serverless Inference

- **Free tier**: ~1,000 requests/day
- **Gotchas**: Cold starts can exceed 30s — dealbreaker for interactive CLI use

---

## Cheap Paid Options

At 200 requests/day (~1.8M tokens/month), everything below costs less than **$1/month**.

| Provider | Model | Input $/M | Output $/M | ~Monthly cost |
|---|---|---|---|---|
| DeepSeek | V3.2 | $0.14 | $0.28 | ~$0.15 |
| Google | Gemini Flash-Lite | $0.075 | $0.30 | ~$0.20 |
| OpenAI | GPT-4o-mini | $0.15 | $0.60 | ~$0.30 |
| Google | Gemini Flash | $0.15 | $0.60 | ~$0.30 |
| Mistral | ministral-8b | $0.10 | — | ~$0.20 |
| Anthropic | Claude 3.5 Haiku | $0.25 | $1.25 | ~$0.50 |

**DeepSeek** is cheapest but can be slow/unreliable (503 errors). Also gives 5M free tokens on signup.
**GPT-4o-mini** is the most reliable, excellent German/Polish, well-documented API.

---

## Local Options (Ollama)

### Qwen 3 8B ⭐

- `ollama pull qwen3:8b` (~5GB)
- **Hardware**: 8GB+ RAM, runs well on Apple Silicon
- **German/Polish**: Strongest multilingual in the small model range (119 languages)
- **Latency**: 10-30 tok/s on M1/M2, 1-3s per response
- **Gotchas**: Won't match cloud 70B+ quality. Occasional awkward Polish

### Gemma 3 12B (Google)

- `ollama pull gemma3:12b` (~8GB)
- **Hardware**: 16GB+ RAM recommended
- **German/Polish**: 140+ languages, 2x multilingual training data vs Gemma 2
- **Latency**: 5-15 tok/s on Apple Silicon

### Mistral 7B

- `ollama pull mistral:7b` (~4GB)
- **German/Polish**: Good for European languages but surpassed by Qwen 3 / Gemma 3
- **Latency**: Fast, well-optimized

### Phi-4 (14B, Microsoft)

- `ollama pull phi4` (~8GB)
- **Not recommended** — primarily English-focused, Microsoft warns about non-English quality

---

## Recommendations

| Priority | Option | Why |
|---|---|---|
| **Best free** | Gemini Flash-Lite + Groq fallback | 1,000 + 6,000 RPD, both free, no credit card |
| **Best cheap** | GPT-4o-mini | $0.30/month, excellent quality, most reliable |
| **Best local** | Qwen 3 8B | Strongest multilingual small model, runs on any modern Mac |
| **Best overall** | Start with Gemini Flash-Lite, Groq fallback, Ollama for offline | Free, reliable, with offline capability |

### Implementation strategy

1. Start with Gemini Flash-Lite (free, easy API, 1,000/day)
2. Add Groq as automatic fallback
3. Support Ollama as offline option
4. Optionally add GPT-4o-mini as paid fallback for best quality (~$0.30/month)
