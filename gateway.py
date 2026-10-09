import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import os
import random
from typing import Protocol

import aiohttp

from .domain import ChoiceJudgment, ChoiceQuestion, DecisionMetadata, Judgment, NoulJudgment, NoulQuestion, Question, nonblank
from .errors import ConfigurationError, ProviderProtocolError, ProviderUnavailable

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MAX_BODY = 1024 * 1024


class JudgmentGateway(Protocol):
    async def evaluate(self, state: dict[str, object], question: Question, model: str) -> Judgment: ...


def parse_noul(payload, model):
    try:
        if set(payload["answers"]) != {"decision"}:
            raise ValueError
        answer = payload["answers"]["decision"]
        if answer["type"] != "noul":
            raise ValueError
        returned_model = payload["model"]
        if not isinstance(returned_model, str) or not returned_model.strip():
            raise ValueError
        usage = payload["usage"]
        counts = (usage["input_tokens"], usage["output_tokens"])
        if any(type(v) is not int or v < 0 for v in counts):
            raise ValueError
        return NoulJudgment(answer["noul"], DecisionMetadata(model, returned_model, *counts))
    except (KeyError, TypeError, ValueError, ProviderProtocolError):
        raise ProviderProtocolError("TypeSafe returned an invalid Noul response.") from None


def parse_choice(payload, model, question):
    try:
        if set(payload["answers"]) != {"decision"}:
            raise ValueError
        answer = payload["answers"]["decision"]
        if answer["type"] != "choice" or not isinstance(answer["probabilities"], dict):
            raise ValueError
        usage = payload["usage"]
        judgment = ChoiceJudgment(
            answer["choice"], tuple(answer["probabilities"].items()), answer["confidence"],
            DecisionMetadata(model, payload["model"], usage["input_tokens"], usage["output_tokens"]),
        )
        judgment.validate_options(key for key, _ in question.criteria)
        return judgment
    except (KeyError, TypeError, ValueError, ProviderProtocolError):
        raise ProviderProtocolError("TypeSafe returned an invalid Choice response.") from None


def retry_delay(header):
    if header is not None:
        try:
            if header.strip().isdigit():
                return float(header)
            date = parsedate_to_datetime(header)
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    return random.uniform(0.2, 0.5)


class TypeSafeHttpGateway:
    async def evaluate(self, state, question, model):
        nonblank(model, "Model")
        if not isinstance(question, (NoulQuestion, ChoiceQuestion)):
            raise ConfigurationError("Unsupported judgment question.")
        key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not key or any(ord(c) < 32 or ord(c) > 126 for c in key):
            raise ConfigurationError("Set a valid TYPESAFE_API_KEY in the ComfyUI server environment.")
        try:
            seconds = float(os.environ.get("TYPESAFE_TIMEOUT_SECONDS", "30"))
            if not math.isfinite(seconds) or not 1 <= seconds <= 120:
                raise ValueError
        except ValueError:
            raise ConfigurationError("TYPESAFE_TIMEOUT_SECONDS must be between 1 and 120.") from None
        question_body = {"type": "noul", "instructions": question.instructions}
        if isinstance(question, ChoiceQuestion):
            question.__post_init__()
            question_body.update(type="choice", criteria=dict(question.criteria))
        request = {"state": state, "model": model, "questions": {"decision": question_body}}

        async def request_with_deadline():
            deadline = asyncio.get_running_loop().time() + seconds
            async with aiohttp.ClientSession() as session:
                for attempt in range(2):
                    remaining = deadline - asyncio.get_running_loop().time()
                    timeout = aiohttp.ClientTimeout(total=remaining)
                    async with session.post(ENDPOINT, json=request,
                                            headers={"Authorization": f"Bearer {key}"},
                                            timeout=timeout, allow_redirects=False) as response:
                        if response.status in (429, 529) and attempt == 0:
                            delay = retry_delay(response.headers.get("Retry-After"))
                            if delay >= deadline - asyncio.get_running_loop().time():
                                raise ProviderUnavailable("TypeSafe retry exceeds the evaluation deadline.")
                        elif response.status != 200:
                            if response.status in (401, 403, 422):
                                raise ConfigurationError(f"TypeSafe HTTP {response.status}; check credentials and request configuration.")
                            raise ProviderUnavailable(f"TypeSafe HTTP {response.status}; evaluation stopped.")
                        else:
                            body = bytearray()
                            async for chunk in response.content.iter_chunked(65536):
                                body.extend(chunk)
                                if len(body) > MAX_BODY:
                                    raise ProviderProtocolError("TypeSafe response exceeds 1 MiB.")
                            try:
                                payload = json.loads(body)
                            except (ValueError, UnicodeError, RecursionError):
                                raise ProviderProtocolError("TypeSafe returned invalid JSON.") from None
                            if isinstance(question, ChoiceQuestion):
                                return parse_choice(payload, model, question)
                            return parse_noul(payload, model)
                    await asyncio.sleep(delay)
        # ComfyUI runs sync nodes (sampling, model loads) on its event loop, so a request
        # awaited there starves and misses its deadline. Run it on a private loop instead.
        loop = asyncio.new_event_loop()
        task = loop.create_task(asyncio.wait_for(request_with_deadline(), timeout=seconds))
        worker = asyncio.get_running_loop().run_in_executor(None, loop.run_until_complete, asyncio.wait([task]))
        try:
            await asyncio.shield(worker)
            return task.result()
        except asyncio.CancelledError:
            loop.call_soon_threadsafe(task.cancel)
            raise
        except (asyncio.TimeoutError, TimeoutError):
            raise ProviderUnavailable("TypeSafe evaluation timed out; retry the prompt.") from None
        except aiohttp.ClientError:
            raise ProviderUnavailable("TypeSafe connection failed; retry the prompt.") from None
        finally:
            await asyncio.wait([worker])
            loop.close()
