#!/usr/bin/env python3
"""
Sincroniza los issues de tarea con GitHub a partir de .issues/manifest.json (lo genera gen_issues.py).

Idempotente de verdad: cada tarea se busca por su ID en el título de los issues existentes. Si existe,
se actualiza (título, cuerpo, milestone y etiquetas); si no, se crea. Nunca se crea un duplicado.
El milestone se asigna por la API REST y por número: `gh issue edit --milestone` no encuentra un milestone
cerrado, y link_and_epics.py cierra el de todo épico terminado.
Además crea los milestones y etiquetas que falten y cierra como «no planeado» el issue de toda tarea
retirada (hoy T036). El estado sigue al índice de tasks.md: el issue de una tarea tildada (`- [X]`) se cierra
como completado y el de una tarea destildada se reabre.

Uso:  python publish_issues.py            -> muestra el plan, no toca GitHub
      python publish_issues.py --apply    -> ejecuta el plan
Requiere `gh` autenticado (`gh auth login`).

Reemplaza a publish_issues.sh, que decía ser idempotente pero truncaba created.tsv y ejecutaba
`gh issue create` para todas las tareas: una segunda corrida duplicaba #1–#50.
"""
import json, pathlib, re, shutil, subprocess, sys

REPO = "HingusPingus/prototipo_recomendaciones"
BASE = pathlib.Path(__file__).resolve().parent
MAN = json.loads((BASE / ".issues/manifest.json").read_text(encoding="utf-8"))
MAP = BASE / ".issues/created.tsv"
APPLY = "--apply" in sys.argv
RETIRED = {"T036": "Tarea retirada el 2026-09-27 (RD-95): el endpoint de feedback se eliminó y su "
                   "trabajo pasó a T064. Se cierra como no planeada; el número no se reutiliza."}
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"

# Familias de etiquetas que este script administra: solo éstas se quitan si dejan de corresponder.
MANAGED = {"infra", "feature", "test", "docs", "observability", "refactor",
           "api", "cache", "data-transformer", "database", "engine", "worker",
           "P0-bloqueante", "P1-alta", "P2-media", "P3-baja", "size-S", "size-M", "size-L",
           "security-invariant", "tech-debt", "parallelizable", "critical-path"}


def gh(*args):
    r = subprocess.run([GH, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(f"ERROR gh {' '.join(args[:3])}: {r.stderr.strip()}")
    return r.stdout


def main():
    gh("auth", "status")
    issues = json.loads(gh("issue", "list", "--repo", REPO, "--state", "all", "--limit", "1000",
                           "--json", "number,title,state,labels,milestone"))
    by_tid = {}
    for i in issues:
        m = re.search(r"\] (T\d{3}) —", i["title"])
        if m:
            by_tid.setdefault(m.group(1), []).append(i)
    dups = {k: [i["number"] for i in v] for k, v in by_tid.items() if len(v) > 1}
    if dups:
        sys.exit(f"ERROR: tareas con más de un issue, resolver a mano antes de seguir: {dups}")
    by_tid = {k: v[0] for k, v in by_tid.items()}

    have_ms = {m["title"] for m in json.loads(gh("api", f"repos/{REPO}/milestones?state=all&per_page=100"))}
    need_ms = sorted({m["milestone"] for m in MAN.values()} - have_ms)
    have_lb = {l["name"] for l in json.loads(gh("label", "list", "--repo", REPO, "--limit", "300", "--json", "name"))}
    need_lb = sorted({l for m in MAN.values() for l in m["labels"]} - have_lb)

    plan = [("milestone", ms) for ms in need_ms] + [("label", lb) for lb in need_lb]
    for tid in sorted(MAN):
        m = MAN[tid]
        if tid in by_tid:
            cur = by_tid[tid]
            curl = {l["name"] for l in cur["labels"]}
            plan.append(("edit", tid, cur["number"], sorted(set(m["labels"]) - curl),
                         sorted((curl & MANAGED) - set(m["labels"]))))
        else:
            plan.append(("create", tid))
        if (by_tid.get(tid, {}).get("milestone") or {}).get("title") != m["milestone"]:
            plan.append(("setms", tid))
        state = by_tid.get(tid, {}).get("state", "OPEN")
        if m["done"] and state == "OPEN":
            plan.append(("done", tid))
        elif not m["done"] and state == "CLOSED" and tid not in RETIRED:
            plan.append(("reopen", tid))
    for tid, why in RETIRED.items():
        if tid in by_tid and by_tid[tid]["state"] == "OPEN":
            plan.append(("close", tid, by_tid[tid]["number"], why))

    for p in plan:
        if p[0] == "edit":
            extra = (f" +{p[3]}" if p[3] else "") + (f" -{p[4]}" if p[4] else "")
            print(f"   edit {p[1]} #{p[2]}{extra}")
        elif p[0] == "close":
            print(f"   close {p[1]} #{p[2]}")
        else:
            print("  ", *p[:2])
    print(f"--- {len(plan)} acciones ({'se ejecutan' if APPLY else 'modo simulación: agregar --apply'}) ---")
    if not APPLY:
        return

    for p in plan:
        kind = p[0]
        if kind == "milestone":
            gh("api", f"repos/{REPO}/milestones", "-f", f"title={p[1]}")
        elif kind == "label":
            gh("label", "create", p[1], "--repo", REPO)
        elif kind == "edit":
            _, tid, num, add, rem = p
            m = MAN[tid]
            args = ["issue", "edit", str(num), "--repo", REPO, "--title", m["title"],
                    "--body-file", str(BASE / f".issues/{tid}.md")]
            for l in add: args += ["--add-label", l]
            for l in rem: args += ["--remove-label", l]
            gh(*args)
        elif kind == "create":
            tid = p[1]; m = MAN[tid]
            url = gh("issue", "create", "--repo", REPO, "--title", m["title"],
                     "--body-file", str(BASE / f".issues/{tid}.md"),
                     "--label", ",".join(m["labels"])).strip().splitlines()[-1]
            by_tid[tid] = {"number": int(url.rsplit("/", 1)[1]), "url": url}
        elif kind == "close":
            gh("issue", "close", str(p[2]), "--repo", REPO, "--reason", "not planned", "--comment", p[3])
        elif kind == "setms":
            ms_num = {x["title"]: x["number"] for x in json.loads(gh("api", f"repos/{REPO}/milestones?state=all&per_page=100"))}
            gh("api", "-X", "PATCH", f"repos/{REPO}/issues/{by_tid[p[1]]['number']}",
               "-F", f"milestone={ms_num[MAN[p[1]]['milestone']]}")
        elif kind == "done":
            gh("issue", "close", str(by_tid[p[1]]["number"]), "--repo", REPO, "--reason", "completed",
               "--comment", "Tarea tildada en tasks.md: implementada y en `main`.")
        elif kind == "reopen":
            gh("issue", "reopen", str(by_tid[p[1]]["number"]), "--repo", REPO,
               "--comment", "La tarea volvió a quedar abierta en tasks.md.")
        print("ok", *p[:2])

    rows = [f"{tid}\t{by_tid[tid]['number']}\thttps://github.com/{REPO}/issues/{by_tid[tid]['number']}"
            for tid in sorted(MAN)]
    MAP.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"--- {len(rows)} tareas mapeadas en {MAP.name} ---")


if __name__ == "__main__":
    main()
