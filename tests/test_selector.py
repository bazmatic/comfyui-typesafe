"""Choice contracts and real-host Autogrow, mapping and cache behaviour."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from aiohttp import web
from test_guard import pkg, domain, gateway, errors
import test_guard
from test_candidate import FakeLoraRuntime, FilesystemFixture, Candidate, node_module
from comfy_api.latest import io

Selector = pkg.TypeSafeLoraSelect


def response(winner='candidate_0', values=None, confidence=0.8):
    return {'model': 'jev-test', 'answers': {'decision': {
        'type': 'choice', 'choice': winner, 'confidence': confidence,
        'probabilities': values if values is not None else {'candidate_0': 0.9, 'none': 0.1}}},
        'usage': {'input_tokens': 20, 'output_tokens': 5}}


class FakeChoiceGateway:
    def __init__(self):
        self.calls = []
        self.payload = None

    async def evaluate(self, state, question, model):
        self.calls.append((state, question, model))
        payload = self.payload or response(values={key: 1.0 if key == 'candidate_0' else 0.0
                                                   for key, _ in question.criteria})
        return gateway.parse_choice(payload, model, question)


class SelectorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeChoiceGateway()
        self.candidate = domain.LoraCandidate('ink.safetensors', 'Ink drawing', -0.5, 0, '  INK\r\n🌿 ')
        self.runtime = FakeLoraRuntime(('ink.safetensors', 'paint.safetensors'))
        self.engine_patch = patch.object(Selector, 'engine', pkg.DecisionEngine(self.fake))
        self.runtime_patch = patch.object(Selector, 'runtime', self.runtime)
        self.engine_patch.start(); self.runtime_patch.start()
        self.addCleanup(self.engine_patch.stop); self.addCleanup(self.runtime_patch.stop)

    async def test_policy_outputs_and_known_record_identity(self):
        cases = [
            (response(confidence=0.5), 0.5, 'selected'),
            (response(confidence=0.49), 0.5, 'low_confidence'),
            (response('none', {'candidate_0': 0.1, 'none': 0.9}, 0), 1, 'no_match'),
            (response('candidate_0', {'candidate_0': 0.5, 'none': 0.5}, 1), 0, 'ambiguous'),
            (response('none', {'candidate_0': 0.5, 'none': 0.5}, 1), 0, 'ambiguous'),
            (response('candidate_0', {'candidate_0': 0.50000001, 'none': 0.49999999}, 0.5), 0.5, 'selected'),
        ]
        for payload, threshold, reason in cases:
            self.fake.payload = payload
            result = (await Selector.execute('draw', {'candidate0': self.candidate}, threshold)).result
            selection = result[0]
            self.assertEqual(selection.reason, reason)
            selected = reason == 'selected'
            self.assertIs(selection.candidate_or_none, self.candidate if selected else None)
            self.assertEqual(result[1:5], (self.candidate.name if selected else '', selected,
                                         payload['answers']['decision']['confidence'],
                                         self.candidate.trigger_words if selected else ''))
            details = json.loads(result[5])
            self.assertEqual(details['winner_id'], payload['answers']['decision']['choice'])
            self.assertEqual(details['reason'], reason)
            with self.assertRaises(FrozenInstanceError):
                selection.reason = 'other'
        state, question, _ = self.fake.calls[0]
        self.assertEqual(set(state), {'text', 'candidates'})
        self.assertEqual(set(state['candidates'][0]), {'id', 'name', 'description'})
        self.assertEqual({key for key, _ in question.criteria}, {'candidate_0', 'none'})
        self.assertNotIn('strength', json.dumps(state))
        self.assertNotIn('INK', json.dumps(state))

    async def test_numeric_order_and_hundred_candidates(self):
        second = domain.LoraCandidate('paint.safetensors', 'painting')
        await Selector.execute('draw', {'candidate10': second, 'candidate2': self.candidate})
        self.assertEqual([c['name'] for c in self.fake.calls[-1][0]['candidates']],
                         ['ink.safetensors', 'paint.safetensors'])
        candidates = {f'candidate{i}': domain.LoraCandidate(f'{i}.safetensors', f'style {i}') for i in range(100)}
        self.runtime.names = tuple(c.name for c in candidates.values())
        await Selector.execute('draw', dict(reversed(list(candidates.items()))))
        self.assertEqual(len(self.fake.calls[-1][1].criteria), 101)
        self.assertEqual(self.fake.calls[-1][0]['candidates'][99]['name'], '99.safetensors')

    async def test_same_lora_with_different_trigger_words(self):
        other = domain.LoraCandidate('ink.safetensors', 'Ink portrait', 1.0, 1.0, 'PORTRAIT')
        self.fake.payload = response('candidate_1', {'candidate_0': 0.1, 'candidate_1': 0.8, 'none': 0.1}, 0.9)
        result = (await Selector.execute('draw', {'candidate0': self.candidate, 'candidate1': other})).result
        self.assertIs(result[0].candidate_or_none, other)
        self.assertEqual(result[1:5], ('ink.safetensors', True, 0.9, 'PORTRAIT'))
        self.assertEqual([c['description'] for c in self.fake.calls[-1][0]['candidates']], ['Ink drawing', 'Ink portrait'])

    async def test_configuration_preflight_no_inference(self):
        forged = domain.LoraCandidate('ink.safetensors', 'ink')
        object.__setattr__(forged, 'strength_model', float('nan'))
        invalid = [dict(candidates=x) for x in ({}, [], {'candidate0': []}, {'candidate0': 'ink'},
                   {'candidate0': forged}, {'candidate100': self.candidate}, {'candidate01': self.candidate},
                   {'candidate0': domain.LoraCandidate('missing.safetensors', 'missing')})]
        invalid += [dict(text=x) for x in ('', None, ' ')]
        invalid += [dict(min_confidence=x) for x in (True, -1, 2, float('nan'), float('inf'))]
        invalid += [{'model': ''}, {'refresh_id': True}]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(errors.ConfigurationError):
                await Selector.execute(**({'text': 'draw', 'candidates': {'candidate0': self.candidate}} | change))
        self.assertEqual(self.fake.calls, [])

    async def test_wrong_judgment_and_provider_errors_propagate(self):
        from unittest.mock import AsyncMock
        for value in (None, domain.NoulJudgment(0.2, domain.DecisionMetadata('m', 'm', 0, 0))):
            with patch.object(self.fake, 'evaluate', AsyncMock(return_value=value)), self.assertRaises(errors.ProviderProtocolError):
                await Selector.execute('draw', {'candidate0': self.candidate})
        with patch.object(self.fake, 'evaluate', side_effect=errors.ProviderUnavailable('offline')):
            with self.assertRaises(errors.ProviderUnavailable):
                await Selector.execute('draw', {'candidate0': self.candidate})

    def test_schema(self):
        info = Selector.GET_NODE_INFO_V1()
        self.assertEqual(info['category'], 'TypeSafe')
        template = info['input']['required']['candidates'][1]['template']
        self.assertEqual((template['min'], template['max'], template['prefix']), (1, 100, 'candidate'))
        self.assertEqual(Selector.RETURN_TYPES[0], 'TYPESAFE_LORA_SELECTION')


class ChoiceProtocolTests(unittest.TestCase):
    def setUp(self):
        self.question = domain.ChoiceQuestion('select', (('candidate_0', 'ink'), ('none', 'no match')))

    def test_invalid_payloads(self):
        payloads = [None, [], {}, response('unknown'), response([], confidence=0.8)]
        for key, values in [('probabilities', [{}, [], {'candidate_0': 1}, {'candidate_0': 0.8, 'none': 0.1, 'extra': 0.1},
                  {'candidate_0': 0.6, 'none': 0.1}, {'candidate_0': 0.2, 'none': 0.8},
                  *({'candidate_0': v, 'none': 0.1} for v in (True, float('nan'), float('inf'), -1, '0.9', 10**400))]),
                  ('confidence', [True, -1, 2, float('nan'), float('inf'), '0.8']), ('type', ['noul', None])]:
            for value in values:
                p = response(); p['answers']['decision'][key] = value; payloads.append(p)
        for key in ('choice', 'probabilities', 'confidence', 'type'):
            p = response(); del p['answers']['decision'][key]; payloads.append(p)
        for key, value in [('answers', {'wrong': {}}), ('model', ''), ('usage', {'input_tokens': True, 'output_tokens': 1})]:
            p = response(); p[key] = value; payloads.append(p)
        p = response(); p['answers']['extra'] = {}; payloads.append(p)
        for p in payloads:
            with self.subTest(payload=p), self.assertRaises(errors.ProviderProtocolError):
                gateway.parse_choice(p, 'jev-latest', self.question)

    def test_tolerance_and_frozen_collections(self):
        judgment = gateway.parse_choice(response(values={'candidate_0': 0.4999999, 'none': 0.5000001}), 'm', self.question)
        self.assertEqual(judgment.winner_id, 'candidate_0')
        self.assertIsInstance(judgment.probabilities, tuple)
        with self.assertRaises(FrozenInstanceError):
            judgment.confidence = 1
        with self.assertRaises(errors.ProviderProtocolError):
            domain.ChoiceJudgment('candidate_0', [('candidate_0', 1)], 1, judgment.metadata)
        with self.assertRaises(errors.ProviderProtocolError):
            domain.ChoiceJudgment('candidate_0', (('candidate_0', 0.5), ('candidate_0', 0.5)), 1, judgment.metadata)
        self.assertEqual(gateway.parse_choice(response(values={'candidate_0': 0.9, 'none': 0.105}), 'm', self.question).probabilities,
                         (('candidate_0', 0.9), ('none', 0.105)))


class ChoiceTransportTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_guard.TransportTests.asyncSetUp
    asyncTearDown = test_guard.TransportTests.asyncTearDown

    async def test_choice_request_and_bad_success(self):
        question = domain.ChoiceQuestion('pick', (('candidate_0', 'ink'), ('none', 'no match')))
        self.responses = [web.json_response(response())]
        result = await gateway.TypeSafeHttpGateway().evaluate({'text': 'draw', 'candidates': []}, question, 'jev-latest')
        self.assertEqual(result.winner_id, 'candidate_0')
        body = self.calls[0][1]
        self.assertEqual(body['questions'], {'decision': {'type': 'choice', 'instructions': 'pick',
                                                                    'criteria': {'candidate_0': 'ink', 'none': 'no match'}}})
        self.responses = [web.json_response(response('unknown'))]
        with self.assertRaises(errors.ProviderProtocolError):
            await gateway.TypeSafeHttpGateway().evaluate({}, question, 'm')
        self.assertEqual(len(self.calls), 2)


class SelectorHostTests(FilesystemFixture, unittest.IsolatedAsyncioTestCase):
    async def test_autogrow_mapping_and_cache(self):
        import execution
        import nodes
        seen = []
        class Consumer(io.ComfyNode):
            @classmethod
            def define_schema(cls):
                return io.Schema(node_id='SelectionConsumer', inputs=[node_module.LoraSelectionSocket.Input('selection')],
                                 outputs=[], is_output_node=True)
            @classmethod
            def execute(cls, selection):
                seen.append(selection)
                return io.NodeOutput()
        class TextBatch(io.ComfyNode):
            @classmethod
            def define_schema(cls):
                return io.Schema(node_id='TextBatch', inputs=[], outputs=[io.String.Output('text', is_output_list=True)])
            @classmethod
            def execute(cls):
                return io.NodeOutput(['first', 'second'])
        second_file = self.root / 'paint.safetensors'; second_file.write_bytes(b'not weights')
        fake = FakeChoiceGateway()
        prompt = {
            '1': {'class_type': 'TypeSafeLoraCandidate', 'inputs': {'lora_name': self.name, 'description': 'ink', 'strength_model': 1.0, 'strength_clip': 1.0, 'trigger_words': ''}},
            '2': {'class_type': 'TypeSafeLoraCandidate', 'inputs': {'lora_name': 'paint.safetensors', 'description': 'paint', 'strength_model': 1.0, 'strength_clip': 1.0, 'trigger_words': ''}},
            '3': {'class_type': 'TypeSafeLoraSelect', 'inputs': {
                'text': 'draw', 'candidates.candidate0': ['1', 0], 'candidates.candidate1': ['2', 0],
                'min_confidence': 0.5, 'model': 'jev-latest', 'refresh_id': 0}},
            '4': {'class_type': 'SelectionConsumer', 'inputs': {'selection': ['3', 0]}}}
        server = SimpleNamespace(client_id=None, last_node_id=None, send_sync=lambda *a, **kw: None)
        executor = execution.PromptExecutor(server, cache_args={'ram': 0})
        with patch.object(Candidate, 'runtime', self.runtime), patch.object(Selector, 'runtime', self.runtime), \
                patch.object(Selector, 'engine', pkg.DecisionEngine(fake)), patch.dict(nodes.NODE_CLASS_MAPPINGS, {
                    'TypeSafeLoraCandidate': Candidate, 'TypeSafeLoraSelect': Selector,
                    'SelectionConsumer': Consumer, 'TextBatch': TextBatch}):
            for cls in (Candidate, Selector, Consumer, TextBatch): cls.GET_SCHEMA()
            valid, error, _, _ = await execution.validate_prompt('valid', deepcopy(prompt), None)
            self.assertTrue(valid, error)
            for run in range(2):
                await executor.execute_async(deepcopy(prompt), str(run), execute_outputs=['4'])
                self.assertTrue(executor.success)
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(len(fake.calls[0][0]['candidates']), 2)
            for key, value in [('refresh_id', 1), ('model', 'pinned'), ('min_confidence', 0.6), ('text', 'painting')]:
                prompt['3']['inputs'][key] = value
                await executor.execute_async(deepcopy(prompt), key, execute_outputs=['4'])
                self.assertTrue(executor.success)
            for key, value in [('description', 'linework'), ('strength_model', 0), ('trigger_words', 'INK')]:
                prompt['1']['inputs'][key] = value
                await executor.execute_async(deepcopy(prompt), key, execute_outputs=['4'])
                self.assertTrue(executor.success)
            self.assertEqual(len(fake.calls), 8)
            self.file.write_bytes(b'new metadata')
            await executor.execute_async(deepcopy(prompt), 'file', execute_outputs=['4'])
            self.assertTrue(executor.success)
            self.assertEqual(len(fake.calls), 9)
            prompt['5'] = {'class_type': 'TextBatch', 'inputs': {}}
            prompt['3']['inputs']['text'] = ['5', 0]
            await executor.execute_async(deepcopy(prompt), 'batch', execute_outputs=['4'])
            self.assertTrue(executor.success)
            self.assertEqual(len(fake.calls), 11)
            self.assertEqual([call[0]['text'] for call in fake.calls[-2:]], ['first', 'second'])
            self.assertTrue(all(len(call[0]['candidates']) == 2 for call in fake.calls[-2:]))
            self.file.unlink()
            with self.assertLogs(level='WARNING'):
                await executor.execute_async(deepcopy(prompt), 'removed', execute_outputs=['4'])
            self.assertFalse(executor.success)
            self.assertEqual(len(fake.calls), 11)
