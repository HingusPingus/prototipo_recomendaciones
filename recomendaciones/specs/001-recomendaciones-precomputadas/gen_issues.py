#!/usr/bin/env python3
"""
Genera issues de GitHub a partir de tasks.md.
El cuerpo se construye parseando el backlog: no se inventa trabajo.
"""
import re, json, subprocess, sys, pathlib

REPO = "HingusPingus/prototipo_recomendaciones"
BASE = pathlib.Path(__file__).resolve().parent
TASKS = BASE / "tasks.md"
OUT = BASE / ".issues"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- metadatos
# milestone, capa, tipo, prioridad, talla
META = {
 "T001": ("M1","infra","infra","P0-bloqueante","size-S"),
 "T002": ("M1","infra","infra","P0-bloqueante","size-M"),
 "T003": ("M1","database","infra","P0-bloqueante","size-L"),
 "T004": ("M1","engine","feature","P0-bloqueante","size-M"),
 "T005": ("M1","engine","feature","P1-alta","size-S"),
 "T006": ("M1","infra","test","P0-bloqueante","size-S"),
 "T007": ("M2","engine","feature","P0-bloqueante","size-M"),
 "T008": ("M2","engine","feature","P0-bloqueante","size-S"),
 "T009": ("M2","engine","feature","P1-alta","size-M"),
 "T010": ("M2","engine","feature","P1-alta","size-M"),
 "T011": ("M2","engine","feature","P1-alta","size-M"),
 "T012": ("M2","engine","feature","P0-bloqueante","size-M"),
 "T013": ("M3","engine","feature","P0-bloqueante","size-M"),
 "T014": ("M3","engine","feature","P0-bloqueante","size-M"),
 "T015": ("M3","engine","feature","P0-bloqueante","size-M"),
 "T016": ("M3","engine","feature","P0-bloqueante","size-M"),
 "T017": ("M3","engine","test","P0-bloqueante","size-L"),
 "T018": ("M4","cache","feature","P0-bloqueante","size-M"),
 "T019": ("M4","cache","feature","P0-bloqueante","size-S"),
 "T020": ("M4","cache","feature","P0-bloqueante","size-M"),
 "T021": ("M4","cache","feature","P1-alta","size-S"),
 "T022": ("M4","cache","feature","P1-alta","size-M"),
 "T023": ("M5","worker","feature","P1-alta","size-M"),
 "T024": ("M5","worker","feature","P1-alta","size-M"),
 "T025": ("M5","worker","feature","P2-media","size-M"),
 "T026": ("M5","worker","feature","P2-media","size-S"),
 "T027": ("M5","worker","feature","P1-alta","size-L"),
 "T028": ("M6","data-transformer","feature","P2-media","size-M"),
 "T029": ("M6","data-transformer","feature","P2-media","size-L"),
 "T030": ("M6","data-transformer","feature","P2-media","size-M"),
 "T031": ("M6","data-transformer","observability","P2-media","size-S"),
 "T032": ("M6","data-transformer","feature","P2-media","size-M"),
 "T033": ("M7","api","feature","P0-bloqueante","size-M"),
 "T034": ("M7","api","feature","P1-alta","size-M"),
 "T035": ("M7","api","feature","P1-alta","size-S"),
 "T036": ("M7","api","feature","P0-bloqueante","size-M"),
 "T037": ("M7","api","feature","P0-bloqueante","size-M"),
 "T038": ("M7","engine","feature","P0-bloqueante","size-M"),
 "T039": ("M8","observability","observability","P2-media","size-M"),
 "T040": ("M8","observability","observability","P2-media","size-M"),
 "T041": ("M8","observability","observability","P2-media","size-M"),
 "T042": ("M8","observability","observability","P2-media","size-M"),
 "T046": ("M8","observability","docs","P3-baja","size-M"),
 "T049": ("M9","api","docs","P0-bloqueante","size-M"),
 "T043": ("M9","api","test","P0-bloqueante","size-M"),
 "T044": ("M9","engine","test","P0-bloqueante","size-L"),
 "T045": ("M9","infra","infra","P0-bloqueante","size-M"),
 "T050": ("M9","api","test","P2-media","size-M"),
 "T047": ("M10","api","docs","P2-media","size-S"),
 "T048": ("M10","infra","docs","P1-alta","size-M"),
}

