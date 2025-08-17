"""
AITradingGateway_OpenAI.py
==========================

This module implements a simple FastAPI application that exposes an API
endpoint for use with an MT5 Expert Advisor.  The EA sends a text payload
describing current market features to the `/decide` endpoint.  The gateway
invokes OpenAI's ChatGPT model to determine whether to buy, sell or stay
flat and returns the decision along with suggested stop‑loss/take‑profit
levels and risk management information.

Deployment is intended for platforms such as Railway but it can also be
run locally.  See the accompanying README for deployment details.
"""

from __future__ import annotations

import json
import os
import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from openai import OpenAI


# Configure logging so that debugging information is visible in Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load OpenAI API key and optional defaults from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning(
        "OPENAI_API_KEY is not set. The gateway will not be able to call OpenAI"
    )

# Initialise the OpenAI client using the new v1 API interface.
# The OpenAI library as of v1.0.0 no longer exposes ChatCompletion directly on the top
# level package.  Instead, a client instance is created which holds the API
# key and endpoints (see https://github.com/openai/openai-python for details).
client: OpenAI | None = None
try:
    if OPENAI_API_KEY:
        client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as exc:
    logger.error("Failed to initialise OpenAI client: %s", exc)
    client = None

MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")

app = FastAPI()


@app.get("/")
async def root() -> Dict[str, str]:
    """Simple root endpoint to show the service is running."""
    return {"message": "AI Trading Gateway is running. POST to /decide"}


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/decide")
async def decide(request: Request) -> Dict[str, str]:
    """
    Endpoint to accept a plain text body describing market features and
    return a trading decision.  The request body should be a raw string
    containing comma or semicolon separated features.  The response will
    be a semicolon separated list of key=value pairs understood by the EA.
    """
    # Optional token header check
    if AUTH_TOKEN:
        token_header = request.headers.get("X-Auth")
        if token_header != AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized: bad token")

    try:
        body = await request.body()
        # Accept both bytes and strings
        content = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)
    except Exception as exc:
        logger.error("Failed to read request body: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid request body")

    logger.info("Received payload for decision: %s", content)

    # If no API key configured, return a flat decision
    if not OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY configured; returning flat decision")
        return {"decision": "action=flat;sl_pips=0;tp_pips=0;risk_pct=0;lots=0;regime=unknown;confidence=0;"}

    # Build messages for ChatGPT.  The system message instructs the model
    # to respond with JSON containing the required fields.  The user
    # message consists of the raw features.  Additional context could be
    # supplied here such as news or historical performance.
    system_msg = (
        "You are an AI trading assistant. Given market feature input, you must "
        "respond with a JSON object containing the following keys: "
        "action (one of 'buy', 'sell', 'flat'), sl_pips, tp_pips, risk_pct, lots, "
        "regime (short description of market condition), and confidence (0 to 1). "
        "When there is no clear trade, set action to 'flat'. Respond only with "
        "valid JSON without any additional explanation."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": content},
    ]

    # Use the new OpenAI client to call chat completions.  In v1 the
    # chat endpoint is accessed via client.chat.completions.create().
    if client is None:
        logger.error("OpenAI client is not initialised; returning flat decision")
        return {
            "decision": "action=flat;sl_pips=0;tp_pips=0;risk_pct=0;lots=0;regime=error;confidence=0;"
        }
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.0,
            max_tokens=200,
        )
    except Exception as exc:
        logger.error("OpenAI call failed: %s", exc)
        # Fall back to flat decision on error
        return {
            "decision": "action=flat;sl_pips=0;tp_pips=0;risk_pct=0;lots=0;regime=error;confidence=0;"
        }

    # Extract the assistant's content from the response.  Note: the new API
    # returns a ChatCompletionResponse object with a list of choices and
    # nested message objects.
    content_raw = response.choices[0].message.content.strip()
    logger.info("Raw response from OpenAI: %s", content_raw)

    # Attempt to parse JSON response
    try:
        parsed: Dict[str, Any] = json.loads(content_raw)
    except Exception as exc:
        logger.error("Failed to parse JSON from OpenAI response: %s", exc)
        return {"decision": "action=flat;sl_pips=0;tp_pips=0;risk_pct=0;lots=0;regime=parse_error;confidence=0;"}

    # Convert to key=value; format expected by EA
    def to_field(key: str) -> str:
        return f"{key}=" + (str(parsed.get(key)) if parsed.get(key) is not None else "")

    decision_str = (
        f"action={parsed.get('action', 'flat')};"
        f"sl_pips={parsed.get('sl_pips', 0)};"
        f"tp_pips={parsed.get('tp_pips', 0)};"
        f"risk_pct={parsed.get('risk_pct', 0)};"
        f"lots={parsed.get('lots', 0)};"
        f"regime={parsed.get('regime', 'unknown')};"
        f"confidence={parsed.get('confidence', 0)};"
    )
    return {"decision": decision_str}