"""Check, document legacy differences, hash and package a sealed release.
Run with the authoring venv (jsonschema installed). Never run Tribunal AI.
"""
import pathlib, json, hashlib, subprocess, sys, zipfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
DEST=pathlib.Path('/Users/hanweizhou/Desktop/tribunal-wild-v2-sealed-20261001.zip')
def digest(b): return hashlib.sha256(b).hexdigest()
def run(name):
    r=subprocess.run([sys.executable,str(ROOT/'gen'/name)],capture_output=True,text=True,check=True)
    return r.stdout

structural=run('validate.py'); semantic=run('semcheck.py'); legacy=run('legacy_semcheck.py')
(ROOT/'eval/wild-v2/validation.txt').write_text(structural+semantic)
(ROOT/'eval/wild-v2/legacy_semcheck.txt').write_text(legacy)
report=json.loads((ROOT/'eval/wild-v2/semantic_check.json').read_text())
key=json.loads((ROOT/'eval/wild-v2/ground_truth.json').read_text())
diffs=[int(line.split()[1]) for line in legacy.splitlines() if line.startswith('DIFF')]
assert set(diffs)=={708,711,714,716,719}
parts=['# Private legacy semantic-check differences\n',
       'The preserved v1 checker checks two fields only. Its five differences do not establish that the new key is wrong. The case-only replacement independently checks all four fields and reports zero differences.\n']
for no in diffs:
    parts.append(f"## Case {no}\n\nThe legacy checker selects NO_ACTION from the quoted/completed-trip branch before checking the mandatory deciding-evidence or amended-baseline trigger. The author key selects ESCALATE.\n\nIndependent trigger: {report['calculations'][str(no)]['trigger']}.\n\n{key[str(no)]['rationale']}\n")
parts.append('## Additional untested legacy fields\n\nThe old checker neither derives nor compares driver_compensation_sgd or referrals. Case 712 has a required POL-RD-09(4) billing-integrity referral; the new checker independently re-matches its gantries and compares that referral, not merely its amount. All other empty referral arrays are deliberate: no generic safety/conduct/policy-gap referral was invented from a source recommendation. No driver payment is licensed on this set.\n')
parts.append('## Source suggestions versus frozen policy\n\nSource-seed expected_ruling is non-authoritative. The mapping below accounts for every retained seed instance; changed suggestions are explained by each key rationale and the schema-compliant rewrite, not by wild-v1 performance.\n')
provenance=json.loads((ROOT/'eval/wild-v2/seed_map.json').read_text())
for no,p in provenance.items():
    parts.append(f"- {no}: {p['seed_id']}; suggested {p['seed_suggestion']}; author {p['author_ruling']}.\n")
(ROOT/'eval/wild-v2/legacy_check_differences.md').write_text('\n'.join(parts))

# Source snapshots must remain byte-identical. Read only these explicitly
# requested public contract/policy/schema files, not repository run notes.
originals={'data/schema.json':pathlib.Path('/Users/hanweizhou/Desktop/Tencent /data/schema.json'),
 'data/PUBLIC-CONTRACT.md':pathlib.Path('/Users/hanweizhou/Desktop/Tribunal/data/PUBLIC-CONTRACT.md')}
for f in ('general','no_show','route_deviation'):
    originals[f'policy/{f}.json']=pathlib.Path(f'/Users/hanweizhou/Desktop/Tribunal/policy/{f}.json')
for rel,src in originals.items(): assert (ROOT/rel).read_bytes()==src.read_bytes(),rel
files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(ROOT.rglob('*'))
       if p.is_file() and '__pycache__' not in p.parts and p.name!='MANIFEST.json'}
cases=[{'path':p,'sha256':h} for p,h in sorted(files.items()) if p.startswith('data/wild-v2/cases/')]
assert len(cases)==20
case_set_bytes=json.dumps(cases,sort_keys=True,separators=(',',':')).encode()
manifest=dict(set='wild-v2',status='SEALED',created='2026-10-01',case_count=20,
    case_set_sha256=digest(case_set_bytes),case_set_hash_algorithm='sha256(compact sort_keys UTF-8 JSON of sorted [{path,sha256}] case list)',
    answer_key_sha256=files['eval/wild-v2/ground_truth.json'],index_sha256=files['data/wild-v2/index.json'],
    cases=cases,files=files,checks=dict(strict_schema_contract=True,unchanged_amount_limits=True,
        validator_passed=True,independent_four_field_differences=0,legacy_differences=diffs,
        isolated_loader_cases=20,formal_tribunal_inference_runs=0))
(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
if DEST.exists(): raise FileExistsError('Refusing to overwrite an existing sealed archive: '+str(DEST))
with zipfile.ZipFile(DEST,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for rel in sorted([*files,'MANIFEST.json']):
        info=zipfile.ZipInfo(rel,date_time=(2026,10,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100600<<16
        z.writestr(info,(ROOT/rel).read_bytes())
receipt=DEST.with_suffix('.zip.sha256')
receipt.write_text(digest(DEST.read_bytes())+'  '+DEST.name+'\n')
with zipfile.ZipFile(DEST) as z:
    assert z.testzip() is None
    for rel,h in files.items(): assert digest(z.read(rel))==h,rel
    for case in cases:
        c=json.loads(z.read(case['path']))
        def clean(x):
            if isinstance(x,dict):
                assert not {'ground_truth','expected_ruling','expected_amount_sgd','expected_driver_compensation_sgd','expected_referrals','difficulty','rationale','governing_clauses'} & x.keys()
                for v in x.values(): clean(v)
            elif isinstance(x,list):
                for v in x: clean(v)
        clean(c)
print('Sealed ZIP:',DEST)
print('SHA256:',digest(DEST.read_bytes()))
print('20 cases; strict validation passed; independent 80-field check passed; ZIP integrity and public-shard answer isolation passed.')
