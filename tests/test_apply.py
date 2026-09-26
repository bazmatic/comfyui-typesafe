"""Application contracts use real host execution/core loader with fake weight decoding."""
from copy import deepcopy
from dataclasses import astuple
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_guard import pkg, domain, errors
from test_candidate import FakeLoraRuntime, FilesystemFixture, Candidate, node_module
from test_selector import FakeChoiceGateway, Selector
from comfy_api.latest import io

Apply = pkg.TypeSafeLoraApply


def selection(candidate=None):
    winner = 'candidate_0' if candidate else 'none'
    judgment = domain.ChoiceJudgment(winner, ((winner, 1.0),), 1.0,
                                     domain.DecisionMetadata('test', 'test', 0, 0))
    return domain.LoraSelection(candidate, 'selected' if candidate else 'no_match', judgment)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeLoraRuntime()
        self.runtime_patch = patch.object(Apply, 'runtime', self.fake)
        self.runtime_patch.start(); self.addCleanup(self.runtime_patch.stop)
        self.model, self.clip = object(), object()
        self.candidate = domain.LoraCandidate(self.fake.names[0], 'ink', -0.5, 0, 'verbatim')

    def test_schema_and_none_without_any_runtime_access(self):
        inputs = Apply.INPUT_TYPES()['required']
        self.assertEqual({name: spec[0] for name, spec in inputs.items()},
                         {'model': 'MODEL', 'clip': 'CLIP', 'selection': 'TYPESAFE_LORA_SELECTION'})
        self.assertEqual(Apply.RETURN_TYPES, ['MODEL', 'CLIP'])
        self.assertEqual(Apply.GET_SCHEMA().category, 'TypeSafe')
        with patch.object(Apply, 'runtime', None):
            result = Apply.execute(self.model, self.clip, selection()).result
            self.assertIs(result[0], self.model); self.assertIs(result[1], self.clip)
            self.assertEqual(Apply.fingerprint_inputs(selection()), ('none',))
            self.assertTrue(math.isnan(Apply.fingerprint_inputs()))
        self.assertEqual(self.fake.checked, []); self.assertEqual(self.fake.loads, [])

    def test_exact_selected_application_and_fingerprint(self):
        record = selection(self.candidate)
        self.assertEqual(Apply.execute(self.model, self.clip, record).result, self.fake.applied)
        self.assertEqual(self.fake.loads, [(self.model, self.clip, self.candidate.name, -0.5, 0)])
        self.assertEqual(Apply.fingerprint_inputs(record), astuple(self.fake.fingerprint(self.candidate.name)))
        self.fake.names = ()
        for action in (lambda: Apply.execute(self.model, self.clip, record), lambda: Apply.fingerprint_inputs(record)):
            with self.assertRaises(errors.LoraApplicationError): action()
        self.assertEqual(len(self.fake.loads), 1)

    def test_malformed_runtime_records_rejected_before_io(self):
        forged = selection(self.candidate)
        object.__setattr__(forged.candidate_or_none, 'strength_model', float('nan'))
        wrong_reason = selection()
        object.__setattr__(wrong_reason, 'reason', 'selected')
        invalid_judgment = selection()
        object.__setattr__(invalid_judgment.raw_judgment, 'confidence', float('nan'))
        for value in ({}, 'none', self.candidate, forged, wrong_reason, invalid_judgment):
            for action in (lambda: Apply.execute(self.model, self.clip, value), lambda: Apply.fingerprint_inputs(value)):
                with self.assertRaises((errors.ConfigurationError, errors.ProviderProtocolError)): action()
        with self.assertRaises(errors.ConfigurationError):
            Apply.execute(self.model, self.clip, None)
        self.assertEqual(self.fake.checked, []); self.assertEqual(self.fake.loads, [])


class CoreLoaderTests(FilesystemFixture, unittest.TestCase):
    def test_core_loader_fresh_weights_exact_settings_and_visible_warnings(self):
        import nodes
        loads = []
        def read(path, safe_load):
            self.assertTrue(safe_load)
            data = self.file.read_bytes(); loads.append(data); return data
        candidate = domain.LoraCandidate(self.name, 'ink', -2.5, 0.75)
        model, clip = object(), object()
        with patch.object(nodes.comfy.utils, 'load_torch_file', side_effect=read), \
                patch.object(nodes.comfy.sd, 'load_lora_for_models', return_value=('patched model', 'patched clip')) as patcher:
            self.assertEqual(self.runtime.apply(model, clip, candidate), ('patched model', 'patched clip'))
            self.file.write_bytes(b'replacement weight fixture')
            self.runtime.apply(model, clip, candidate)
            self.assertNotEqual(loads[0], loads[1])
            self.assertEqual(patcher.call_args.args, (model, clip, loads[1], -2.5, 0.75))
            self.assertEqual(patcher.call_count, 2)
        def warn(*args):
            import logging
            logging.warning('lora key not loaded: fixture key')
            return model, clip
        with patch.object(nodes.comfy.utils, 'load_torch_file', return_value={}), \
                patch.object(nodes.comfy.sd, 'load_lora_for_models', side_effect=warn), self.assertLogs(level='WARNING') as logs:
            self.runtime.apply(model, clip, candidate)
        self.assertIn('lora key not loaded', str(logs.output))

    def test_zero_strength_and_loading_error_and_removed_file(self):
        import nodes
        model, clip = object(), object()
        zero = domain.LoraCandidate(self.name, 'ink', 0, 0)
        with patch.object(nodes.comfy.utils, 'load_torch_file', side_effect=AssertionError('weight read')):
            result = self.runtime.apply(model, clip, zero)
            self.assertIs(result[0], model); self.assertIs(result[1], clip)
        with patch.object(nodes.comfy.utils, 'load_torch_file', side_effect=ValueError('fixture shape mismatch')):
            with self.assertRaisesRegex(errors.LoraApplicationError, 'fixture shape mismatch') as caught:
                self.runtime.apply(model, clip, domain.LoraCandidate(self.name, 'ink'))
            self.assertIsInstance(caught.exception.__cause__, ValueError)
        from comfy.model_management import InterruptProcessingException
        with patch.object(nodes.LoraLoader, 'load_lora', side_effect=InterruptProcessingException()):
            with self.assertRaises(InterruptProcessingException): self.runtime.apply(model, clip, zero)
        self.file.unlink()
        with patch.object(nodes.LoraLoader, 'load_lora', side_effect=AssertionError('loader called')):
            with self.assertRaises(errors.LoraApplicationError): self.runtime.apply(model, clip, zero)


