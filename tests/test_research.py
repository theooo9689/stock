import json
from types import SimpleNamespace

import pytest

from radar.config import Settings
from radar.research import Research, ResearchResult
from radar.storage import Store


def test_strict_schema_for_all_structured_objects():
    schema = ResearchResult.model_json_schema()
    assert schema['additionalProperties'] is False
    for model in schema['$defs'].values():
        if model.get('type') == 'object':
            assert model['additionalProperties'] is False
            assert set(model['required']) == set(model['properties'])


def test_research_filters_uncited_sources_and_saves_cost(tmp_path):
    good='https://www.federalreserve.gov/confirmed'
    bad='https://invented.example.com/story'
    payload={
        'summary':'Pesquisa com fontes','news':[], 'events':[], 'risks':[], 'limitations':[],
        'theses':[{'symbol':'EME','facts':[{'fact':'Confirmado','source_url':good,'published_at':'2026-10-18'},
                                         {'fact':'Não citado','source_url':bad,'published_at':'não informado'}],
                   'valuation_context':'Cenários','fundamentals':'Fatos','technical_interpretation':'Indicadores',
                   'catalysts':[],'risks':[],'wait_condition':'Aguardar','horizon':'longo','conviction':'baixa',
                   'conviction_reason':'Dados limitados','assessments':[{'criterion':'macro','score':50,'reason':'Fonte confirmada','sources':[good]},
                                                                      {'criterion':'growth','score':100,'reason':'Sem confirmação','sources':[bad]}],
                   'missing':[]}]
    }
    class FakeResponse:
        status='completed'
        id='resp_test'
        usage=SimpleNamespace(input_tokens=100,output_tokens=100)
        output=[SimpleNamespace(type='web_search_call')]
        output_text=json.dumps(payload)
        def model_dump(self,mode=None):
            return {'output':[{'type':'web_search_call','action':{'sources':[{'url':good}]}}]}
        def model_dump_json(self,indent=None):
            return json.dumps(self.model_dump())
    class Responses:
        def create(self,**kwargs):
            assert kwargs['tool_choice']=='required'
            return FakeResponse()
    s=Settings(data_dir=tmp_path)
    store=Store(tmp_path/'state.db')
    answer=Research(s,store,SimpleNamespace(responses=Responses())).run('2026-10-18',{},['EME'],'Analyze')
    thesis=answer['result']['theses'][0]
    assert len(thesis['facts'])==1
    assert len(thesis['assessments'])==1
    assert store.cost('2026-10-18') == pytest.approx((.0102,0))
    assert list((tmp_path/'research').glob('*.json'))


def test_incomplete_research_does_not_claim_completion(tmp_path):
    class FakeResponse:
        status='incomplete'
        id='resp_incomplete'
        usage=SimpleNamespace(input_tokens=100,output_tokens=100)
        output=[]
        def model_dump_json(self,indent=None):return '{}'
    client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs:FakeResponse()))
    with pytest.raises(RuntimeError,match='não concluída'):
        Research(Settings(data_dir=tmp_path),Store(tmp_path/'state.db'),client).run('2026-10-18',{},[],'test')
