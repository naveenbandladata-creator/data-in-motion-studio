# Data in Motion - episode production guide

Channel: daily animated PySpark explainers, 1920x1080 @30fps, 2.5-4 min, AI voice (Kokoro `af_heart`).

## Files
- engine.py   drawing primitives (cards, blocks/partitions, arrows w/ flowing dots, servers, cores, code panel w/ typing + highlight, file icon, laptop, pills, spark logo), background, chrome, captions.
- build.py    TTS -> timeline -> per-scene render (skia -> ffmpeg) -> concat -> audio mix (voice + synthesized pad, ducked, loudnorm) -> mp4, .srt, thumbnail.png, youtube.txt
- episodes/ep01.py  REFERENCE episode. Copy its structure exactly.
- topics.json / status.json  30-day plan; status.json drives the hub page.

## Writing an episode (episodes/epNN.py)
- `EP = dict(id='epNN', tag='EP NN', short='<4-5 word topic>')`, `META` (title, description, tags), `SCENES`, `thumbnail(c)`.
- Scene('Chapter name', [beat sentences...], draw_fn). Each beat = 1-2 sentences of narration. In draw_fn(c, x):
  `x.p(i, dur, delay)` eased 0->1 starting when beat i starts; `x.since(i)`; `x.t`; `x.b[i]` beat start; `x.D` scene length.
  Animate each visual on the beat that talks about it. Fade old elements out with `* (1 - x.p(next_beat, .5))`.
- Structure: Hook (problem, 15-20s) -> Title card (chrome=False, captions=False) -> 3-4 concept scenes -> code scene -> Recap cards -> "Next episode" + Subscribe.
- Safe content area: y 110..930 (captions live at the bottom ~950-1046, chrome at top <90).
- Write numbers/abbreviations for the voice as words in beats ("one hundred and twenty eight megabytes"); visuals can show "128 MB".
- Technical accuracy matters: only state defaults/config names you are sure of (e.g. spark.sql.shuffle.partitions = 200, spark.sql.autoBroadcastJoinThreshold = 10MB, maxPartitionBytes = 128MB).

## Plain-English style (Naveen, 2026-11-01 - applies to every episode from Ep 3 on)
Audience: someone who knows a bit of Python/SQL but is new to Spark. A first-time viewer must get the point in one watch.
Length stays 3-4 min; spend the time on examples and analogies, not on more terms.
- One question per episode, in the viewer's words (e.g. "Which one should I use in Python, and why?"). Hook = a concrete problem they recognise.
- Max 3 new technical terms per episode. Introduce each with an everyday analogy FIRST, then the real name
  (RDD = sealed boxes, DataFrame = labelled table, Python round trip = a trip per row).
- Every other term: either say it in plain words ("Spark runs on Java" not "JVM"; "packed up and sent" not "serialized")
  or cut it. Interesting-but-extra internals (Tungsten, lineage, plan operators, compiler details) go to their own episode.
- One action-able takeaway, shown big on screen and as the last recap card (e.g. "In PySpark: use DataFrames").
- Code scene: the shortest code that shows the idea; explain what it does, not its internals. No explain()/plan dumps unless the episode is about plans.
- Self-check before rendering: read the narration aloud as a beginner - any word you'd have to google? Replace it or define it with a picture.
Ep 3 v2 (sealed boxes / labelled table / round trips) is the reference for this style; ep01 stays the reference for structure and branding.

