"""Offline contract and host tests; use run.py with ComfyUI's Python environment."""
import asyncio
from copy import deepcopy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestServer
from comfy.cli_args import args
args.cpu = True

package_root = Path(__file__).resolve().parents[1]
package_spec = importlib.util.spec_from_file_location(
    'comfyui_typesafe_under_test', package_root / '__init__.py',
    submodule_search_locations=[str(package_root)],
)
pkg = importlib.util.module_from_spec(package_spec)
sys.modules[package_spec.name] = pkg
package_spec.loader.exec_module(pkg)
domain = importlib.import_module(pkg.__name__ + '.domain')
gateway = importlib.import_module(pkg.__name__ + '.gateway')
errors = importlib.import_module(pkg.__name__ + '.errors')
Guard = pkg.TypeSafeTextGuard


def response(value=0.2):
    return {'model': 'jev-test', 'answers': {'decision': {'type': 'noul', 'noul': value}},
            'usage': {'input_tokens': 12, 'output_tokens': 2}}


class FakeGateway:
    def __init__(self, value=0.2):
        self.value = value
        self.calls = []

    async def evaluate(self, state, question, model):
        self.calls.append((state, question, model))
        return gateway.parse_noul(response(self.value), model)


class GuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake = FakeGateway()
        Guard.engine = pkg.DecisionEngine(self.fake)

    async def test_policy_and_preservation(self):
        text = '  original\r\ntext 🌿  '
        for value in (0, 0.49):
            self.fake.value = value
            result = await Guard.execute(text)
            self.assertEqual(result.result[0], text)
            self.assertEqual(result.result[1], value)
            self.assertEqual(json.loads(result.result[2])['metadata']['input_tokens'], 12)
        for value in (0.5, 1):
            self.fake.value = value
            with self.assertRaises(errors.GuardRejected) as caught:
                await Guard.execute(text)
            self.assertNotIn(text, str(caught.exception))
            self.assertEqual(caught.exception.probability, value)

    async def test_configuration(self):
        for kwargs in ({'text': ' '}, {'text': 'x', 'condition': ''}, {'text': 'x', 'model': ''},
                       *({'text': 'x', 'stop_threshold': x} for x in (True, -1, 2, float('nan'), float('inf'))),
                       {'text': 'x', 'refresh_id': True}):
            with self.assertRaises(errors.ConfigurationError):
                await Guard.execute(**kwargs)
        self.assertEqual(self.fake.calls, [])

    async def test_registration_without_credentials(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': ''}):
            extension = await pkg.comfy_entrypoint()
        self.assertEqual(await extension.get_node_list(), [Guard, pkg.TypeSafeLoraCandidate, pkg.TypeSafeLoraSelect, pkg.TypeSafeLoraApply])
        schema = Guard.GET_SCHEMA()
        self.assertEqual(schema.node_id, 'TypeSafeTextGuard')
        self.assertEqual(len(schema.outputs), 3)

    async def test_bad_provider_records(self):
        payloads = [None, [], {}, response(True), response(float('nan')), response(float('inf')), response(-1)]
        for section, replacement in [('answers', {}), ('model', ''), ('usage', {'input_tokens': True, 'output_tokens': 1})]:
            p = response(); p[section] = replacement; payloads.append(p)
        for answer in ({'type': 'choice', 'noul': 0.2}, {'type': 'noul'}, None):
            p = response(); p['answers']['decision'] = answer; payloads.append(p)
        p = response(); p['answers']['extra'] = {}; payloads.append(p)
        for p in payloads:
            with self.assertRaises(errors.ProviderProtocolError):
                gateway.parse_noul(p, 'jev-latest')


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.responses = [web.json_response(response())]
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.block = False
        async def handler(request):
            self.calls.append((dict(request.headers), await request.json()))
            self.entered.set()
            if self.block:
                await self.release.wait()
            return self.responses.pop(0)
        app = web.Application()
        app.router.add_post('/v1/systemone', handler)
        self.server = TestServer(app)
        await self.server.start_server()
        self.env = patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-only', 'TYPESAFE_TIMEOUT_SECONDS': '1'})
        self.env.start()
        self.url = patch.object(gateway, 'ENDPOINT', str(self.server.make_url('/v1/systemone')))
        self.url.start()

    async def asyncTearDown(self):
        self.release.set()
        await self.server.close()
        self.url.stop(); self.env.stop()

    async def evaluate(self):
        return await gateway.TypeSafeHttpGateway().evaluate({'text': 'private input'}, domain.NoulQuestion('condition'), 'jev-latest')

    async def test_valid_request(self):
        answer = await self.evaluate()
        self.assertEqual(answer.probability, 0.2)
        headers, body = self.calls[0]
        self.assertEqual(headers['Authorization'], 'Bearer test-only')
        self.assertEqual(body['questions'], {'decision': {'type': 'noul', 'instructions': 'condition'}})
        self.assertEqual(body['state'], {'text': 'private input'})

    async def test_missing_key_and_bad_deadline(self):
        for config in ({'TYPESAFE_API_KEY': ''}, {'TYPESAFE_TIMEOUT_SECONDS': 'nan'}, {'TYPESAFE_TIMEOUT_SECONDS': '121'}):
            with patch.dict(os.environ, config), self.assertRaises(errors.ConfigurationError):
                await self.evaluate()
        self.assertEqual(self.calls, [])

    async def test_http_errors_no_retry(self):
        for status in (401, 422, 500, 302):
            self.responses = [web.Response(status=status, headers={'Location': '/stolen'}, text='private input test-only')]
            with self.assertRaises((errors.ConfigurationError, errors.ProviderUnavailable)) as caught:
                await self.evaluate()
            self.assertNotIn('private input', str(caught.exception))
            self.assertNotIn('test-only', str(caught.exception))
        self.assertEqual(len(self.calls), 4)

    async def test_retry_success_and_limit(self):
        for status in (429, 529):
            self.responses = [web.Response(status=status, headers={'Retry-After': '0'}), web.json_response(response())]
            self.assertEqual((await self.evaluate()).probability, 0.2)
        self.responses = [web.Response(status=429, headers={'Retry-After': '0'}), web.Response(status=529)]
        with self.assertRaises(errors.ProviderUnavailable):
            await self.evaluate()
        self.assertEqual(len(self.calls), 6)

    async def test_retry_exceeds_deadline(self):
        self.responses = [web.Response(status=429, headers={'Retry-After': '5'})]
        with self.assertRaises(errors.ProviderUnavailable):
            await self.evaluate()
        self.assertEqual(len(self.calls), 1)

    async def test_retry_dates_and_jitter(self):
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime
        future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60))
        self.assertTrue(58 <= gateway.retry_delay(future) <= 60)
        self.assertTrue(0.2 <= gateway.retry_delay('invalid') <= 0.5)
        self.responses = [web.Response(status=529), web.json_response(response())]
        self.assertEqual((await self.evaluate()).probability, 0.2)

    async def test_connection_failure_not_retried(self):
        await self.server.close()
        with self.assertRaises(errors.ProviderUnavailable):
            await self.evaluate()
        self.assertEqual(self.calls, [])

    async def test_invalid_and_oversized_body(self):
        for body in (b'bad json', b'x' * (gateway.MAX_BODY + 1), json.dumps(response(float('nan'))).encode()):
            self.responses = [web.Response(body=body)]
            with self.assertRaises(errors.ProviderProtocolError):
                await self.evaluate()
        self.assertEqual(len(self.calls), 3)

    async def test_timeout_and_cancellation_close_sessions(self):
        real_session = gateway.aiohttp.ClientSession
        sessions = []
        def session_factory(*a, **kw):
            session = real_session(*a, **kw); sessions.append(session); return session
        self.block = True
        with patch.object(gateway.aiohttp, 'ClientSession', session_factory):
            with self.assertRaises(errors.ProviderUnavailable):
                await self.evaluate()
            self.assertTrue(sessions[-1].closed)
            self.entered.clear()
            task = asyncio.create_task(self.evaluate())
            await self.entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(sessions[-1].closed)
        self.assertEqual(len(self.calls), 2)


class HostTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_stop_and_cache(self):
        import execution
        import nodes
        from comfy_api.latest import io
        from types import SimpleNamespace
        seen = []
        class Sentinel(io.ComfyNode):
            @classmethod
            def define_schema(cls):
                return io.Schema(node_id='TypeSafeTestSentinel', inputs=[io.String.Input('text')], outputs=[], is_output_node=True)
            @classmethod
            def execute(cls, text):
                seen.append(text)
                return io.NodeOutput()
        fake = FakeGateway()
        Guard.engine = pkg.DecisionEngine(fake)
        Guard.GET_SCHEMA(); Sentinel.GET_SCHEMA()
        server = SimpleNamespace(client_id=None, last_node_id=None, send_sync=lambda *a, **kw: None)
        executor = execution.PromptExecutor(server, cache_args={'ram': 0})
        prompt = {'1': {'class_type': 'TypeSafeTextGuard', 'inputs': {
            'text': 'original', 'condition': 'failure?', 'stop_threshold': 0.5, 'model': 'jev-latest', 'refresh_id': 0}},
            '2': {'class_type': 'TypeSafeTestSentinel', 'inputs': {'text': ['1', 0]}}}
        with patch.dict(nodes.NODE_CLASS_MAPPINGS, {'TypeSafeTextGuard': Guard, 'TypeSafeTestSentinel': Sentinel}):
            valid, error, _, _ = await execution.validate_prompt('validation', deepcopy(prompt), None)
            self.assertTrue(valid, error)
            for run in range(2):
                await executor.execute_async(deepcopy(prompt), str(run), execute_outputs=['2'])
                self.assertTrue(executor.success)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(seen, ['original'])
            for key, value in [('refresh_id', 1), ('model', 'jev-pinned'), ('stop_threshold', 0.6)]:
                prompt['1']['inputs'][key] = value
                await executor.execute_async(deepcopy(prompt), key, execute_outputs=['2'])
                self.assertTrue(executor.success)
            self.assertEqual(len(fake.calls), 4)
            fake.value = 0.9
            prompt['1']['inputs']['refresh_id'] = 2
            count = len(seen)
            with self.assertLogs(level='ERROR'):
                await executor.execute_async(deepcopy(prompt), 'reject', execute_outputs=['2'])
            self.assertFalse(executor.success)
            self.assertEqual(len(seen), count)
            self.assertTrue(any(event == 'execution_error' for event, _ in executor.status_messages))
