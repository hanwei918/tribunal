"""Finalize tribunal-sealed-v3: check_set output, second-reading count, MANIFEST, zips, SHA256SUMS.

Prints only file names, counts and SHA-256 values - never a case's content or answer.
usage: python3 tools/finalize.py <workspace>
"""
import collections, glob, hashlib, json, os, shutil, subprocess, sys, zipfile

W = os.path.abspath(sys.argv[1])
REF, OUT, BUILD, REVIEW, DIST = (os.path.join(W, d) for d in ("ref", "out", "build", "review", "dist"))
CASES, ANS = os.path.join(OUT, "cases"), os.path.join(OUT, "answers")
SRC = "/Users/hanweizhou/Desktop/Tribunal-提交材料/sealed-v3-authoring"
REF_NAMES = ["PUBLIC-CONTRACT.md", "general.json", "no_show.json", "route_deviation.json",
             "0001-pol-ns-11.json", "0002-pol-rd-14.json", "0003-pol-ns-12.json", "check_set.py", "case-00901.json"]
POLICY = ["general.json", "no_show.json", "route_deviation.json",
          "0001-pol-ns-11.json", "0002-pol-rd-14.json", "0003-pol-ns-12.json"]
ZIP_TIME = (2026, 10, 13, 0, 0, 0)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def die(msg):
    print("ABORT:", msg)
    sys.exit(1)


# 1. reference files: as received (original bytes) and the copies used must agree
ref_sha = {}
for n in REF_NAMES:
    a, b = sha(os.path.join(SRC, n)), sha(os.path.join(REF, n))
    if a != b:
        die("reference copy differs from the original: " + n)
    ref_sha[n] = a

# 2. check_set, run from out/, output saved verbatim
cp = subprocess.run([sys.executable, os.path.join(REF, "check_set.py"), "cases", "answers/ground_truth.json",
                     "--range", "4001", "4099"], cwd=OUT, capture_output=True, text=True)
check_out = cp.stdout + cp.stderr
if cp.returncode != 0 or not check_out.strip().endswith("0 failure(s)") or "WARN" in check_out:
    die("check_set is not clean")

# 3. second reading: compare the first key (snapshot) with the final key, case by case
key = json.load(open(os.path.join(ANS, "ground_truth.json")))
first = json.load(open(os.path.join(REVIEW, "round0", "ground_truth.json")))
fk = {r["case_no"]: r for r in first}
nums = sorted(r["case_no"] for r in key)
key_changed = [n for n in nums if fk.get(n) != next(r for r in key if r["case_no"] == n)]
file_changed = [n for n in nums
                if sha(os.path.join(REVIEW, "round0", "cases", "case-%05d.json" % n)) != sha(os.path.join(CASES, "case-%05d.json" % n))]
verdicts = collections.OrderedDict()
for rdir in sorted(glob.glob(os.path.join(REVIEW, "r[0-9]*"))):
    rnd = os.path.basename(rdir)
    verdicts[rnd] = {}
    for p in sorted(glob.glob(os.path.join(rdir, "compare-*.json"))):
        c = json.load(open(p))
        verdicts[rnd][str(c["case_no"])] = c["verdict"]

# 4. counts from the final files
disputes = {}
for n in nums:
    disputes[n] = json.load(open(os.path.join(CASES, "case-%05d.json" % n)))["dispute"]
cnt = lambda xs: dict(sorted(collections.Counter(xs).items()))
categories = cnt(d["category"] for d in disputes.values())
filed_by = cnt(d["filed_by"] for d in disputes.values())
rulings = cnt(r["ground_truth"]["expected_ruling"] for r in key)
difficulty = cnt(r["ground_truth"]["difficulty"] for r in key)
canary = open(os.path.join(CASES, "CANARY.txt")).read()

# 5. authoring records and second-reading records go with the answers (sealed side)
auth = os.path.join(ANS, "authoring")
sr = os.path.join(ANS, "second_reading")
for d in (auth, sr):
    if os.path.exists(d):
        shutil.rmtree(d)
shutil.copytree(BUILD, auth, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copytree(REVIEW, sr, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "scratch*", "tmp*"))
summary = {
    "definition": "second_reading_changes counts the cases whose answer-key record differs between the key as first "
                  "generated (snapshot taken before the second reading, in round0/) and the final key. Case files "
                  "changed during the second reading are counted separately.",
    "key_changed_cases": len(key_changed),
    "key_changed_case_numbers": key_changed,
    "case_file_changed_cases": len(file_changed),
    "case_file_changed_case_numbers": file_changed,
    "verdicts_by_round": verdicts,
}
json.dump(summary, open(os.path.join(sr, "SUMMARY.json"), "w"), indent=2)
open(os.path.join(ANS, "check_set_output.txt"), "w").write(check_out)

