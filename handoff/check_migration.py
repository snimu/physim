"""Static migration checks: no simulator/model imports, no large-cache reads."""
from pathlib import Path
import hashlib,json,re
from urllib.parse import unquote,urlsplit
ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
ABS=ROOT/"probes/blobs/agentenv/round5/resource_revision/absolute_scoring"

def strict(path):
    def fail(v):raise ValueError(f"nonfinite JSON constant in {path}: {v}")
    return json.loads(path.read_text(),parse_constant=fail)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

checks={}; failures=[]
state=strict(HERE/"SESSION_STATE.json")
assets=strict(HERE/"LOCAL_ASSETS.json")
envs=strict(HERE/"ENVIRONMENTS.json")
original=strict(ABS/"PRESERVATION.json")
absolute=strict(ABS/"absolute_scores.json")
checks["runtime_snapshot_closed"]=state["runtime_at_migration"]["direct_children"]==[] and state["runtime_at_migration"]["agent_owned_heartbeats"]==[]
checks["approval_limits_explicit"]=all(state["approval_limits"][k] for k in ("no_automatic_paid_model_rollouts","no_automatic_new_worlds_seeds_truth_battery","no_automatic_gpu_pods"))
original_checks=[]
for row in original["original_files"]:
    p=ABS/row["path"]
    original_checks.append({"path":str(p.relative_to(ROOT)),"matches":p.stat().st_size==row["bytes"] and digest(p)==row["sha256"]})
checks["original_scoring_files_unchanged"]=all(x["matches"] for x in original_checks)
rows=[c for r in absolute.values() for c in r["contracts"].values()]
checks["raw_crps_twelve_matches_at_six_decimals"]=len(rows)==12 and all(round(c["agent_crps"],6)==c["stored_crps"] for c in rows)
checks["recorded_input_hash_comparison_no_mismatch"]=all(r.get("sha256_matches_record") is not False and r.get("bytes_match_record") is not False for r in assets["assets"])
checks["separate_native_environment_snapshots"]=envs["project"]["executable"]!=envs["science"]["executable"]

markdown=[HERE/"SESSION_MIGRATION.md",HERE/"HANDOFF.md",ROOT/"README.md",ABS/"README.md",HERE/"CONTRACT_DISCUSSION.md",ROOT/"probes/blobs/l0/deepsearch/TRACKA_R6_PREDICTOR.md",ROOT/"probes/blobs/agentenv/round6/README.md",ROOT/"probes/blobs/agentenv/round6/PLAN.md"]
missing=[]
for p in markdown:
    for raw in re.findall(r"\]\(([^)]+)\)",p.read_text()):
        link=urlsplit(raw.split(' "',1)[0])
        if link.scheme or link.netloc or not link.path:continue
        if not (p.parent/unquote(link.path)).resolve().exists():missing.append([str(p.relative_to(ROOT)),raw])
checks["migration_local_links_exist"]=not missing
if missing:failures.append({"missing_links":missing})

json_paths=sorted(HERE.glob("*.json"))+sorted(ABS.glob("*.json"))
for p in json_paths:strict(p)
checks["migration_json_is_finite"]=True
text_paths=markdown+sorted(HERE.glob("*.py"))+json_paths+[ABS/"absolute_scores.py",ABS/"run.log"]
patterns=[r"sk-[A-Za-z0-9_-]{20,}",r"Bearer[ \t]+[A-Za-z0-9_.-]{20,}"]
credential_files=[str(p.relative_to(ROOT)) for p in text_paths if any(re.search(r,p.read_text()) for r in patterns)]
checks["no_credential_value_patterns_in_new_material"]=not credential_files
if credential_files:failures.append({"credential_pattern_files":credential_files})
checks["corrected_scoring_warning_present"]="Known flaws" in (ABS/"README.md").read_text() and "not adopted" in (ABS/"README.md").read_text()
checks["corrected_current_handoff_present"]="SESSION_MIGRATION.md" in (HERE/"HANDOFF.md").read_text() and "now archived unchanged" in (HERE/"HANDOFF.md").read_text()
report={"schema":"physim-migration-validation-v1","status":"passed" if all(checks.values()) else "failed","checks":checks,"original_file_checks":original_checks,"failures":failures,"limitations":["Checks recorded live-state snapshot, not another session's runtime.","No raw trace, field cache, archive, simulator or predictor was read/executed by this checker.","Input hashes are those recorded by the separate inventory command, not recomputed here.","Credential scan is narrow; old launchers were not read or included.","No new scientific claims or normalized scoring policy are validated."]}
(HERE/"VALIDATION.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"status":report["status"],"checks":checks,"failures":failures},indent=2))
raise SystemExit(0 if report["status"]=="passed" else 1)
