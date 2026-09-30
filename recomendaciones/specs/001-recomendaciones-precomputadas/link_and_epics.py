#!/usr/bin/env python3
"""Enlaza dependencias por número de issue y mantiene un épico por milestone.

Idempotente: los épicos existentes se buscan por título («[Mx] EPIC — …») y se **editan**; solo se crea
el que falte. La versión anterior ejecutaba `gh issue create` para los diez épicos en cada corrida.
Cada hijo terminado aparece tildado, y el épico se cierra cuando todos sus hijos están terminados (se reabre
si alguno vuelve a quedar pendiente).

Uso:  python link_and_epics.py            -> simula
      python link_and_epics.py --apply    -> ejecuta
Requiere haber corrido antes gen_issues.py y publish_issues.py --apply (que escribe .issues/created.tsv).
"""
import json, pathlib, re, shutil, subprocess, sys

REPO = "HingusPingus/prototipo_recomendaciones"
BASE = pathlib.Path(__file__).resolve().parent
MAN = json.loads((BASE / ".issues/manifest.json").read_text(encoding="utf-8"))
NUM = {l.split("\t")[0]: l.split("\t")[1]
       for l in (BASE / ".issues/created.tsv").read_text(encoding="utf-8").splitlines() if l.strip()}
APPLY = "--apply" in sys.argv
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def gh(*a):
    r = subprocess.run([GH, *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"ERROR gh {' '.join(a[:3])}: {r.stderr.strip()}")
    return r.stdout.strip()


def act(desc, *args):
    print(("   " if APPLY else "   [simulación] ") + desc)
    return gh(*args) if APPLY else ""


faltan = sorted(set(MAN) - set(NUM))
if faltan:
    sys.exit(f"ERROR: tareas sin número de issue en created.tsv: {faltan}. Correr publish_issues.py --apply.")

# ---- 1. reescribir dependencias con número real de issue
for tid, m in MAN.items():
    if not m["deps"]:
        continue
    p = BASE / f".issues/{tid}.md"
    body = p.read_text(encoding="utf-8")
    for d in m["deps"]:
        if d in NUM:
            body = re.sub(rf"^- \[([ x])\] {d} debe estar cerrado", rf"- [\1] #{NUM[d]} ({d}) debe estar cerrado",
                          body, flags=re.M)
    p.write_text(body, encoding="utf-8")
    act(f"deps {tid} -> #{NUM[tid]}", "issue", "edit", NUM[tid], "--repo", REPO, "--body-file", str(p))

# ---- 2. épicos por milestone
MS_ORDER = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10", "M11", "M12"]
MS_GOAL = {
 "M1": "Dejar el proyecto arrancable, con esquema de datos y configuracion versionada del motor.",
 "M2": "Implementar las tres senales del motor y su combinacion lineal, test-first.",
 "M3": "Garantizar los invariantes de seguridad: edad, exclusion y diversificacion en orden estricto.",
 "M4": "Persistir el top-N en Redis con claves por usuario y modulo, TTL y politica determinista de cache miss.",
 "M5": "Consumir el evento de recalculo con idempotencia, reintentos y dead-letter.",
 "M6": "Sincronizar datos desde api-general de forma unidireccional, autenticada e idempotente.",
 "M7": "Servir el top-N cache-first desde Redis, con el respaldo solo filtrado por pertenencia, sin computo en el request path.",
 "M8": "Poder diagnosticar en produccion cada escenario critico.",
 "M9": "Convertir los invariantes y contratos en gates bloqueantes de CI.",
 "M10": "Cerrar la feature con trazabilidad verificable.",
 "M11": "Implementar los requisitos de la segunda y tercera sesion de clarificacion y las decisiones del 2026-09-27: "
        "declaracion de gustos, supresion verificada, popularidad por ventana, cuota de novedades y senal de obsoleto.",
 "M12": "Cerrar las brechas entre spec, plan y codigo que encuentra /speckit-converge tras cada implementacion.",
}
epics = {}
epic_state = {}
for i in json.loads(gh("issue", "list", "--repo", REPO, "--state", "all", "--limit", "1000",
                       "--json", "number,title,state")):
    m = re.match(r"\[(M\d+)\] EPIC", i["title"])
    if m:
        epics[m.group(1)] = i["number"]
        epic_state[m.group(1)] = i["state"]

by_ms = {}
for tid, m in MAN.items():
    by_ms.setdefault(m["milestone"].split(" ")[0], []).append(tid)

for ms in MS_ORDER:
    tids = sorted(by_ms.get(ms, []))
    if not tids:
        continue
    full = MAN[tids[0]]["milestone"]
    lines = [f"## Objetivo\n\n{MS_GOAL[ms]}\n", "## Issues hijos\n"]
    for t in tids:
        m = MAN[t]
        marks = []
        if m["critical"]: marks.append("🔴 ruta critica")
        if "parallelizable" in m["labels"]: marks.append("⚡ paralelizable")
        if "security-invariant" in m["labels"]: marks.append("🛡️ invariante")
        suf = f" — _{', '.join(marks)}_" if marks else ""
        lines.append(f"- [{'x' if m['done'] else ' '}] #{NUM[t]} {t} · `{m['priority']}` · `{m['size']}`{suf}")
    done = all(MAN[t]["done"] for t in tids)
    box = "[x]" if done else "[ ]"
    lines += ["\n## Cierre del epico\n",
              f"- {box} Todos los issues hijos cerrados",
              f"- {box} CI en verde sobre la rama del milestone",
              f"- {box} Ningun invariante (INV-1 a INV-4) relajado en el camino",
              f"\n---\n<sub>Epico del milestone {full} · backlog en `specs/001-recomendaciones-precomputadas/tasks.md`</sub>"]
    p = BASE / f".issues/EPIC_{ms}.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    title = f"[{ms}] EPIC — {full.split(' - ', 1)[1]}"
    if ms in epics:
        act(f"EPIC {ms} -> editar #{epics[ms]}", "issue", "edit", str(epics[ms]), "--repo", REPO,
            "--title", title, "--body-file", str(p), "--milestone", full)
    else:
        out = act(f"EPIC {ms} -> crear", "issue", "create", "--repo", REPO, "--title", title,
                  "--body-file", str(p), "--milestone", full, "--label", "epic")
        if out:
            print("      ", out.splitlines()[-1])
            epics[ms] = out.splitlines()[-1].rsplit("/", 1)[1]
        epic_state[ms] = "OPEN"
    if done and epic_state[ms] == "OPEN":
        act(f"EPIC {ms} -> cerrar (hijos terminados)", "issue", "close", str(epics.get(ms, "?")), "--repo", REPO,
            "--reason", "completed", "--comment", "Todos los issues hijos del milestone están terminados.")
    elif not done and epic_state[ms] == "CLOSED":
        act(f"EPIC {ms} -> reabrir", "issue", "reopen", str(epics[ms]), "--repo", REPO,
            "--comment", "Hay issues hijos pendientes en el milestone.")
