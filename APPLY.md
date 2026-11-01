# Apply the Series 2 foundation to the hub (one time)

Run ONCE by the daily task (step 0 of its prompt) when the hub has no studio/capture.py.txt.
Source: this private repo, naveenbandladata-creator/data-in-motion-studio.
Hub: https://claude.ai/artifact/16834BCsBpb7k6WvQb1cto

1. Read the hub (status.json and the studio files).
2. status.json: APPEND every entry of series2_entries.json whose "ep" is not already present. Do not change,
   reorder or overwrite any existing entry. Keep their "status": "draft" (the daily task picks drafts of
   "Spark UI in Motion" only after all "planned" episodes are done).
3. Publish these to the hub as text/plain (replace if they exist):
   studio/engine.py.txt        <- engine.py      (adds ui_shot, spotlight, callout, Shot, font fallback; Series 1 drawing unchanged)
   studio/youtube.py.txt       <- youtube.py     (adds playlist-privacy)
   studio/PRODUCTION.md        <- PRODUCTION.md  (text/markdown; adds the SERIES 2 section at the end)
   studio/capture.py.txt       <- capture.py
   studio/ui_summary.py.txt    <- ui_summary.py
   studio/sql_nodes.py.txt     <- sql_nodes.py
   studio/setup_ui.sh.txt      <- setup_ui.sh
   studio/episodes/ui_template.py.txt <- episodes/ui_template.py
   Republish index.html unchanged (it already understands "draft" and "series").
4. The labs are already on GitHub (all 24). Nothing to push.
5. Do NOT publish TASK_PROMPT.md or any secret. Reply with the list of files published and the count of status.json entries.

