# Control Cartera Provincia de Maipo

Panel y scripts para controlar los proyectos de la Provincia de Maipo (Paine, San Bernardo, Calera de Tango, Buin): estado de proyectos, transferencias y rendiciones Sub 33, pagos Sub 22/29/31, contratos y vigencias, licitaciones de Mercado Público, ruta documental SGD y casos de borde de la Ley de Compras Públicas.

Este repositorio guarda solo código y documentación. Las planillas y los datos generados quedan fuera (ver `.gitignore`).

## Contenido
| Ruta | Qué es |
|---|---|
| `panel/cartera-maipo.html` | El panel (se publica como `index.html` del artefacto "Cartera Provincia de Maipo") |
| `panel/build_data.py` | Arma los datos del panel desde la planilla de proyectos y los archivos de transferencias y pagos |
| `panel/ledger.py` | Libro de movimientos, historial y cuadratura entre cargas |
| `panel/build_sgd.py` | Procesa la exportación SGD (`sgd_todos_fechas-DD-MM-AAAA.xls`) |
| `panel/diff_data.py` | Compara dos cargas |
| `panel/daily_summary.py` | Resumen diario |
| `panel/mercadopublico/` | Consulta de licitaciones por BIP (requiere la variable `MERCADOPUBLICO_TICKET`) |
| `normativa-compras-publicas.md` | Referencia de la Ley 19.886 / Ley 21.634 y DS 661 usada para validar casos de borde |

## Proceso semanal (manual, viernes)
1. Exportar la planilla de proyectos (Sub 33 y Sub 22/29/31), transferencias-rendiciones, pagos 31 SAGIR, pagos enviados y efectuados DAF 31/33 y SGD.
2. Ejecutar `build_data.py`, luego `ledger.py` y `build_sgd.py`.
3. Publicar `index.html` y `data/sistema.json` en el artefacto. El panel copia el paquete a su base la primera vez que lo abre alguien con permiso de edición.

El ticket de Mercado Público nunca se guarda en el repositorio.
