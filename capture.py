"""Run a spark-ui-labs lab on the local cluster and capture its REAL Spark UI.

  python3 capture.py <labs_dir>/epNN_x.py out/epNN/ui [--shots jobs,stages,stage:3,sql:0,executors,storage,env,timeline]
                    [--find "Shuffle Read Size / Records|Spill (Disk)"]   # -> boxes.json, pixel boxes for highlights

Writes to the output folder:
  metrics.json  jobs, stages (+ min/25/50/75/max task metrics per stage), executors, storage, sql
  shot_<name>.png  1600x1000 screenshots of the requested UI pages (headless Chromium)
  boxes.json    {shot: {text: {cell:[x,y,w,h], row:[x,y,w,h]}}} in screenshot pixels, for ui_shot()+spotlight()
  console.txt   everything the lab printed
Numbers in narration and on-screen text must come from metrics.json, never invented.
Needs the cluster from start_cluster.sh running. One lab at a time (they share 4 cores).
"""
import sys, os, json, time, subprocess, urllib.request, asyncio

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())

SCALE = 1.25
PAGES = {'jobs': '/jobs/', 'stages': '/stages/', 'executors': '/executors/', 'storage': '/storage/',
         'env': '/environment/', 'sqllist': '/SQL/'}

def page_for(name):
    if name in PAGES: return PAGES[name]
    kind, _, num = name.partition(':')
    if kind == 'stage': return f'/stages/stage/?id={num}&attempt=0'
    if kind == 'job': return f'/jobs/job/?id={num}'
    if kind == 'sql': return f'/SQL/execution/?id={num}'
    raise SystemExit(f'unknown shot {name}')

async def shoot(base, names, out, find=()):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1600, 'height': 1000}, device_scale_factor=SCALE)
        boxes = {}
        for n in names:
            await pg.goto(base + page_for(n)); await pg.wait_for_timeout(2000)
            if n == 'timeline' or n.startswith('job:'):
                for t in await pg.query_selector_all('span.expand-application-timeline, span.expand-job-timeline'):
                    await t.click(); await pg.wait_for_timeout(1500)
            if n.startswith('stage:'):
                for sel in ['span.expand-dag-viz', 'span.expand-task-assignment-timeline']:
                    el = await pg.query_selector(sel)
                    if el: await el.click(); await pg.wait_for_timeout(1500)
            key = n.replace(":", "_")
            await pg.screenshot(path=f'{out}/shot_{key}.png', full_page=True)
            boxes[key] = {}
            for txt in find:                       # screenshot-pixel boxes of a label and of its table row
                loc = pg.get_by_text(txt, exact=True)
                if await loc.count() == 0: continue
                cell = await loc.first.bounding_box()
                row = loc.first.locator('xpath=ancestor::tr[1]')
                rbox = await row.bounding_box() if await row.count() else None
                sc = lambda bb: [round(bb[k] * SCALE) for k in ('x', 'y', 'width', 'height')] if bb else None
                boxes[key][txt] = dict(cell=sc(cell), row=sc(rbox))
        json.dump(boxes, open(f'{out}/boxes.json', 'w'), indent=1)
        await b.close()

def main():
    lab, out = sys.argv[1], sys.argv[2]
    shots = sys.argv[sys.argv.index('--shots') + 1].split(',') if '--shots' in sys.argv else \
        ['jobs', 'stages', 'executors', 'sqllist']
    find = [t for t in sys.argv[sys.argv.index('--find') + 1].split('|')] if '--find' in sys.argv else []
    os.makedirs(out, exist_ok=True)
    ready = os.path.abspath(f'{out}/.ready'); 
    if os.path.exists(ready): os.remove(ready)
    env = dict(os.environ, LAB_KEEP='900', LAB_READY_FILE=ready)
    log = open(f'{out}/console.txt', 'w')
    proc = subprocess.Popen([sys.executable, os.path.basename(lab)], cwd=os.path.dirname(os.path.abspath(lab)),
                            env=env, stdout=log, stderr=subprocess.DEVNULL, start_new_session=True)
    t0 = time.time()
    while not os.path.exists(ready):
        if proc.poll() is not None: raise SystemExit(f'lab exited early, see {out}/console.txt')
        if time.time() - t0 > 900: proc.kill(); raise SystemExit('lab took over 15 min')
        time.sleep(2)
    ui = open(ready).read().strip().replace('0.0.0.0', 'localhost')
    try:
        api = f'{ui}/api/v1/applications'; app = get(api)[0]['id']; A = f'{api}/{app}'
        q = 'quantiles=0,0.25,0.5,0.75,1.0'
        stages = get(f'{A}/stages')
        for s in stages:
            try: s['taskSummary'] = get(f"{A}/stages/{s['stageId']}/{s['attemptId']}/taskSummary?{q}")
            except Exception: s['taskSummary'] = None
        m = dict(app=app, ui=ui, lab=os.path.basename(lab), seconds=round(time.time() - t0),
                 jobs=get(f'{A}/jobs'), stages=stages, executors=get(f'{A}/allexecutors'),
                 storage=get(f'{A}/storage/rdd'), sql=get(f'{A}/sql?details=true&planDescription=true'))
        json.dump(m, open(f'{out}/metrics.json', 'w'), indent=1)
        asyncio.run(shoot(ui, shots, out, find))
        print(f"captured {len(m['jobs'])} jobs, {len(stages)} stages, {len(shots)} shots -> {out}")
    finally:
        os.killpg(proc.pid, 15); proc.wait(timeout=60)

if __name__ == '__main__':
    main()
