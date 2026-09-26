"""Candidate domain, filesystem adapter, and real prompt-executor contracts."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import importlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_guard import pkg, domain, errors, gateway
from comfy_api.latest import io
import folder_paths

runtime_module = importlib.import_module(pkg.__name__ + '.lora_runtime')
node_module = importlib.import_module(pkg.__name__ + '.nodes')
Candidate = pkg.TypeSafeLoraCandidate


class FakeLoraRuntime:
    def __init__(self, names=('styles/ink.safetensors',)):
        self.names = names
        self.checked = []
        self.loads = []
        self.applied = (object(), object())

    def list_names(self):
        return self.names

    def validate_file(self, name):
        self.fingerprint(name)

    def fingerprint(self, name):
        self.checked.append(name)
        if not self.names:
            raise errors.ConfigurationError('No LoRAs are installed.')
        domain.installed_name(name)
        if name not in self.names:
            raise errors.ConfigurationError('Choose an exact installed LoRA name.')
        return runtime_module.LoraFingerprint('/fake/' + name, 1, 2, 3, 4)

    def apply(self, model, clip, candidate):
        domain.validate_candidate(candidate)
        try:
            self.validate_file(candidate.name)
        except errors.ConfigurationError as exc:
            raise errors.LoraApplicationError("The accepted LoRA is unavailable.") from exc
        self.loads.append((model, clip, candidate.name, candidate.strength_model, candidate.strength_clip))
        return (model, clip) if candidate.strength_model == candidate.strength_clip == 0 else self.applied


class CandidateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeLoraRuntime()
        self.runtime_patch = patch.object(Candidate, 'runtime', self.fake)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    async def test_registration_and_metadata_only_execution(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': ''}), \
                patch.object(gateway.TypeSafeHttpGateway, 'evaluate', side_effect=AssertionError('inference')):
            extension = await pkg.comfy_entrypoint()
            self.assertIn(Candidate, await extension.get_node_list())
            Candidate.runtime = self.fake
            triggers = '  INK,\r\nverbatim 🌿 '
            result = Candidate.execute('styles/ink.safetensors', '  An ink style ', -100, 100, triggers)
        record = result.result[0]
        self.assertEqual(record, domain.LoraCandidate('styles/ink.safetensors', '  An ink style ', -100, 100, triggers))
        with self.assertRaises(FrozenInstanceError):
            record.name = 'changed'
        self.assertEqual(self.fake.checked, ['styles/ink.safetensors'])
        self.assertEqual(Candidate.execute('styles/ink.safetensors', 'ink').result[0].strength_model, 1.0)

    def test_invalid_domain_records_and_execution(self):
        base = dict(lora_name='styles/ink.safetensors', description='ink')
        invalid = [{'description': value} for value in ('', ' \n', None, 3)]
        invalid += [{'trigger_words': value} for value in (None, [], 1)]
        invalid += [{key: value} for key in ('strength_model', 'strength_clip')
                    for value in (True, None, '1', -101, 101, 10**400, float('nan'), float('inf'), -float('inf'))]
        invalid += [{'lora_name': value} for value in ('missing.safetensors', '/tmp/a.safetensors',
                    'C:\\a.safetensors', '../a.safetensors', 'styles/../a.safetensors', '', 'No LoRAs installed')]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(errors.ConfigurationError):
                Candidate.execute(**(base | change))
        for strength in (-100, 0, 100):
            self.assertEqual(Candidate.execute(**base, strength_model=strength).result[0].strength_model, strength)

    def test_schema_and_empty_library(self):
        schema = Candidate.GET_SCHEMA()
        self.assertEqual(schema.node_id, 'TypeSafeLoraCandidate')
        self.assertEqual(schema.category, 'TypeSafe')
        inputs = Candidate.INPUT_TYPES()['required']
        self.assertEqual(inputs['lora_name'][1]['options'], ['styles/ink.safetensors'])
        self.assertEqual(Candidate.RETURN_TYPES, ['TYPESAFE_LORA_CANDIDATE'])
        for name in ('strength_model', 'strength_clip'):
            self.assertEqual({k: inputs[name][1][k] for k in ('default', 'min', 'max')},
                             {'default': 1.0, 'min': -100, 'max': 100})
        self.fake.names = ()
        self.assertEqual(Candidate.INPUT_TYPES()['required']['lora_name'][1]['options'], [])
        self.assertIn('No LoRAs', Candidate.validate_inputs(''))
        with self.assertRaises(errors.ConfigurationError):
            Candidate.execute('placeholder', 'ink')


class FilesystemFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / 'styles' / 'ink.safetensors'
        self.file.parent.mkdir()
        self.file.write_bytes(b'metadata only, not a valid weight file')
        self.names_patch = patch.dict(folder_paths.folder_names_and_paths,
                                     {'loras': ([str(self.root)], {'.safetensors'})})
        self.names_patch.start()
        self.addCleanup(self.names_patch.stop)
        self.cache_patch = patch.dict(folder_paths.filename_list_cache, {}, clear=True)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.runtime = runtime_module.ComfyLoraRuntime()
        self.name = 'styles/ink.safetensors'


class FilesystemTests(FilesystemFixture, unittest.TestCase):
    def test_installed_names_and_metadata_identity(self):
        self.assertEqual(self.runtime.list_names(), (self.name,))
        before = self.runtime.fingerprint(self.name)
        self.runtime.validate_file(self.name)
        self.assertEqual(before.resolved_path, str(self.file.resolve()))
        self.assertEqual(before.size, self.file.stat().st_size)
        self.assertEqual(before.mtime_ns, self.file.stat().st_mtime_ns)
        # Same-size in-place rewrites with restored mtime intentionally evade this metadata fingerprint.
        stat = self.file.stat()
        self.file.write_bytes(b'x' * stat.st_size)
        os.utime(self.file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(self.runtime.fingerprint(self.name), before)
        replacement = self.root / 'replacement'
        replacement.write_bytes(b'y' * stat.st_size)
        os.utime(replacement, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        replacement.replace(self.file)
        self.assertNotEqual(self.runtime.fingerprint(self.name), before)

    def test_stale_library_and_sanitized_folder_errors(self):
        self.runtime.list_names()
        for name in ('/tmp/a.safetensors', '../styles/ink.safetensors', 'other.safetensors'):
            with self.assertRaises(errors.ConfigurationError):
                self.runtime.validate_file(name)
        self.file.unlink()
        with self.assertRaises(errors.ConfigurationError):
            self.runtime.fingerprint(self.name)
        self.file.parent.rmdir()
        with self.assertRaises(errors.ConfigurationError) as caught:
            self.runtime.validate_file(self.name)
        self.assertNotIn(str(self.root), str(caught.exception))


class CandidateHostTests(FilesystemFixture, unittest.IsolatedAsyncioTestCase):
    async def test_host_validation_and_file_cache(self):
        import execution
        import nodes
        seen = []
        class Consumer(io.ComfyNode):
            @classmethod
            def define_schema(cls):
                return io.Schema(node_id='TypeSafeCandidateTestConsumer',
                                 inputs=[node_module.LoraCandidateSocket.Input('candidate')],
                                 outputs=[], is_output_node=True)
            @classmethod
            def execute(cls, candidate):
                seen.append(candidate)
                return io.NodeOutput()
        prompt = {'1': {'class_type': 'TypeSafeLoraCandidate', 'inputs': {
            'lora_name': self.name, 'description': 'ink', 'strength_model': 1.0,
            'strength_clip': 1.0, 'trigger_words': ''}},
            '2': {'class_type': 'TypeSafeCandidateTestConsumer', 'inputs': {'candidate': ['1', 0]}}}
        server = SimpleNamespace(client_id=None, last_node_id=None, send_sync=lambda *a, **kw: None)
        executor = execution.PromptExecutor(server, cache_args={'ram': 0})
        with patch.object(Candidate, 'runtime', self.runtime), patch.dict(nodes.NODE_CLASS_MAPPINGS, {
                'TypeSafeLoraCandidate': Candidate, 'TypeSafeCandidateTestConsumer': Consumer}):
            Candidate.GET_SCHEMA(); Consumer.GET_SCHEMA()
            valid, error, _, _ = await execution.validate_prompt('valid', deepcopy(prompt), None)
            self.assertTrue(valid, error)
            for run in range(2):
                await executor.execute_async(deepcopy(prompt), str(run), execute_outputs=['2'])
                self.assertTrue(executor.success)
            self.assertEqual(len(seen), 1)
            for key, value in [('description', 'painterly'), ('strength_model', 0), ('trigger_words', 'paint')]:
                prompt['1']['inputs'][key] = value
                await executor.execute_async(deepcopy(prompt), key, execute_outputs=['2'])
                self.assertTrue(executor.success)
            self.assertEqual(len(seen), 4)
            self.file.write_bytes(b'changed weight metadata')
            await executor.execute_async(deepcopy(prompt), 'replacement', execute_outputs=['2'])
            self.assertTrue(executor.success)
            self.assertEqual(len(seen), 5)
            self.file.unlink()
            with self.assertLogs(level='WARNING'):
                await executor.execute_async(deepcopy(prompt), 'removal', execute_outputs=['2'])
            self.assertFalse(executor.success)
            self.assertEqual(len(seen), 5)
            with self.assertLogs(level='ERROR'):
                valid, _, _, details = await execution.validate_prompt('empty', deepcopy(prompt), None)
            self.assertFalse(valid)
            self.assertIn('No LoRAs are installed', str(details))

    async def test_host_rejects_numeric_widget_overflow(self):
        import execution
        import nodes
        prompt = {'1': {'class_type': 'TypeSafeLoraCandidate', 'inputs': {
            'lora_name': self.name, 'description': 'ink', 'strength_model': 101,
            'strength_clip': 1.0, 'trigger_words': ''}}}
        with patch.object(Candidate, 'runtime', self.runtime), patch.dict(nodes.NODE_CLASS_MAPPINGS, {'TypeSafeLoraCandidate': Candidate}):
            Candidate.GET_SCHEMA()
            valid, errors_, _ = await execution.validate_inputs('invalid', prompt, '1', {})
            self.assertFalse(valid)
            self.assertIn('value_bigger_than_max', str(errors_))
