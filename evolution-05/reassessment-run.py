import asyncio, hashlib, json, os, secrets, shutil, subprocess, sys, tempfile, time
from pathlib import Path

repo = Path.cwd()
assert '\nGO — Codex independent Chase' in (repo/'evolution-05/reassessment-flight-card.md').read_text()
root=Path(tempfile.mkdtemp(prefix='e5-native-'))
print(root,flush=True)
source=repo/'evolution-05/sortie-05'
for f in ('pin.py','tool-pins.json','issuer.py','server.py','scopes.py'):
    shutil.copyfile(source/f,root/f)
notes=root/'notes'
notes.mkdir()
(notes/'fixture.md').write_text('Synthetic E5 read fixture.\n')
def snapshot():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in notes.iterdir()}
before=snapshot()
os.environ['E5_TEST_SIGNING_KEY']=secrets.token_hex(32)
sys.path.insert(0,str(root))
from issuer import issue_token
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
import importlib.metadata
pin = subprocess.run([sys.executable,'-B','pin.py'],cwd=root,capture_output=True,text=True,check=True)
env={k:os.environ[k] for k in ('PATH','E5_TEST_SIGNING_KEY')}
async def exercise():
    request_token=issue_token(sub='synthetic-e5-reader',scope='notes:read')
    async with create_mcp_http_client(headers={'Authorization':f'Bearer {request_token}'}) as client:
        async with streamable_http_client('http://127.0.0.1:8000/mcp',http_client=client) as streams:
            async with ClientSession(streams[0],streams[1]) as session:
                await session.initialize()
                read=await session.call_tool('read_note',{'name':'fixture'})
                read_ok=not read.is_error and any(getattr(i,'text',None)=='Synthetic E5 read fixture.\n' for i in read.content)
                try:
                    write=await session.call_tool('write_note',{'name':'blocked','text':'synthetic'})
                    code=getattr(write,'is_error',False)
                except Exception as exc:
                    code=type(exc).__name__
                return read_ok,code
with (root/'runtime.txt').open('w') as logs:
    child=subprocess.Popen([sys.executable,'-B','server.py'],cwd=root,env=env,stdout=logs,stderr=logs)
    try:
        for _ in range(100):
            if 'Uvicorn running' in (root/'runtime.txt').read_text():
                break
            if child.poll() is not None:
                raise RuntimeError('server did not start')
            time.sleep(.1)
        else:
            raise RuntimeError('server startup timed out')
        read_ok,write_result=asyncio.run(exercise())
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
after=snapshot()
raw=(root/'server.log').read_text() if (root/'server.log').exists() else ''
events=[dict((key,row[key]) for key in ('event','tool','subject','reason','required_scope','validated_scopes') if key in row)
        for row in map(json.loads,raw.splitlines())]
result=dict(sdk=importlib.metadata.version('mcp'),pin=pin.stdout.strip(),read_ok=read_ok,
            write_result=write_result,before=before,after=after,events=events)
rendered=json.dumps(result,indent=2)
assert os.environ['E5_TEST_SIGNING_KEY'] not in rendered
(root/'observed.json').write_text(rendered+'\n')
print(rendered)
assert read_ok and write_result and before==after
assert any(row.get('event')=='scope_denied' and row.get('reason')=='insufficient_scope' and
           row.get('subject')=='synthetic-e5-reader' and row.get('tool')=='write_note' for row in events)
