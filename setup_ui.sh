#!/bin/bash
# Extra setup for Series 2 (Spark UI in Motion). Run from the studio folder AFTER setup.sh.
# Needs GH_TOKEN in the environment (fine-grained, spark-ui-labs only, Contents read/write).
set -e
command -v java >/dev/null || { apt-get update -qq && apt-get install -y -qq openjdk-21-jre-headless; }
pip install "pyspark==4.0.1" pandas playwright --break-system-packages -q
python3 -c "from playwright.sync_api import sync_playwright as s; p=s().start(); p.chromium.executable_path; p.stop()" 2>/dev/null \
  || python3 -m playwright install chromium
REPO=naveenbandladata-creator/spark-ui-labs
AUTH="Authorization: Basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
if [ -d labs-repo/.git ]; then git -C labs-repo -c http.extraHeader="$AUTH" pull -q
else git -c http.extraHeader="$AUTH" clone -q https://github.com/$REPO.git labs-repo; fi
git -C labs-repo config user.name "Data In Motion"; git -C labs-repo config user.email "naveen.bandla.data@gmail.com"
curl -s http://127.0.0.1:8080/json/ >/dev/null 2>&1 || (cd labs-repo && setsid bash start_cluster.sh)
sleep 10
curl -s http://127.0.0.1:8080/json/ | python3 -c "import json,sys;j=json.load(sys.stdin);assert len(j['workers'])==2, j;print('cluster ALIVE, 2 workers')"
echo "series 2 ready: labs in ./labs-repo"
