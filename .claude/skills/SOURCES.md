# Origen de las skills de terceros

Copiadas a mano (revisado el `SKILL.md` antes de instalar; solo contienen instrucciones en Markdown, sin scripts).
Para actualizar: volver a clonar, revisar el diff y anotar el commit nuevo aquí y en ADR-008.

| Skill | Repositorio | Commit | Licencia | Fecha |
|---|---|---|---|---|
| `interface-design` | https://github.com/Dammyjay93/interface-design (`.claude/skills/interface-design`, `reference/` y `.claude/commands/` → `.claude/commands/interface-design/`) | `2f9be3206855bcb2d1d0af262c8bae25cba6658d` | MIT (`interface-design/LICENSE`) | 15-nov-2026 |
| `web-interface-guidelines` | https://github.com/vercel-labs/web-interface-guidelines (`command.md` copiado como `SKILL.md`, con encabezado propio) | `434b7f91364665f2f733b310ec54809bf8f37937` | MIT (`web-interface-guidelines/LICENSE`) | 15-nov-2026 |
| `emil-design-eng` | https://github.com/emilkowalski/skill (`skills/emil-design-eng`) | `64eb3deb9a5fbfa041faf783e0bc3fd635872e9c` | MIT (`emil-design-eng/LICENSE`) | 15-nov-2026 |
| `frontend-design` | https://github.com/anthropics/skills (`skills/frontend-design`) | `1780c5e5a552fd4d1c9d6a7b0cab26b0c2bef064` | Apache-2.0 (`frontend-design/LICENSE.txt`) | 15-nov-2026 |

`caterin-brand` es propia del proyecto. El archivo de memoria que pide `interface-design` es
`.interface-design/system.md`, en la raíz del repositorio.

## Retiradas o descartadas (15-nov-2026)

| Skill | Decisión | Motivo |
|---|---|---|
| `material-3` (hamen, commit `14385f2`) | **Retirada** | Pensada para Jetpack Compose; empujaba a la estética MD3 por defecto (píldoras, contenedores pastel). Se mantienen solo los nombres de rol de color en `index.css` |
| `anti-ui-slop` (UIZZE, en `.agents/skills/`) | No adoptada | Sus guías gratuitas repiten lo que cubre `interface-design`; su política pide ocultar al usuario cuándo falló su servicio pagado (choca con AGENTS.md, sección 10) y la licencia declarada (MIT) no coincide con el archivo `LICENSE` (Apache-2.0) |
| `web-design-guidelines` (vercel-labs/agent-skills) | No adoptada; en su lugar `web-interface-guidelines` | Descarga las reglas de una URL sin versión fija en cada uso. Se copió el archivo de reglas con commit fijo |
| `impeccable` (pbakaus) | No adoptada | Trae ejecutables y scripts de navegador (~2 MB); más superficie de la que hace falta |