## Everyday analogy dictionary (use these; same term = same analogy in every episode)
Rules: show the analogy first, then the real name on screen next to it. One analogy "world" per scene. If the analogy would
plant a wrong idea, add one short "where it breaks" line (listed below). Recurring cluster terms use the RESTAURANT KITCHEN.
| Spark term | Everyday analogy | Where it breaks / careful |
|---|---|---|
| Cluster | a restaurant kitchen with many cooks | |
| Driver | head chef: reads the order, plans, hands out work, doesn't cook the big batches | collect() = every plate carried to the head chef's small counter -> it overflows (driver OOM) |
| Executor / cores | a cook at a station / the cook's burners (one dish per burner at a time) | |
| Cluster manager | the restaurant manager who assigns cooks and stations | |
| Partition / task | one tray of ingredients / "cook this tray" | |
| Tasks in waves | more trays than burners: next tray goes on when a burner frees up | |
| Transformation vs action | writing recipe steps vs a customer actually ordering the dish | |
| Lazy evaluation | nothing is cooked until someone orders | |
| Logical plan | the recipe card | |
| Optimizer (Catalyst) | a GPS: you say the destination, it picks the fastest route | |
| Column pruning | only take the ingredients the recipe uses out of the fridge | |
| Predicate pushdown / filter early | pick only the ripe tomatoes at the market instead of carrying the whole crate home | |
| Job / stage / task | the whole order / a course that must finish before the next starts / one cook's portion | |
| Narrow vs wide | each cook works on their own tray vs everyone has to swap ingredients between stations | |
| Shuffle | a post office sorting every letter by pin code across all branches: pack, send, unpack | |
| groupBy partial aggregation | each polling booth counts its own votes, only totals go to HQ | |
| Sort-merge join | two stacks of exam papers, both sorted by roll number, merged side by side | |
| Broadcast join | photocopy the small price list and give every cashier a copy | only works if the list is small enough to copy everywhere |
| Data skew / salting | one checkout line has the whole queue; everyone waits / split that queue across extra counters | |
| repartition vs coalesce | shuffle the whole deck into new piles vs just stacking neighbouring piles together | |
| cache / persist | keep chopped onions in the fridge instead of chopping again; memory vs disk = fridge vs freezer | cache is lazy: the fridge fills only the first time you cook |
| Executor memory / spill / OOM | a desk: work space + reference books share it / papers moved to the floor (disk) / the desk collapses | |
| AQE | GPS re-routing mid-trip using live traffic | |
| Parquet (columnar) + min/max stats | a library shelved by column / box labels "dates Jan 1-15" so you skip boxes | |
| partitionBy / pruning / over-partitioning | filing-cabinet drawers per month / only open March / a drawer per day per city = thousands of near-empty drawers | |
| Bucketing | mail pre-sorted into numbered pigeonholes, so matching is instant | |
| Window functions | running total on a bank statement; row_number = finishing positions per race category; lag = yesterday's price | |
| Python UDF / built-in / pandas UDF | translator for every sentence / a native speaker / translating a whole page at once | |
| explain() | GPS route preview before you drive | |
| Spark UI | the car dashboard | |
| Schema / inferSchema | a form's labelled fields / reading the whole book just to write its table of contents | |
| Null | a blank field on a form: unknown, not zero | |
| Small files problem | 10,000 receipts in separate envelopes vs one binder | |
| Streaming micro-batch / checkpoint | a bus leaving every few minutes with whoever is waiting / a bookmark | |
| Watermark | "late homework accepted up to two days", then the gradebook closes | |
| Delta Lake log / time travel / MERGE | a bank passbook / last month's statement / updating a contact list (fix existing, add new) | |
| shuffle partitions setting | the number of checkout counters you open | |

## Build
    bash setup.sh
    python3 build.py episodes/epNN.py --times                 # TTS + timings only
    python3 build.py episodes/epNN.py --preview 5,30,60,...    # PNG stills to out/epNN/ - LOOK at them, fix overlaps
    python3 build.py episodes/epNN.py                          # full render (~15-20 min on 2 cores)
Outputs: out/epNN/epNN.mp4, epNN.srt, thumbnail.png, youtube.txt

## Approval gate (nothing goes public without Naveen's YES)
Episode statuses in status.json: "planned" -> "awaiting_approval" -> "posted".
The daily run takes the lowest-numbered "planned" episode, so episodes still awaiting approval never block the next one.

Daily run (review stage):
1. Upload PRIVATE: `python3 youtube.py publish out/epNN PLZuolPojDl_8 --privacy private` (thumbnail, captions, playlist as usual).
2. Write post.txt but do NOT run linkedin.py post.
3. In status.json set the episode to: "status": "awaiting_approval", "youtube": "<https://youtu.be/ID>", "youtube_id": "<ID>",
   "youtube_title": "<exact YouTube title>", "duration": "<m:ss>", "linkedin_text": "<full post.txt text>".
   Publish status.json AND studio/episodes/epNN.py.txt to the hub, so approval or a re-render works from any session.
4. Notify Naveen (PushNotification + SendUserMessage + the thumbnail via SendUserFile): private link, exact LinkedIn text,
   any other episodes still "awaiting_approval", and the line "Reply YES to publish, or tell me what to change".

