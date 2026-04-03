# Provider-Migrations-Guide

## Provider hinzufügen (Checkliste)

So wird ein neuer Provider (z.B. „Mistral Cloud") eingebunden:

### 1. LiteLLM config (`litellm/config.yaml`)
```yaml
- model_name: mistral-fast
  litellm_params:
    model: mistral/mistral-7b-instruct
    api_key: os.environ/MISTRAL_API_KEY
    timeout: 30
```

### 2. `.env` / `.env.example`
```
MISTRAL_API_KEY=
```

### 3. `backend/app/config.py`
```python
MISTRAL_API_KEY: str = ""
```

### 4. `routing_matrix.py` — `_has_key()` erweitern
```python
if model_alias.startswith("mistral"):
    return bool(settings.MISTRAL_API_KEY)
```

### 5. `router.py` — Model-Map ergänzen
```python
_MODEL_MAP_MISTRAL: dict[str, str] = {
    "low":    "mistral-fast",
    "medium": "mistral-medium",
    "high":   "mistral-large",
}
```

### 6. `registry.py` — Adapter registrieren
```python
if model_alias.startswith("mistral"):
    return _get_mistral_adapter()
```

**Kein Eingriff in Business-Logik** (ai_story_service.py, Routers, Frontend).

---

## IONOS-Region wechseln

Nur `.env` ändern:
```
IONOS_API_BASE=https://openai.ionos.com/openai
```
Kein Code-Change, kein Build.

---

## IONOS durch anderen Provider ersetzen

1. `PROVIDER_ROUTING_SUGGEST=claude-sonnet-4-6` in `.env` setzen
2. `IONOS_API_KEY=` leer lassen
3. Deployment neu starten

Kein Code-Change. Die Routing-Matrix greift auf Anthropic zurück.

---

## Modell-ID aktualisieren

Nur in `litellm/config.yaml`:
```yaml
# vorher:
model: openai/meta-llama/Meta-Llama-3.1-8B-Instruct
# nachher:
model: openai/meta-llama/Meta-Llama-3.2-8B-Instruct
```

Der logische Alias `ionos-fast` bleibt unverändert — Backend und Frontend
sehen nie den echten Modell-Namen.
