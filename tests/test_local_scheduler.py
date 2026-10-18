from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from radar.config import Settings
from radar.pipeline import run_lock, RunInProgress
from radar.scheduler import tick
from radar.storage import Store


class ClockSettings(Settings):
    at: datetime

    def now(self):
        return self.at


def settings(tmp_path, clock):
    return ClockSettings(at=datetime.fromisoformat('2026-10-18T'+clock).replace(tzinfo=ZoneInfo('America/Sao_Paulo')),
                         data_dir=tmp_path, reports_dir=tmp_path/'reports')


def test_morning_start_does_not_spend_or_send(tmp_path):
    def fail(*a, **kw):raise AssertionError('nao deveria pesquisar')
    assert tick(settings(tmp_path,'08:00:00'),fail)=='aguardando_horario'


def test_prepare_once_then_wait_for_delivery(tmp_path):
    s=settings(tmp_path,'19:30:00'); calls=[]
    def runner(config,**kwargs):
        calls.append(kwargs)
        Store(tmp_path/'radar.sqlite3').save_report('2026-10-18',{'status':'parcial','generated_at':s.now().isoformat()})
    assert tick(s,runner)=='pesquisado'
    assert tick(s,runner)=='pesquisa_pronta'
    assert len(calls)==1
    assert calls[0]['refresh'] and not calls[0]['send']


def test_notebook_start_after_deadline_delivers_same_day(tmp_path):
    calls=[]
    assert tick(settings(tmp_path,'22:45:00'),lambda *a,**kw:calls.append(kw))=='entrega_processada'
    assert calls==[{'send':True,'refresh':False,'edition':'scheduled'}]


def test_old_manual_report_is_refreshed_at_prepare_time(tmp_path):
    Store(tmp_path/'radar.sqlite3').save_report('2026-10-18',{'status':'parcial','generated_at':'2026-10-18T14:00:00-03:00'})
    calls=[]
    tick(settings(tmp_path,'20:45:00'),lambda *a,**kw:calls.append(kw))
    assert calls[0]['refresh']


def test_completed_scheduled_edition_does_not_repeat_on_login(tmp_path):
    st=Store(tmp_path/'radar.sqlite3')
    st.claim_delivery('2026-10-18','scheduled-concluido');st.sent('2026-10-18','scheduled-concluido',0)
    def fail(*a,**kw):raise AssertionError('nao deveria reenviar')
    assert tick(settings(tmp_path,'23:00:00'),fail)=='ja_entregue'


def test_ambiguous_delivery_not_retried_automatically(tmp_path):
    Store(tmp_path/'radar.sqlite3').claim_delivery('2026-10-18','scheduled-resumo-1')
    def fail(*a,**kw):raise AssertionError('nao deveria reenviar')
    assert tick(settings(tmp_path,'22:00:00'),fail)=='entrega_incerta'


def test_busy_manual_execution_is_not_a_network_failure(tmp_path):
    def busy(*a,**kw):raise RunInProgress('ocupado')
    assert tick(settings(tmp_path,'20:30:00'),busy)=='em_execucao'


def hold_lock(path, ready, release):
    with run_lock(path):
        ready.set()
        release.wait(15)


def test_file_lock_works_across_processes_and_releases(tmp_path):
    ctx=get_context('spawn');ready=ctx.Event();release=ctx.Event()
    path=tmp_path/'run.lock'
    p=ctx.Process(target=hold_lock,args=(path,ready,release));p.start()
    try:
        assert ready.wait(10)
        with pytest.raises(RunInProgress):
            with run_lock(path):pass
    finally:
        release.set();p.join(10)
        if p.is_alive():p.terminate();p.join(5)
    assert p.exitcode==0
    with run_lock(path):pass
