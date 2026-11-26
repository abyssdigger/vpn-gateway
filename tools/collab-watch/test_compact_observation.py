import copy
import random
import unittest
from core import canonical,digest,Conflict
from journal import project_m,project_m_compact,JOURNAL_MARKER,SIGNAL_MARKER
from preflight_m import preflight_journal_fact,preflight_journal_fact_compact,preflight_signal,preflight_signal_compact
from compact_observation import (CompactObservation, OpaqueObservationRow, compact_observation,
                                 compact_snapshots, decode_compact, encode_compact)

actor=340153730
holder=114166706
cfg={'protocol':'vpng-collab/1','repository':'owner/repo','signal_room':37,
     'task_rooms':[34],'journal_epoch':'test-epoch',
     'roles':{'GUARD':{'actor_id':actor,'incarnation':'guard'},
              'BUILDER':{'actor_id':actor,'incarnation':'builder'}},
     'projectholder':{'actor_id':holder,'room':35,'route_to':['GUARD']},
     'command_registry':{'cycle':'test-cycle','capability_scopes':{},
                         'condition_keys':[],'utc_keys':[],'model_scopes':{}}}

def row(cid,body,author=actor): return {'id':cid,'user':{'id':author},'body':body}
def ref(room,cid):return f'issue:{room}#issuecomment-{cid}'
def event(kind,mid,sender='GUARD',recipient='BUILDER',**fields):
    return JOURNAL_MARKER+'\n```json\n'+canonical({'protocol':'vpng-collab/1','journal_epoch':cfg['journal_epoch'],'event_id':mid,'kind':kind,'room':34,'from':sender,'to':[recipient],'incarnation':cfg['roles'][sender]['incarnation'],'payload_ref':ref(34,1),**fields})+'\n```'
def signal(mid,body,cid=3,**kw):
    return SIGNAL_MARKER+'\n```json\n'+canonical({'protocol':'vpng-collab-signal/1','journal_epoch':cfg['journal_epoch'],'signal_id':mid,'event_id':'i','journal_ref':ref(34,cid),'journal_sha256':digest(body),'from':'GUARD','to':'BUILDER','incarnation':cfg['roles']['GUARD']['incarnation'],**kw})+'\n```'
def snap(rng):
    ob={'id':'o','revision':1}; op=event('OPEN','o',obligation={**ob,'kind':'work','assignee':'BUILDER','disposition_by':'GUARD'}); inp=event('INPUT','i',obligation=ob,outcome='ANSWER'); receipt=event('HANDLED','h','BUILDER','BUILDER',handled=[{'event_id':'i','ref':ref(34,3),'body_sha256':digest(inp)}]);ping=event('PING','p',ping_id='p');pong=event('PONG','q','BUILDER','GUARD',ping_id='p');sig=signal('s',inp)
    s={'34':[row(1,'payload, unicode Ж😀'+str(rng.random()),rng.choice([actor,holder,999])),row(2,op),row(3,inp),row(4,receipt),row(5,ping),row(6,pong),row(7,'unreferenced '+str(rng.random())),row(8,'<!-- vpng-collab-journal/999 -->',999)],'35':[row(20,'ordinary product input',holder),row(21,'!COLLAB STOP cycle='+cfg['command_registry']['cycle'],holder),row(22,'ignored prose',actor)],'37':[row(30,sig),row(31,'external',999)]}
    # independent variants, including valid duplicate occurrences and conflicts
    v=rng.randrange(23)
    if v==1:s['34'].append(row(9,inp))
    if v==2:s['34'].append(row(1,'different payload'))
    if v==3:s['34'].append(row(11,'<!-- vpng-collab-journal/999 -->'))
    if v==4:s['34'].append(row(9,op+'\nchanged'))
    if v==5:s['35'].append(row(22,'conflicting ignored prose',actor))
    if v==6:s['35'].append(row(20,'conflicting holder',holder))
    if v==7:s['37'].append(row(32,sig))
    if v==8:s['37'].append(row(32,signal('s',inp,journal_sha256='0'*64)))
    if v==9:s['37'].append(row(30,'malformed signal'))
    if v==10:s['37'].append(row(30,sig,999))
    if v==11:s['37'].clear()
    if v==12:s['34'].append(row(12,event('DISPOSITION','close',obligation=ob,disposition='CLOSED',closure_ref=ref(34,7))))
    if v==13:s['34']=[r for r in s['34'] if r['id']!=1]
    if v==14:s['34'].append(row(1,s['34'][0]['body'],s['34'][0]['user']['id']))
    if v==15:s['34'].append(row(13,event('INPUT','future',outcome='ANSWER',payload_ref=ref(34,14))));s['34'].append(row(14,'forward payload',999))
    if v==16:s['35'].append(row(23,'!COLLAB STOP cycle=unknown',holder))
    if v==17:s['34'].append(row(13,event('HANDLED','hold','GUARD','GUARD',handled=[{'event_id':'holder:20','ref':ref(35,20),'body_sha256':digest('ordinary product input')}])) )
    if v==18:s['34'].append(row(13,event('BLOCK','b','BUILDER','BUILDER',obligation=ob,wait_for_event_id='missing')))
    if v==19:s['34'].append(row(13,event('BLOCK','b','BUILDER','BUILDER',obligation=ob,wait_for_event_id='h')))
    if v==20:s['34'].append(row(1,op))
    if v==21:s['35'].append(row(20,'different actor',actor))
    if v==22:s['34'].append(row(2,'ordinary duplicate of journal identity'))
    for rows in s.values():rng.shuffle(rows)
    return s