class ApplyHostTests(FilesystemFixture, unittest.IsolatedAsyncioTestCase):
    async def test_real_executor_cache_none_and_arbitrary_cached_selection(self):
        import execution
        import nodes
        model, clip = object(), object()
        seen, loaded = [], []
        selected = selection(domain.LoraCandidate(self.name, 'ink'))
        class Source(io.ComfyNode):
            @classmethod
            def define_schema(cls):
                return io.Schema(node_id='ApplySource', inputs=[], outputs=[io.Model.Output(), io.Clip.Output(), node_module.LoraSelectionSocket.Output()])
            @classmethod
            def execute(cls): return io.NodeOutput(model, clip, selected)
        class Consumer(io.ComfyNode):
            @classmethod
            def define_schema(cls):
                return io.Schema(node_id='ApplyConsumer', inputs=[io.Model.Input('model'), io.Clip.Input('clip')], outputs=[], is_output_node=True)
            @classmethod
            def execute(cls, model, clip):
                seen.append((model, clip)); return io.NodeOutput()
        fake = FakeChoiceGateway()
        prompt = {
            '1': {'class_type': 'ApplySource', 'inputs': {}},
            '2': {'class_type': 'TypeSafeLoraCandidate', 'inputs': {'lora_name': self.name, 'description': 'ink', 'strength_model': 1.0, 'strength_clip': 1.0, 'trigger_words': ''}},
            '3': {'class_type': 'TypeSafeLoraSelect', 'inputs': {'text': 'draw', 'candidates.candidate0': ['2', 0], 'min_confidence': 0.5, 'model': 'test', 'refresh_id': 0}},
            '4': {'class_type': 'TypeSafeLoraApply', 'inputs': {'model': ['1', 0], 'clip': ['1', 1], 'selection': ['3', 0]}},
            '5': {'class_type': 'ApplyConsumer', 'inputs': {'model': ['4', 0], 'clip': ['4', 1]}}}
        def read(*args, **kwargs):
            value = self.file.read_bytes(); loaded.append(value); return value
        server = SimpleNamespace(client_id=None, last_node_id=None, send_sync=lambda *a, **kw: None)
        executor = execution.PromptExecutor(server, cache_args={'ram': 0})
        with patch.object(Apply, 'runtime', self.runtime), patch.object(Candidate, 'runtime', self.runtime), \
                patch.object(Selector, 'runtime', self.runtime), patch.object(Selector, 'engine', pkg.DecisionEngine(fake)), \
                patch.dict(nodes.NODE_CLASS_MAPPINGS, {c.GET_SCHEMA().node_id: c for c in (Source, Consumer, Apply, Candidate, Selector)}), \
                patch.object(nodes.comfy.utils, 'load_torch_file', side_effect=read), \
                patch.object(nodes.comfy.sd, 'load_lora_for_models', side_effect=lambda m, c, weights, *s: (weights, c)):
            valid, error, _, _ = await execution.validate_prompt('valid', deepcopy(prompt), None)
            self.assertTrue(valid, error)
            for run in range(2):
                await executor.execute_async(deepcopy(prompt), str(run), execute_outputs=['5'])
                self.assertTrue(executor.success)
            self.assertEqual(len(fake.calls), 1)  # Only Apply/downstream conservatively rerun.
            self.assertEqual(len(loaded), 2)
            self.file.write_bytes(b'new weights')
            await executor.execute_async(deepcopy(prompt), 'replace', execute_outputs=['5'])
            self.assertTrue(executor.success); self.assertEqual(len(fake.calls), 2)
            self.assertEqual(seen[-1][0], b'new weights')
            # A cached custom socket source without Candidate ancestry must also be safe.
            prompt['4']['inputs']['selection'] = ['1', 2]
            await executor.execute_async(deepcopy(prompt), 'custom', execute_outputs=['5'])
            self.file.write_bytes(b'another replacement')
            await executor.execute_async(deepcopy(prompt), 'custom replaced', execute_outputs=['5'])
            self.assertTrue(executor.success); self.assertEqual(seen[-1][0], b'another replacement')
            self.file.unlink()
            before = len(seen)
            with self.assertLogs(level='ERROR'):
                await executor.execute_async(deepcopy(prompt), 'custom removed', execute_outputs=['5'])
            self.assertFalse(executor.success); self.assertEqual(len(seen), before)
            # New source instance/cache with none: even fingerprinting must do zero runtime I/O.
            selected = selection()
            del prompt['2']; del prompt['3']
            executor = execution.PromptExecutor(server, cache_args={'ram': 0})
            with patch.object(Apply, 'runtime', None):
                for run in range(2):
                    await executor.execute_async(deepcopy(prompt), f'none {run}', execute_outputs=['5'])
                    self.assertTrue(executor.success)
                    self.assertIs(seen[-1][0], model); self.assertIs(seen[-1][1], clip)
