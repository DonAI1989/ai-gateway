# AI Trading Gateway for MT5

This repository contains a small FastAPI web server that acts as a bridge
between MetaTrader 5 (MT5) and OpenAI’s ChatGPT.  It receives market
features from an Expert Advisor via HTTP, sends them to OpenAI for
analysis and returns a trading decision complete with stop‑loss,
take‑profit and risk management guidance.

## Files

| File                         | Description                                                       |
|-----------------------------|-------------------------------------------------------------------|
| `AITradingGateway_OpenAI.py`| Main FastAPI application that handles `/decide` requests and calls OpenAI |
| `requirements.txt`          | Python dependencies to install                                    |
| `Procfile`                  | Start command for Uvicorn used by Railway                         |
| `railway.json`              | Optional configuration for Railway project variables               |
| `README.md`                 | This documentation                                                |

## Deployment on Railway

1. **Create a GitHub repository.**  Place all files from this folder into the root of your repo and push it to GitHub.
2. **Sign in to [Railway](https://railway.app)** and choose **New Project → Deploy from GitHub**.  Select your newly created repository.
3. **Add environment variables** under *Settings → Variables* in Railway:
   - `OPENAI_API_KEY` – your OpenAI API key (required).
   - Optional: `OPENAI_MODEL` – override the default model name (e.g. `gpt-4o-mini` or `gpt-5`).
   - Optional: `AUTH_TOKEN` – if set, the EA must include this value in the `X-Auth` HTTP header.
4. Railway automatically installs dependencies from `requirements.txt` and uses the command in `Procfile` to run the server.
5. After deployment completes, note the public URL (e.g. `https://your-app.up.railway.app`).  Append `/decide` for the EA endpoint: `https://your-app.up.railway.app/decide`.
6. In MetaTrader 5:
   - Go to **Tools → Options → Expert Advisors** and add your Railway URL (without `/decide`) to the list of allowed WebRequest URLs.
   - Set the EA input `AI_Endpoint` to the full `/decide` URL.
   - Enable `UseAI_Decision` and configure other risk parameters as needed.

## Local Testing

To run the gateway locally for development, make sure you have Python 3.9+
installed and run the following commands:

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...            # set your API key
uvicorn AITradingGateway_OpenAI:app --host 0.0.0.0 --port 8090
```

Then point your EA to `http://localhost:8090/decide`.  Be sure to add
`http://localhost:8090` to the list of allowed WebRequest URLs in MT5.

## Security Considerations

This server relays potentially sensitive market data to OpenAI.  Never
include API keys or account numbers in the features you send.  Use the
`AUTH_TOKEN` environment variable and corresponding `X-Auth` header in
the EA to restrict access to your gateway.  OpenAI’s API usage costs
money; monitor your usage and apply quotas if needed.

---

**Disclaimer:**  This software is provided for educational purposes only and
does not constitute financial advice.  Use at your own risk.