Approval ("YES" in the run's session, or "approve episode N" in any chat in the Data in Motion Studio project):
1. Read the hub (status.json, studio/youtube.py.txt, studio/linkedin.py.txt). If ./studio is gone, recreate it from the hub.
   Credentials: in the run's session they are in its task prompt; in a project chat, read the project doc credentials.env
   and `source` it. Never print, publish or message their values.
2. Confirm the episode's status is "awaiting_approval" (if it is already "posted", do nothing and say so).
3. `python3 youtube.py set-privacy <youtube_id> public` - must report "privacy": "public".
4. Write linkedin_text to post.txt exactly, then `python3 linkedin.py post post.txt <youtube url> "<youtube_title>"`.
   On 401: send the post text and the re-auth URL below, and leave the status as "awaiting_approval" with "youtube_public": true.
5. Set status "posted", add "linkedin": "<post url>", remove "linkedin_text", publish status.json to the hub (read it first).
   Republish index.html unchanged.
6. Reply with the public YouTube URL and the LinkedIn post URL.

Changes requested instead of YES:
- Text only (LinkedIn post, YouTube title/description): edit, update status.json (and youtube.txt / video metadata if needed), ask again.
- Video changes: edit episodes/epNN.py, re-render, upload again PRIVATE, then delete the old private upload only if the new upload
  succeeded (or leave it and tell Naveen its id), update youtube/youtube_id in status.json, publish epNN.py.txt, and ask again.

## YouTube (channel: Data In Motion, @DataInMotionYT)
    python3 youtube.py whoami                                  # must print 'Data In Motion'
    python3 youtube.py publish out/epNN PLZuolPojDl_8 --privacy private
    python3 youtube.py set-privacy <video_id> public           # on approval (videos.update, keeps other status fields)
Playlist "Spark in Motion" = PLZuolPojDl_8. Needs YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN env vars (given in the task prompt; never publish them).
Video title style: "<punchy outcome-focused title> | PySpark Ep N" (no word "Animated").

## LinkedIn (Naveen's profile) - only after approval
    python3 linkedin.py whoami
    python3 linkedin.py post post.txt https://youtu.be/<ID> "<YouTube title>"
Needs LI_CLIENT_ID / LI_CLIENT_SECRET / LI_ACCESS_TOKEN / LI_PERSON_URN (given in the task prompt; never publish them). Token expires ~2026-12-30.
Re-auth URL: https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=77ac1sr84bk85q&redirect_uri=https%3A%2F%2Fnaveenbandladata-creator.github.io%2F&scope=openid%20profile%20w_member_social&state=dim1

---------------------------------------------------------------------------------------------------
# SERIES 2: Spark UI in Motion (hub episodes 31-54, on screen "UI 01" ... "UI 24")
Goal: a data engineer who finishes the series can open ANY Spark UI and read it without confusion.
Every episode teaches with the REAL Spark UI from a REAL job, never invented screens or numbers.

## Identity
- status.json entries have "series": "Spark UI in Motion", "series_ep": N, "lab": "labs/epNN_x.py".
- EP = dict(id='uiNN', tag='UI NN', short='<4-5 words>'); file episodes/uiNN.py; output out/uiNN/.
- Title card line: "Data in Motion. Spark UI, episode N: <title>." YouTube title: "<punchy outcome> | Spark UI Ep N".
- Playlist "Spark UI in Motion" = PLeclC2DCNwhM (created PRIVATE 2026-11-01; made public when UI 01 is approved).
- Analogy world for the UI itself: the car dashboard (see dictionary). Plain-English rules above still apply.
- Thumbnail: a real screenshot fragment (blurred/zoomed) + 3-line hook text + "DATA IN MOTION". Never the Apache Spark logo.

## Lab repo (companion for viewers)
https://github.com/naveenbandladata-creator/spark-ui-labs (public since 2026-11-01).
- labs/common.py fixes the cluster settings (2 executors x 1 core x 512m, shuffle partitions 8, Spark 4.0.1). Never change them
  without re-capturing every published lab.
- One lab per episode: labs/epNN_<topic>.py (NN = series_ep). Docstring = what to open + "Your turn" questions.
  Exercise episodes (6, 12, 18, 24) are labs/epNN_spot_the_problem_K.py with answers/epNN.md.
- All 24 labs exist and were tested on 2026-11-01. Adjust a lab only if the episode needs it: re-run, check the UI still shows the
  lesson CLEARLY (look at the screenshots), push. If a lesson stops showing, change the lab, not the story.
- All 24 labs are already pushed. Only if you changed a lab AND GH_TOKEN is set, push it before uploading; if GH_TOKEN is
  not set, skip the push and list the changed lab in the review message so Naveen knows:
  git -C labs-repo -c http.extraHeader="Authorization: Basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)" push
  Never write the token into files, remotes or git config.

## Per-episode pipeline (after bash setup.sh)
    bash setup_ui.sh                                  # Java, pyspark 4.0.1, Chromium, clone labs-repo, start 1 master + 2 workers
    python3 capture.py labs-repo/labs/epNN_x.py out/uiNN/ui --shots jobs,stage:2,sql:0 --find "Shuffle Read Size / Records|Duration"
    python3 ui_summary.py out/uiNN/ui/metrics.json    # THE source of every number in narration and on screen
- First capture with --shots jobs,stages,executors,sqllist to see stage ids, then capture again with the exact pages you need.
- Shot names: jobs, stages, executors, storage, env, sqllist, stage:<id>, job:<id>, sql:<id>, timeline.
- boxes.json gives screenshot-pixel boxes for --find texts ({cell, row}). Use them with engine.ui_shot() + spotlight() + callout().
  See episodes/ui_template.py (zoom from wide crop to magnified median..max columns, spotlight a row, callout with the ratio).
- ONE Spark app at a time (the cluster has 4 cores). capture.py starts the lab, waits for it, captures, then stops it.
- Numbers vary a little between runs. Narrate numbers from THIS run's metrics.json, rounded ("about thirty times").
  If they differ a lot from the README table, update the table in the same commit.

## Episode structure (3-4 min; exercise episodes 2-3 min)
1. Hook: the symptom in the viewer's words ("one task never finishes").
2. Title card.
3. The real screen: ui_shot of the relevant page, zooming to the part that matters.
4. The tell: spotlight + callout with the one number (from metrics.json).
5. Why: an animated concept scene (engine primitives, kitchen/dashboard analogy). Max 3 new terms.
6. The fix: short code scene (code_panel) with the one change.
7. After: the same screen from the fixed job (most labs run job A and job B, so one capture has both).
8. "Your turn" card: lab file name + the question (big, on screen for at least 4 s).
9. Recap cards, last card = the takeaway; next episode + Subscribe.
Exercise episodes: 3 real screens, each with a 5-second on-screen countdown ("pause and decide"), then the reveal.
Description: what you'll learn, "Lab: https://github.com/naveenbandladata-creator/spark-ui-labs/blob/main/labs/<file>",
"Answers: .../answers/epNN.md" for exercises, the Subscribe line, hashtags (#SparkUI #PySpark #ApacheSpark #DataEngineering).

## Verified on Spark 4.0.1 (2026-11-01), safe to state
- With AQE on (default) a single count() creates 2 jobs; a broadcast join or orderBy can create 3 (orderBy samples the data first).
- PySpark jobs without setJobDescription get unreadable names ("$anonfun$withThreadLocalCaptured...", "save at NativeMethodAccessorImpl...").
- Pre-aggregation hides skew in record counts: groupBy().count() looks even; collect_list sends one huge record per machine,
  so records look even while bytes are 26x apart. Joins show skew in records clearly (31x in lab 7).
- Spill: sort of 6M rows in 2 partitions spilled ~420 MB memory / ~340 MB disk; with 32 partitions, 0.
- Killing an executor: Executors tab shows it Dead with "Command exited with code 137", a replacement executor starts,
  failed tasks are counted, the job still succeeds. Exit code 52 = executor out of memory (lab 12 with 3M rows).
- "size of files read" on a Scan box = size of the files OPENED; column pruning shows in the Stages "Input" column (24 MB vs 190 MB, lab 15).
- A filter through a Python UDF on a partition column reads all folders (12 of 12); filtering the column directly reads 1 (lab 15, 18).
- AQE: 200 shuffle partitions coalesced to 1 task; a sort-merge join in the Initial Plan became a broadcast join at runtime (lab 16).
- dropDuplicates appears in the SQL graph as HashAggregate. After a cache hit the graph still draws the original source box,
  but it outputs 0 rows (lab 17). The Storage tab names a .cache() DataFrame by its plan text.
- AQE skew join only triggers when a partition is 5x the median AND over 256 MB (defaults); lab 19 lowers the size limit to 1 MB
  and says so. A skewed partition can be split at most into one piece per map task (16 input pieces -> 16 splits).
- Salting needs more salt values than partitions (64 over 16) or hashing collisions leave skew; it also copies the small table N times.
- 2000 shuffle partitions on small data: ~90 s vs ~8 s with 16 (lab 20). AQE's 64 MB default target still spilled on 512 MB executors.
- Python UDF ~2.3x slower than built-ins on 6M rows; pandas UDF in between (lab 21). Box names: BatchEvalPython / ArrowEvalPython.
- Exceeding spark.driver.maxResultSize fails the action with "Total size of serialized results ... is bigger than spark.driver.maxResultSize".
- Broadcast join removes join skew entirely (the big side is never shuffled): case study 22 s -> 4.5 s (lab 23).
- Both workers run on one machine, so remote shuffle reads are always 0. Say so; never claim network effects from these labs.

## Approval differences
Same gate as Series 1. Extra on approval of UI 01 (series_ep 1) only:
  python3 youtube.py playlist-privacy PLeclC2DCNwhM public
LinkedIn post: "🎬 Spark UI in Motion, Episode N: <title>" + hook + "→ " lines + "🧪 Try it yourself: <lab link>" + watch line.
