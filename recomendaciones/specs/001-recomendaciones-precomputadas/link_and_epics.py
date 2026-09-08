#!/usr/bin/env python3
"""Crea los epicos por milestone y enlaza dependencias por numero de issue."""
import json, subprocess, pathlib, re

REPO = "HingusPingus/prototipo_recomendaciones"
BASE = pathlib.Path(__file__).resolve().parent
MAN = json.loads((BASE / ".issues/manifest.json").read_text())
NUM = {l.split("\t")[0]: l.split("\t")[1]
       for l in (BASE / ".issues/created.tsv").read_text().splitlines() if l.strip()}

def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()

# ---- 1. reescribir dependencias con numero real de issue
for tid, m in MAN.items():
    if not m["deps"]:
        continue
    body = (BASE / f".issues/{tid}.md").read_text()
    for d in m["deps"]:
        if d in NUM:
            body = body.replace(f"- [ ] {d} debe estar cerrado",
                                f"- [ ] #{NUM[d]} ({d}) debe estar cerrado")
    (BASE / f".issues/{tid}.md").write_text(body)
    sh("gh","issue","edit",NUM[tid],"--repo",REPO,"--body-file",str(BASE/f".issues/{tid}.md"))
    print(f"deps {tid} -> #{NUM[tid]}")

# ---- 2. epicos por milestone
MS_ORDER = ["M1","M2","M3","M4","M5","M6","M7","M8","M9","M10"]
MS_GOAL = {
 "M1":"Dejar el proyecto arrancable, con esquema de datos y configuracion versionada del motor.",
 "M2":"Implementar las tres senales del motor y su combinacion lineal, test-first.",
 "M3":"Garantizar los invariantes de seguridad: edad, exclusion y diversificacion en orden estricto.",
 "M4":"Persistir el top-N en Redis con claves por usuario y modulo, TTL y politica determinista de cache miss.",
 "M5":"Consumir el evento de recalculo con idempotencia, reintentos y dead-letter.",
 "M6":"Sincronizar datos desde api-general de forma unidireccional, autenticada e idempotente.",
 "M7":"Servir el top-N cache-first y registrar feedback emitiendo el evento de recalculo.",
 "M8":"Poder diagnosticar en produccion cada escenario critico.",
 "M9":"Convertir los invariantes y contratos en gates bloqueantes de CI.",
 "M10":"Cerrar la feature con trazabilidad verificable.",
}
by_ms = {}
for tid, m in MAN.items():
    by_ms.setdefault(m["milestone"][:m["milestone"].find(" ")], []).append(tid)

for ms in MS_ORDER:
    tids = sorted(by_ms.get(ms, []))
    if not tids: continue
    full = MAN[tids[0]]["milestone"]
    lines = [f"## Objetivo\n\n{MS_GOAL[ms]}\n",
             "## Issues hijos\n"]
    for t in tids:
        m = MAN[t]
        marks = []
        if m["critical"]: marks.append("🔴 ruta critica")
        if "parallelizable" in m["labels"]: marks.append("⚡ paralelizable")
        if "security-invariant" in m["labels"]: marks.append("🛡️ invariante")
        suf = f" — _{', '.join(marks)}_" if marks else ""
        lines.append(f"- [ ] #{NUM[t]} {t} · `{m['priority']}` · `{m['size']}`{suf}")
    lines += ["\n## Cierre del epico\n",
              "- [ ] Todos los issues hijos cerrados",
              "- [ ] CI en verde sobre la rama del milestone",
              "- [ ] Ningun invariante (INV-1 a INV-4) relajado en el camino",
              f"\n---\n<sub>Epico del milestone {full} · backlog en `specs/001-recomendaciones-precomputadas/tasks.md`</sub>"]
    p = BASE / f".issues/EPIC_{ms}.md"; p.write_text("\n".join(lines))
    out = sh("gh","issue","create","--repo",REPO,
             "--title",f"[{ms}] EPIC — {full.split(' - ',1)[1]}",
             "--body-file",str(p),"--milestone",full,"--label","epic")
    print(f"EPIC {ms} -> {out.splitlines()[-1] if out else 'ERR'}")
