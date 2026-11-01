"""Series 2 template - how a Spark UI episode uses REAL captured data. Copy into episodes/uiNN.py.

Before writing beats:
  python3 capture.py labs-repo/labs/epNN_x.py out/uiNN/ui --shots stage:2,sql:0 --find "Shuffle Read Size / Records"
  python3 ui_summary.py out/uiNN/ui/metrics.json      # every number you narrate comes from here
Look at out/uiNN/ui/shot_*.png before choosing crops. Boxes in boxes.json are screenshot pixels.
"""
import json, os
from engine import *

UI = os.path.join(HERE, 'out', 'ui07', 'ui')          # <- change per episode
def metrics(): return json.load(open(f'{UI}/metrics.json'))
def boxes(shot): return json.load(open(f'{UI}/boxes.json'))[shot]
def stage(m, sid): return [s for s in m['stages'] if s['stageId'] == sid][0]

def summary_scene(c, x):
    """Beat 0: show the Summary Metrics table. Beat 1: spotlight the row. Beat 2: zoom + the number."""
    m = metrics(); bx = boxes('stage_2')
    rr = stage(m, 2)['taskSummary']['shuffleReadMetrics']['readRecords']
    top = bx['Summary Metrics for 8 Completed Tasks']['cell']; row = bx['Shuffle Read Size / Records']['row']
    wide = (0, top[1] - 20, 2000, row[1] + row[3] + 40 - (top[1] - 20))
    tight = (row[0] + row[2] * .38, row[1] - 70, row[2] * .62 + 10, row[3] + 100)   # median..max columns, magnified
    a = x.p(0, .6)
    sh = ui_shot(c, f'{UI}/shot_stage_2.png', 160, 170, 1600, crop=tight, zoom_from=wide, zoom=x.p(2, 1.0),
                 a=a, url='localhost:4040/stages/stage/?id=2')
    spotlight(c, sh.rect(*row), a=x.p(1, .5), t=x.t)
    r = sh.rect(*row)
    callout(c, f'max {int(rr[4]):,}  vs  median {int(rr[2]):,}  =  {rr[4] / rr[2]:.0f}x',
            W / 2, min(860, r[1] + r[3] + 170), target=(r[0] + r[2] * .85, r[1] + r[3] + 10),
            a=x.p(2, .5, .8), prog=x.p(2, .6, .9))

EP = dict(id='ui_template', tag='UI 07', short='Summary Metrics')
SCENES = [Scene('Summary metrics', ['Open the stage.', 'Find this row.', 'Compare the biggest task with the median.'], summary_scene)]
