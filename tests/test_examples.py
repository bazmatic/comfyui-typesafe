"""Execute exported visual graph topology with real decisions and lightweight heavy-node fixtures."""
import asyncio
from copy import deepcopy
import json
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_guard import pkg, Guard, FakeGateway, gateway, response as noul_response
import test_guard
from test_candidate import Candidate, FakeLoraRuntime
from test_selector import Selector, FakeChoiceGateway, response
from test_apply import Apply
from comfy_extras.nodes_string import StringConcatenate
from comfy_extras.nodes_primitive import StringMultiline
from comfy_extras.nodes_preview_any import PreviewAny

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'
WIDGETS = {
 'CheckpointLoaderSimple': ['ckpt_name'], 'CLIPTextEncode': ['text'],
 'EmptyLatentImage': ['width','height','batch_size'],
 'KSampler': ['seed',None,'steps','cfg','sampler_name','scheduler','denoise'],
 'VAEDecode': [], 'SaveImage': ['filename_prefix'], 'PreviewAny': [],
 'TypeSafeTextGuard': ['text','condition','stop_threshold','model','refresh_id'],
 'PrimitiveStringMultiline': ['value'],
 'TypeSafeLoraCandidate': ['lora_name','description','strength_model','strength_clip','trigger_words'],
 'TypeSafeLoraSelect': ['text','min_confidence','model','refresh_id'],
 'TypeSafeLoraApply': [], 'StringConcatenate': ['string_a','string_b','delimiter']}


def api_prompt(filename):
    graph=json.loads((EXAMPLES / filename).read_text())
    links={link[0]:link for link in graph['links']}
    prompt={}
    for node in graph['nodes']:
        fields=WIDGETS[node['type']]
        values=node.get('widgets_values', [])
        inputs={key:value for key,value in zip(fields, values) if key}
        for slot in node.get('inputs', []):
            if slot.get('link') is not None:
                link=links[slot['link']]
                inputs[slot['name']]=[str(link[1]),link[2]]
        prompt[str(node['id'])]={'class_type':node['type'],'inputs':inputs}
    return graph,prompt


class ExampleTests(unittest.IsolatedAsyncioTestCase):
    async def test_exported_graphs_pass_reject_selected_none_and_diagnostics(self):
        import execution
        import nodes
        model,clip=object(),object()
        observed=[]
        # Preserve real core input/output schemas and exported links; replace only expensive execution.
        def stub(cls,fn):
            return type('Fixture'+cls.__name__,(cls,),{cls.FUNCTION:staticmethod(fn)})
        def encode(clip,text): observed.append(('encode',text,clip)); return (text,)
        def sample(**kw): observed.append(('sample',kw['model'])); return ('latent',)
        fixture={
            'CheckpointLoaderSimple':stub(nodes.CheckpointLoaderSimple,lambda ckpt_name:(model,clip,'vae')),
            'CLIPTextEncode':stub(nodes.CLIPTextEncode,encode),
            'EmptyLatentImage':stub(nodes.EmptyLatentImage,lambda **kw:('latent',)),
            'KSampler':stub(nodes.KSampler,sample),
            'VAEDecode':stub(nodes.VAEDecode,lambda **kw:('image',)),
            'SaveImage':stub(nodes.SaveImage,lambda **kw:{}),
            'PreviewAny':PreviewAny,'PrimitiveStringMultiline':StringMultiline,'StringConcatenate':StringConcatenate,
            'TypeSafeTextGuard':Guard,'TypeSafeLoraCandidate':Candidate,'TypeSafeLoraSelect':Selector,'TypeSafeLoraApply':Apply}
        fake=FakeGateway(); choice=FakeChoiceGateway()
        runtime=FakeLoraRuntime(('CHOOSE_INK_LORA.safetensors','CHOOSE_PAINT_LORA.safetensors'))
        server=SimpleNamespace(client_id=None,last_node_id=None,send_sync=lambda *a,**kw:None)
        with patch.dict(nodes.NODE_CLASS_MAPPINGS,fixture),patch.object(Guard,'engine',pkg.DecisionEngine(fake)), \
                patch.object(Selector,'engine',pkg.DecisionEngine(choice)),patch.object(Selector,'runtime',runtime), \
                patch.object(Candidate,'runtime',runtime),patch.object(Apply,'runtime',runtime):
            for cls in (Guard,Candidate,Selector,Apply,StringMultiline,StringConcatenate): cls.GET_SCHEMA()
            for filename in ('guard-before-sampling.json','select-and-apply-lora.json'):
                graph,prompt=api_prompt(filename)
                # Check visual links agree with target slots and declared source types.
                by_id={n['id']:n for n in graph['nodes']}
                for lid,src,out,dst,inp,typ in graph['links']:
                    self.assertEqual(by_id[dst]['inputs'][inp]['link'],lid)
                    self.assertIn(lid,by_id[src]['outputs'][out]['links'])
                    self.assertEqual(by_id[src]['outputs'][out]['type'],typ)
                executor=execution.PromptExecutor(server,cache_args={'ram':0})
                outputs=[key for key,node in prompt.items() if node['class_type'] in ('SaveImage','PreviewAny')]
                await executor.execute_async(deepcopy(prompt),filename,execute_outputs=outputs)
                self.assertTrue(executor.success)
                self.assertTrue(any(v[0]=='sample' for v in observed))
                details_id, probability_id = ('9', '10') if 'guard' in filename else ('14', '15')
                details = json.loads(executor.history_result['outputs'][details_id]['text'][0])
                self.assertIn('metadata', details)
                self.assertTrue(executor.history_result['outputs'][probability_id]['text'][0])
                if 'guard' in filename:
                    self.assertIn(('encode',prompt['8']['inputs']['text'],clip),observed)
                    count=sum(v[0]=='sample' for v in observed)
                    fake.value=0.9;prompt['8']['inputs']['refresh_id']=1
                    with self.assertLogs(level='ERROR'):
                        await executor.execute_async(deepcopy(prompt),'reject',execute_outputs=outputs)
                    self.assertFalse(executor.success)
                    self.assertEqual(sum(v[0]=='sample' for v in observed),count)
                    # Positive text encoding cannot run after rejected guard.
                    self.assertEqual(sum(v[:2]==('encode',prompt['8']['inputs']['text']) for v in observed),1)
                else:
                    self.assertEqual(runtime.loads[-1],(model,clip,'CHOOSE_INK_LORA.safetensors',0.8,0.7))
                    self.assertIn(('sample',runtime.applied[0]),observed)
                    self.assertIn(('encode','An ink drawing of a mountain lake. INK',runtime.applied[1]),observed)
                    choice.payload=response('none',{'candidate_0':0.05,'candidate_1':0.05,'none':0.9})
                    prompt['11']['inputs']['refresh_id']=1
                    count=len(runtime.loads)
                    await executor.execute_async(deepcopy(prompt),'none',execute_outputs=outputs)
                    self.assertTrue(executor.success);self.assertEqual(len(runtime.loads),count)
                    self.assertEqual(observed[-1],('sample',model))
                    self.assertIn(('encode','An ink drawing of a mountain lake. ',clip),observed)


class InterruptTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_guard.TransportTests.asyncSetUp
    asyncTearDown=test_guard.TransportTests.asyncTearDown

    async def test_host_interrupt_waits_for_pending_http_then_blocks_downstream(self):
        import execution
        import nodes
        from comfy_api.latest import io
        seen=[]
        class Consumer(io.ComfyNode):
            @classmethod
            def define_schema(cls): return io.Schema(node_id='InterruptConsumer',inputs=[io.String.Input('text')],outputs=[],is_output_node=True)
            @classmethod
            def execute(cls,text): seen.append(text);return io.NodeOutput()
        Consumer.GET_SCHEMA();Guard.GET_SCHEMA()
        prompt={'1':{'class_type':'TypeSafeTextGuard','inputs':{'text':'draw','condition':'failed?','stop_threshold':0.5,'model':'test','refresh_id':0}},'2':{'class_type':'InterruptConsumer','inputs':{'text':['1',0]}}}
        server=SimpleNamespace(client_id=None,last_node_id=None,send_sync=lambda *a,**kw:None)
        self.block=True
        with patch.dict(nodes.NODE_CLASS_MAPPINGS,{'TypeSafeTextGuard':Guard,'InterruptConsumer':Consumer}),patch.object(Guard,'engine',pkg.DecisionEngine(gateway.TypeSafeHttpGateway())):
            for release_http in (True,False):
                executor=execution.PromptExecutor(server,cache_args={'ram':0})
                self.entered.clear();self.release.clear()
                from aiohttp import web
                self.responses = [web.json_response(noul_response())]
                task=asyncio.create_task(executor.execute_async(deepcopy(prompt),str(release_http),execute_outputs=['2']))
                try:
                    await asyncio.wait_for(self.entered.wait(),2)
                    started=time.monotonic();nodes.interrupt_processing(True)
                    await asyncio.sleep(0.15)
                    self.assertFalse(task.done(),'Host unexpectedly cancelled the pending HTTP evaluation')
                    if release_http: self.release.set()
                    with self.assertLogs(level='INFO'):
                        await asyncio.wait_for(task,3)
                    elapsed=time.monotonic()-started
                    self.assertFalse(executor.success);self.assertEqual(seen,[])
                    events=[event for event,_ in executor.status_messages]
                    self.assertIn('execution_interrupted' if release_http else 'execution_error',events)
                    if not release_http:self.assertGreater(elapsed,0.7)
                    print(f'Host interrupt fixture: release_http={release_http}, elapsed_after_interrupt={elapsed:.3f}s, events={events}')
                finally:
                    self.release.set();nodes.interrupt_processing(False)
                    if not task.done(): task.cancel()
                    await asyncio.gather(task,return_exceptions=True)
