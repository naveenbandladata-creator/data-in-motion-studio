"""Print a readable digest of a capture:  python3 ui_summary.py out/epNN/ui/metrics.json"""
import sys, json
m = json.load(open(sys.argv[1]))
mb = lambda b: f'{b/2**20:.1f} MB'
print(f"app {m['app']}  lab {m['lab']}  captured after {m['seconds']}s")
for j in sorted(m['jobs'], key=lambda j: j['jobId']):
    print(f"job {j['jobId']:>2} {j['status']:<9} stages {j['stageIds']} tasks {j['numTasks']:>4}  {j.get('description', j['name'])[:60]}")
for s in sorted(m['stages'], key=lambda s: s['stageId']):
    ts = s.get('taskSummary') or {}
    rt = [int(v) for v in ts.get('executorRunTime', [])]
    rr = [int(v) for v in ts.get('shuffleReadMetrics', {}).get('readRecords', [])]
    print(f"stage {s['stageId']:>2} {s['status']:<8} tasks {s['numTasks']:>4} in {mb(s['inputBytes'])} "
          f"shW {mb(s['shuffleWriteBytes'])} shR {mb(s['shuffleReadBytes'])} spillMem {mb(s['memoryBytesSpilled'])} "
          f"spillDisk {mb(s['diskBytesSpilled'])}  runtime min/med/max {rt[0] if rt else '-'}/{rt[2] if rt else '-'}/{rt[4] if rt else '-'} ms"
          + (f"  readRecords med/max {rr[2]}/{rr[4]}" if rr and rr[4] else ''))
for e in m['executors']:
    print(f"executor {e['id']:<6} active {e['isActive']} tasks {e['totalTasks']} failed {e['failedTasks']} gc {e['totalGCTime']}ms")
for r in m['storage']:
    print(f"cached {r['name'][:50]} {r['numCachedPartitions']}/{r['numPartitions']} {mb(r['memoryUsed'])}")
