import socket, subprocess, sys, threading, time
from pathlib import Path

PORT=45678
relay=Path(__file__).resolve().parents[1]/'rou_v0_relay.py'
stop=False

def server():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.bind(('127.0.0.2',PORT)); s.settimeout(0.2)
    while not stop:
        try: data,peer=s.recvfrom(65535)
        except socket.timeout: continue
        s.sendto(b'ACK:'+data, peer)
    s.close()

t=threading.Thread(target=server,daemon=True); t.start()
p=subprocess.Popen([sys.executable,str(relay),'--listen-address','127.0.0.1','--internal-source-address','127.0.0.1','--target-address','127.0.0.2','--port',str(PORT)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
time.sleep(1)
clients=[]
try:
    for payload in (b'one',b'two'):
        c=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); c.bind(('127.0.0.1',0)); c.settimeout(2)
        c.sendto(payload,('127.0.0.1',PORT))
        data,_=c.recvfrom(65535)
        assert data==b'ACK:'+payload,(payload,data)
        clients.append(c)
    print('MULTI_PEER_UDP_PASS')
finally:
    for c in clients: c.close()
    p.terminate()
    try: p.wait(timeout=2)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
    stop=True
    out=p.stdout.read() if p.stdout else ''
    print(out)