MILESTONES = {
 "M1":"M1 - Fundaciones", "M2":"M2 - Motor de recomendacion",
 "M3":"M3 - Post-procesamiento (invariantes)", "M4":"M4 - Persistencia y cache",
 "M5":"M5 - Worker asincrono", "M6":"M6 - Data Transformer",
 "M7":"M7 - API de lectura", "M8":"M8 - Observabilidad y operacion",
 "M9":"M9 - Testing y verificacion", "M10":"M10 - Cierre",
}

CRITICAL = ["T001","T004","T007","T008","T012","T015","T016","T019","T020",
            "T033","T036","T038","T037","T049","T043","T044","T045","T048"]
SECURITY = ["T013","T014","T017","T037","T044"]
TECHDEBT = ["T018","T014","T004","T019","T036","T020"]

INV = {
 "INV-1":"Cero computo pesado en el request path (FR-003, Principio III). La API no importa `engine/` ni consulta Postgres en el camino normal.",
 "INV-2":"Redis nunca es fuente de verdad (FR-065). Su perdida total debe ser recuperable desde Postgres.",
 "INV-3":"Filtro de edad y filtro de exclusion no admiten bypass ni desactivacion (FR-049 a FR-055).",
 "INV-4":"Sin acceso directo a bases de datos de otros repositorios (Principio I). Los contratos compartidos se consumen, no se redefinen unilateralmente (Principio II).",
}

# ---------------------------------------------------------------- parser
raw = TASKS.read_text(encoding="utf-8")
blocks = re.split(r"\n### (?=T\d{3})", raw)
tasks = {}
for b in blocks[1:]:
    tid = b[:4]
    head = b.split("\n", 1)[0]
    title = head.split("—", 1)[1].strip() if "—" in head else head
    tags = re.findall(r"\[(P|TDD)\]", head)
    body = b.split("\n", 1)[1]
    body = re.split(r"\n---\s*\n", body)[0]

    def grab(label):
        m = re.search(rf"\*\*{label}\*\*:(.*?)(?=\n\*\*|\n- \[ \]|\Z)", body, re.S)
        return m.group(1).strip() if m else ""

    desc  = grab("Descripción")
    files = grab("Archivos")
    dep   = grab("Dep\\.")
    acs   = re.findall(r"^- \[ \] (.+(?:\n      .+)*)$", body, re.M)
    tm = re.search(r"(\*\*(?:🔴 Paso 1 — Rojo|Tests)\*\*.*)", body, re.S)
    tests = tm.group(1).strip() if tm else ""
    tasks[tid] = dict(id=tid, title=title, tags=tags, desc=desc,
                      files=files, dep=dep, acs=acs, tests=tests)

# ---------------------------------------------------------------- cuerpos
def deps_of(tid):
    return sorted(set(re.findall(r"T\d{3}", tasks[tid]["dep"])))

def invariants_for(tid, layer):
    out = []
    if tid in SECURITY or layer == "engine": out.append("INV-3")
    if layer in ("api","cache") or tid in ("T006","T021","T037","T033","T050"): out.append("INV-1")
    if layer == "cache" or tid in ("T003","T022","T024"): out.append("INV-2")
    if layer in ("data-transformer","api","database") or tid in ("T002","T049","T047"): out.append("INV-4")
    return out or ["INV-4"]