# 6. MANIFEST
manifest = collections.OrderedDict([
    ("sealed_set", "tribunal-sealed-v3"),
    ("created", "2026-10-13"),
    ("author", "Claude, in a fresh Claude Code desktop session started with no project folder and no repository access "
               "(a scratch workspace only), not a claude.ai chat; model: Opus 5.5 (claude-opus-5-5), as stated in the "
               "session's own system information. Workflow subagents were launched without a model override and so "
               "ran on the session model."),
    ("prompted_by", "Zhou Hanwei (team owner), who supplied the nine files and this prompt"),
    ("independence", collections.OrderedDict([
        ("saw", ["the nine reference files listed in reference_file_sha256",
                 "the owner's prompt for this set",
                 "the owner's general Claude Code instructions loaded automatically into every session, which name the "
                 "hackathon project and the folder of its code but contain none of its code, prompts, runs or results"]),
        ("did_not_see", ["the system's code", "the system's prompts", "any run of the system or its results",
                         "any other test set or answer key", "any discussion of the system, its runs or other sets"]),
        ("how", "All work ran in a scratch workspace holding copies of the nine files. The orchestrating session and its "
                "subagents were instructed not to open, list or search anything outside it, and the subagents' file "
                "accesses were audited afterwards (see second_reading/SUMMARY.json and the author's report). Second "
                "readers saw only one case file and the six policy files (plus the public contract)."),
    ])),
    ("review_status", "no human review; the reference answers are the author's, checked by the author's own second reading"),
    ("second_reading_changes", len(key_changed)),
    ("second_reading_case_file_changes", len(file_changed)),
    ("tools_used", ["Python 3.11 standard library (json, decimal, math, random, hashlib, uuid, datetime, zipfile)",
                    "check_set.py as received, unmodified",
                    "Claude Code Workflow tool: subagents for planning, blueprint design and adversarial critique, "
                    "generator code and audits, two blind second readers per case, and a comparison of each reading "
                    "with the key",
                    "per-category audit scripts that re-derive the deciding measurements from the generated files and "
                    "were shown to fail on a corrupted copy"]),
    ("schema_version", "1.2.0"),
    ("policy_version", 6),
    ("policy_files", POLICY),
    ("reference_file_sha256", ref_sha),
    ("case_count", len(nums)),
    ("case_numbers", nums),
    ("categories", categories),
    ("rulings", rulings),
    ("difficulty", difficulty),
    ("filed_by", filed_by),
    ("case_file_sha256", {"case-%05d.json" % n: sha(os.path.join(CASES, "case-%05d.json" % n)) for n in nums}),
    ("other_case_folder_files_sha256", {f: sha(os.path.join(CASES, f)) for f in ("index.json", "CANARY.txt", "README.md")}),
    ("answer_key_sha256", sha(os.path.join(ANS, "ground_truth.json"))),
    ("canary", canary),
    ("protocol", collections.OrderedDict([
        ("runs_allowed", 1),
        ("run_from", "freeze-2026-10-11"),
        ("no_tuning_after_run", "Any tuning using this set after the sealed run turns it into a development set; "
                                "the key is not edited after the run"),
        ("run_performed", False),
    ])),
])
json.dump(manifest, open(os.path.join(ANS, "MANIFEST.json"), "w"), indent=2)
open(os.path.join(ANS, "MANIFEST.json"), "a").write("\n")


# 7. deterministic zips and SHA256SUMS
def zip_dir(src_parent, folder, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(os.path.join(src_parent, folder)):
            dirs.sort()
            for f in sorted(files):
                full = os.path.join(root, f)
                zi = zipfile.ZipInfo(os.path.relpath(full, src_parent), ZIP_TIME)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                z.writestr(zi, open(full, "rb").read())


os.makedirs(DIST, exist_ok=True)
A, B = "tribunal-sealed-v3-A-cases.zip", "tribunal-sealed-v3-B-answers.zip"
zip_dir(OUT, "cases", os.path.join(DIST, A))
zip_dir(OUT, "answers", os.path.join(DIST, B))
sums = "".join("{0}  {1}\n".format(sha(os.path.join(DIST, f)), f) for f in (A, B))
open(os.path.join(DIST, "SHA256SUMS"), "w").write(sums)

# report: counts and hashes only
print("check_set:", check_out.strip().splitlines()[-1])
print("categories", categories, "| filed_by", filed_by)
print("rulings", rulings)
print("difficulty", difficulty)
print("second_reading_changes (key)", len(key_changed), "| case files changed", len(file_changed))
print("answer_key_sha256", manifest["answer_key_sha256"])
print(sums, end="")