def outcome(fn):
    try:return ('PASS',canonical(fn()))
    except Conflict as exc:return ('CONFLICT',str(exc))

class CompactObservationTests(unittest.TestCase):
    def test_seeded_raw_compact_equivalence(self):
        rng=random.Random(20261126)
        valid=conflicts=0
        for i in range(3000):
            s=snap(rng)
            comp=compact_observation(cfg,s)
            wire=encode_compact(cfg,comp)
            decoded=decode_compact(cfg,wire,digest(wire))
            a=outcome(lambda:project_m(cfg,s))
            b=outcome(lambda:project_m_compact(cfg,decoded))
            self.assertEqual(a,b,i)
            if a[0]=='CONFLICT':
                conflicts+=1
                continue
            valid+=1
            _,state=project_m(cfg,s)
            self.assertEqual(outcome(lambda:project_m(cfg,s,state)),
                             outcome(lambda:project_m_compact(cfg,decoded,state)),i)
            for delete in (False,True):
                changed=copy.deepcopy(s)
                if delete:
                    changed['34']=[r for r in changed['34'] if r['id']!=1]
                else:
                    next(r for r in changed['34'] if r['id']==1)['body']+=' drift'
                ct=compact_observation(cfg,changed)
                a=outcome(lambda:project_m(cfg,changed,state))
                b=outcome(lambda:project_m_compact(cfg,ct,state))
                self.assertEqual(a,b,i)
                self.assertEqual(a[0],'CONFLICT',i)
            body=event('INPUT','new',outcome='PARTIAL',payload_ref=ref(34,7))
            self.assertEqual(outcome(lambda:preflight_journal_fact(cfg,s,actor,body,state)),
                             outcome(lambda:preflight_journal_fact_compact(cfg,decoded,actor,body,state)),i)
            for sid in ('new-signal','s'):
                original=next(r for r in s['34'] if r['id']==3)['body']
                body=signal(sid,original)
                self.assertEqual(outcome(lambda:preflight_signal(cfg,s,actor,body,state)),
                                 outcome(lambda:preflight_signal_compact(cfg,decoded,actor,body,state)),(i,sid))
        self.assertGreater(valid,1000)
        self.assertGreater(conflicts,1000)

    def test_typed_wire_gates(self):
        s=snap(random.Random(1));c=compact_observation(cfg,s);wire=encode_compact(cfg,c)
        def reject(fn):
            with self.assertRaises(Conflict):fn()
        reject(lambda:decode_compact(cfg,wire,'0'*64))
        reject(lambda:decode_compact(cfg,wire+'\n',digest(wire+'\n')))
        reject(lambda:project_m(cfg,compact_snapshots(cfg,c)))
        reject(lambda:preflight_journal_fact(cfg,compact_snapshots(cfg,c),actor,event('INPUT','new',outcome='ANSWER')))
        reject(lambda:preflight_signal(cfg,compact_snapshots(cfg,c),actor,signal('s','bad')))
        for room,kind,author in [(37,'task_payload',actor),(35,'holder_ignored',holder),(34,'holder_ignored',actor),(35,'task_payload',actor),(37,'holder_ignored',999)]:
            rr=dict(c.rooms);rr[str(room)]=rr[str(room)]+(OpaqueObservationRow(kind,999,author,'a'*64),)
            reject(lambda:project_m_compact(cfg,CompactObservation(c.config_hash,rr)))
        for cid,author,h in [(0,actor,'a'*64),(99,0,'a'*64),(99,actor,'a'*63),(99,actor,'A'*64)]:
            rr=dict(c.rooms);rr['34']=rr['34']+(OpaqueObservationRow('task_payload',cid,author,h),)
            reject(lambda:project_m_compact(cfg,CompactObservation(c.config_hash,rr)))
        rr=dict(c.rooms);opaque=next(x for x in rr['34'] if isinstance(x,OpaqueObservationRow))
        orig=next(x for x in s['34'] if x['id']==opaque.comment_id)
        rr['34']=rr['34']+(orig,)
        reject(lambda:project_m_compact(cfg,CompactObservation(c.config_hash,rr)))
        import json
        original=json.loads(wire)
        for field,value in [('protocol','bad'),('config_hash','a'*64),('rooms',{})]:
            obj=copy.deepcopy(original);obj[field]=value;data=canonical(obj)
            reject(lambda:decode_compact(cfg,data,digest(data)))
        for invalid in (['bad',1,actor,'x'],['raw',1,actor],['raw',0,actor,'x']):
            obj=copy.deepcopy(original);obj['rooms']['34'].append(invalid);data=canonical(obj)
            reject(lambda:decode_compact(cfg,data,digest(data)))

    def test_wire_reduces_large_ordinary_prose(self):
        s=snap(random.Random(1))
        s['34'].append(row(100,'large ordinary payload '+('abc Ж '*10000)))
        compact=compact_observation(cfg,s)
        self.assertLess(len(encode_compact(cfg,compact).encode('utf-8')),
                        len(canonical(s).encode('utf-8'))//4)
        self.assertEqual(outcome(lambda:project_m(cfg,s)),
                         outcome(lambda:project_m_compact(cfg,compact)))


if __name__ == '__main__':
    unittest.main()
