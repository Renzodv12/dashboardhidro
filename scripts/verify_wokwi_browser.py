"""Ejecuta el circuito en una sesión temporal de Wokwi web, sin guardar el proyecto.
Requiere playwright y Chrome, además de scripts/prepare_wokwi.py previo.
Solo se cargan el firmware simulado, diagrama y configuración pública generada.
"""
from pathlib import Path
import re
import time
import sqlite3
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'data/wokwi'
firmware=(folder/'sketch.ino').read_text()
header=(folder/'hidroponia_config.h').read_text()
firmware=re.sub(r'#if __has_include\("hidroponia_config.h"\).*?#endif',header,firmware,flags=re.S)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    try:
        page.goto('https://wokwi.com/projects/new/esp32',wait_until='domcontentloaded',timeout=60000)
        page.wait_for_function('window.monaco && monaco.editor.getModels().some(m=>m.uri.toString()==="vfs:sketch.ino")')
        page.evaluate('(text)=>monaco.editor.getModels().find(m=>m.uri.toString()==="vfs:sketch.ino").setValue(text)',firmware)
        page.get_by_text('diagram.json',exact=True).click()
        page.wait_for_function('monaco.editor.getModels().some(m=>m.uri.toString()==="vfs:diagram.json")')
        page.evaluate('(text)=>monaco.editor.getModels().find(m=>m.uri.toString()==="vfs:diagram.json").setValue(text)',(folder/'diagram.json').read_text())
        for library in ['PubSubClient','ArduinoJson']:
            page.get_by_text('Library Manager',exact=True).click()
            page.get_by_role('button',name='Add a new library',exact=True).click()
            page.locator('input[type=text]').fill(library)
            page.get_by_text(library,exact=True).last.click(timeout=20000)
            page.wait_for_timeout(500)
        page.get_by_role('button',name='Start the simulation',exact=True).click()
        since=datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        deadline=time.monotonic()+180
        passed=False
        last_update=0
        while time.monotonic()<deadline:
            page.wait_for_timeout(1000)
            with sqlite3.connect(f'{(ROOT/"data/hidroponia-wokwi.sqlite3").as_uri()}?mode=ro',uri=True) as db:
                rows=db.execute('SELECT s.variable,r.value FROM sensor_readings r JOIN sensor_types s ON s.id=r.sensor_type_id WHERE r.received_at>=? ORDER BY r.id DESC',(since,)).fetchall()
            latest={}
            for variable,value in rows:
                latest.setdefault(variable,value)
            if len(latest)==6:
                assert latest['nivel']>25, 'El circuito no entrega nivel suficiente: revisar pines'
                print('APROBADO: ESP32 virtual Wokwi → broker público → SQLite: '+str(latest),flush=True)
                passed=True
                break
            if time.monotonic()-last_update>15:
                print('Wokwi: '+page.locator('body').inner_text()[-450:],flush=True)
                last_update=time.monotonic()
        page.screenshot(path=str(folder/'wokwi-web.png'))
        if not passed:
            raise RuntimeError('Sin seis lecturas del ESP32 virtual en 180 s; revisar cola, Serial y red')
    finally:
        browser.close()
