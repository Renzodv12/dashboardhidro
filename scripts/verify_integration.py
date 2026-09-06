"""Prueba real aislada: Mosquitto + Flask HTTP + simulador. Sin hardware."""
import concurrent.futures
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def wait_until(fn,timeout=15):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            result=fn()
            if result: return result
        except (OSError,ValueError): pass
        time.sleep(.3)
    raise AssertionError('Tiempo de espera agotado')


def main():
    broker=shutil.which('mosquitto') or '/opt/homebrew/opt/mosquitto/sbin/mosquitto'
    if not Path(broker).exists(): raise SystemExit('Instalar Mosquitto primero')
    with tempfile.TemporaryDirectory(prefix='hidroponia-e2e-') as directory:
        directory=Path(directory)
        mqtt_port,web_port=free_port(),free_port()
        env=dict(os.environ,DATABASE_PATH=str(directory/'test.sqlite3'),SECRET_KEY=secrets.token_hex(32),
                 MQTT_HOST='127.0.0.1',MQTT_PORT=str(mqtt_port),MQTT_USERNAME='',MQTT_PASSWORD='',
                 PORT=str(web_port),HOST='127.0.0.1',HYDRO_DEBUG='false',SIMULATION_ENABLED='true',CONTROL_DEVICE_ID='simulator-e2e')
        old=dict(os.environ)
        os.environ.update(env)
        from app import create_app
        from app.db import get_db
        from app.routes.auth import create_user
        app=create_app()
        password=secrets.token_urlsafe(20)
        with app.app_context():
            with get_db(): create_user('e2e-admin',password,'ADMIN')
        os.environ.clear(); os.environ.update(old)
        config=directory/'mosquitto.conf'
        config.write_text(f'listener {mqtt_port} 127.0.0.1\nallow_anonymous true\npersistence false\n')
        processes=[]
        log=open(directory/'processes.log','w+')
        try:
            processes.append(subprocess.Popen([broker,'-c',str(config)],stdout=log,stderr=log))
            time.sleep(.5)
            processes.append(subprocess.Popen([sys.executable,'run.py'],cwd=ROOT,env=env,stdout=log,stderr=log))
            base=f'http://127.0.0.1:{web_port}'
            opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            def raw(path,data=None,csrf=None):
                headers={}
                if data is not None:
                    data=json.dumps(data).encode();headers={'Content-Type':'application/json','X-CSRF-Token':csrf or token}
                return opener.open(urllib.request.Request(base+path,data=data,headers=headers),timeout=5)
            def api(path,data=None): return json.load(raw(path,data))
            wait_until(lambda:api('/api/health')['services']['mqtt']=='connected')
            html=raw('/login').read().decode()
            token=re.search(r'name="csrf_token" value="([^"]+)"',html).group(1)
            from urllib.parse import urlencode
            request=urllib.request.Request(base+'/login',data=urlencode(dict(username='e2e-admin',password=password,csrf_token=token)).encode())
            html=opener.open(request).read().decode()
            token=re.search(r'name="csrf-token" content="([^"]+)"',html).group(1)
            processes.append(subprocess.Popen([sys.executable,'simulator.py'],cwd=ROOT,env=env,stdout=log,stderr=log))
            wait_until(lambda:all(r['value'] is not None for r in api('/api/sensors/latest')))
            baseline=api('/api/sensors/latest')[0]['value']
            api('/api/simulation/disturbance',dict(variable='ph',delta=.8))
            high=wait_until(lambda:(rows:=api('/api/sensors/latest'))[0]['value']>6.8 and rows[0]['value'])
            assert api('/api/alerts'), 'No se generó alerta'
            api('/api/control/mode',dict(mode='automatic'))
            start=time.monotonic()
            final=wait_until(lambda:(rows:=api('/api/sensors/latest'))[0]['value']<6.25 and rows[0]['value'],timeout=60)
            elapsed=time.monotonic()-start
            assert any(e['output']<0 for e in api('/api/control/events'))
            wait_until(lambda:not api('/api/alerts'))
            csv=raw('/api/sensors/history/ph?format=csv').read()
            assert b'transport_ms' in csv and len(csv.splitlines())>5
            # Tres solicitudes simultáneas autenticadas; no es una prueba de carga sostenida.
            cookies=next(h for h in opener.handlers if isinstance(h,urllib.request.HTTPCookieProcessor)).cookiejar
            cookie='; '.join(f'{c.name}={c.value}' for c in cookies)
            def page_check(_):
                request=urllib.request.Request(base+'/dashboard',headers={'Cookie':cookie})
                started=time.monotonic()
                with urllib.request.urlopen(request,timeout=5) as response:
                    assert response.status==200
                return (time.monotonic()-started)*1000
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                timings=list(executor.map(page_check,range(3)))
            api('/api/control/emergency',{})
            assert api('/api/control/status')['mode']=='emergency'
            # Rearme manual más nivel bajo: debe impedir nuevas dosificaciones.
            api('/api/control/reset',{})
            api('/api/simulation/disturbance',dict(variable='nivel',delta=-70))
            wait_until(lambda:api('/api/sensors/latest')[5]['value']<25)
            api('/api/control/mode',dict(mode='automatic'))
            time.sleep(2)
            assert api('/api/control/status')['output']==0
            if '--browser' in sys.argv:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as playwright:
                    browser=playwright.chromium.launch(channel='chrome',headless=True)
                    context=browser.new_context()
                    page=context.new_page()
                    errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(base+'/login')
                    page.locator('input[name=username]').fill('e2e-admin')
                    page.locator('input[name=password]').fill(password)
                    page.get_by_role('button',name='Ingresar',exact=True).click()
                    page.wait_for_url('**/dashboard')
                    page.wait_for_selector('#sensor-cards article')
                    for width,height in [(1440,1000),(768,1024),(390,844)]:
                        page.set_viewport_size(dict(width=width,height=height))
                        page.wait_for_timeout(300)
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'Overflow en {width}'
                    page.set_viewport_size(dict(width=1440,height=1000))
                    for path in ['history','control','vision','settings','users','audit']:
                        page.goto(base+'/'+path)
                        page.wait_for_timeout(700)
                        assert not page.locator('#feedback.alert-danger').count(),page.locator('#feedback').inner_text()
                    page.goto(base+'/dashboard')
                    page.wait_for_selector('#sensor-cards article')
                    page.wait_for_timeout(700)
                    evidence=ROOT/'docs/evidence'
                    evidence.mkdir(exist_ok=True)
                    page.screenshot(path=str(evidence/'dashboard.png'),full_page=True)
                    assert not errors,errors
                    browser.close()
            report=dict(baseline_ph=baseline,disturbed_ph=high,corrected_ph=final,correction_seconds=round(elapsed,2),
                        parallel_request_ms=[round(t,2) for t in timings],metrics=api('/api/metrics'),
                        emergency_and_low_level='passed',scope='Simulación local MQTT y HTTP. No hardware ni disponibilidad experimental prolongada.')
            print(json.dumps(report,indent=2,ensure_ascii=False))
        except Exception:
            log.flush();log.seek(0)
            print(log.read()[-5000:],file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close()


if __name__=='__main__': main()
