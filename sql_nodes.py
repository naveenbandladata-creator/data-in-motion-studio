"""Print SQL-tab node metrics from a capture:  python3 sql_nodes.py metrics.json [metric substrings...]"""
import sys, json
m = json.load(open(sys.argv[1])); want = sys.argv[2:] or ['output rows', 'files read', 'partitions read', 'size of files', 'shuffle records written']
for q in m['sql']:
    print(f"\nQUERY {q['id']}  {q.get('description','')[:60]}  {q.get('duration')} ms")
    for n in q.get('nodes', []):
        ms = [f"{x['name']}={x['value']}" for x in n.get('metrics', []) if any(w in x['name'] for w in want)]
        if ms or 'Join' in n['nodeName'] or 'Exchange' in n['nodeName']:
            print(f"  {n['nodeName'][:40]:<40} " + '; '.join(ms)[:150])