def build(tid):
    t = tasks[tid]; ms, layer, kind, prio, size = META[tid]
    d = deps_of(tid)
    L = []
    L.append("## Contexto\n")
    L.append(t["desc"] or "_Ver `specs/001-recomendaciones-precomputadas/tasks.md`._")
    L.append(f"\n> Tarea **{tid}** del backlog aprobado, milestone **{MILESTONES[ms]}**.")
    if tid in CRITICAL:
        L.append("> ⚠️ **Esta tarea esta en la ruta critica.** Su retraso desplaza la fecha de entrega.")
    if "TDD" in t["tags"]:
        L.append("> 🔴 **Tarea test-first.** El commit de test debe preceder al de implementacion "
                 "en el historial de git. Un PR con un solo commit que traiga test e implementacion "
                 "juntos no demuestra haber visto el rojo y se rechaza.")
    L.append("\n## Alcance\n")
    L.append("**Entra**: lo descrito en *Trabajo a realizar* y verificable por los criterios de aceptacion.\n")
    L.append("**No entra**: cualquier cambio fuera de los archivos listados; optimizaciones no pedidas; "
             "modificar contratos compartidos de `api-general` (se consumen, no se redefinen); "
             "relajar cualquier invariante de la seccion *Restricciones no negociables*.")
    L.append("\n## Trabajo a realizar\n")
    L.append(f"**Archivos / modulos afectados**: {t['files'] or '_por definir en el PR_'}")
    if "TDD" in t["tags"]:
        L.append("\n1. 🔴 Escribir los tests de la seccion *Tests requeridos* y **verlos fallar**. Commit propio.")
        L.append("2. 🟢 Implementar lo minimo para pasar. Commit siguiente.")
        L.append("3. ♻️ Refactorizar sin tocar los tests.")
    else:
        L.append("\n1. Implementar segun los criterios de aceptacion.")
        L.append("2. Agregar los tests de la seccion *Tests requeridos*.")
        L.append("3. Verificar que los invariantes aplicables siguen en verde.")
    L.append("\n## Criterios de aceptacion\n")
    for a in t["acs"]:
        L.append(f"- [ ] {' '.join(a.split())}")
    L.append("\n## Tests requeridos\n")
    L.append(t["tests"] or "_Declarar en el PR: ninguna tarea de produccion se cierra sin test._")
    L.append("\n## Restricciones no negociables\n")
    for k in invariants_for(tid, layer):
        L.append(f"- **{k}** — {INV[k]}")
    L.append("\n## Dependencias\n")
    if d:
        for x in d:
            L.append(f"- [ ] {x} debe estar cerrado")
    else:
        L.append("- Ninguna. Puede arrancar de inmediato.")
    L.append("\n## Definition of Done\n")
    L.append("- [ ] Todos los criterios de aceptacion tildados")
    L.append("- [ ] Tests requeridos escritos y en verde en CI")
    if "TDD" in t["tags"]:
        L.append("- [ ] El historial muestra el commit de test **antes** del de implementacion")
    L.append("- [ ] Ningun invariante de la seccion de restricciones fue relajado")
    L.append("- [ ] Revision de codigo aprobada")
    L.append(f"\n---\n<sub>Generado desde `specs/001-recomendaciones-precomputadas/tasks.md` · tarea {tid}</sub>")
    return "\n".join(L)

def labels_for(tid):
    ms, layer, kind, prio, size = META[tid]
    ls = [kind, layer, prio, size]
    if tid in SECURITY: ls.append("security-invariant")
    if tid in TECHDEBT: ls.append("tech-debt")
    if "P" in tasks[tid]["tags"]: ls.append("parallelizable")
    if tid in CRITICAL: ls.append("critical-path")
    return sorted(set(ls))

def verb_title(tid):
    ms = META[tid][0]
    return f"[{ms}] {tid} — {tasks[tid]['title']}"

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    manifest = {}
    for tid in META:
        body = build(tid)
        (OUT / f"{tid}.md").write_text(body, encoding="utf-8")
        manifest[tid] = dict(title=verb_title(tid), milestone=MILESTONES[META[tid][0]],
                             labels=labels_for(tid), deps=deps_of(tid),
                             priority=META[tid][3], size=META[tid][4],
                             critical=tid in CRITICAL)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(f"OK: {len(manifest)} issues preparados en {OUT}")
