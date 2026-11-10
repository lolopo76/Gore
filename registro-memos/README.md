# Registro de memos y gestiones

Página para registrar los memos de las unidades técnicas (Paine, San Bernardo, Buin, Calera de Tango) y sacar el informe mensual de gestión para remuneraciones. Reemplaza la planilla en papel (BIP, IDDOC, Fecha SAGIR, DEIN/DAF, Memo U.T. N°, Fecha, U.T., Materia, Carga SAGIR).

- `index.html`: la página (sin dependencias; funciona en GitHub Pages o abriéndola desde el repositorio publicado).
- `data/registro.json`: el registro. Cada vez que se guarda una gestión desde la página queda un commit en este archivo, así el historial queda en git.

## Uso
1. Abrir la página publicada (GitHub Pages del repositorio, carpeta `registro-memos/`).
2. Pulsar **⚙ GitHub** y pegar un token *fine-grained* con permiso **Contents: Read and write** solo sobre este repositorio. El token queda en el navegador, nunca en el repositorio. Sin token la página funciona en modo lectura y guarda los cambios solo en ese navegador.
3. **Registro**: `+ Nueva gestión`, o clic en una fila para editarla. Al escribir el BIP se muestra el proyecto y se completa la U.T.
4. **Informe mensual**: elegir mes, año y U.T. y pulsar *Imprimir / Guardar PDF*.
5. **Resumen anual**: gestiones, cargas SAGIR, tipos y montos por mes.

El mes de cada gestión se toma de la Fecha SAGIR; si falta, de la fecha del memo U.T. Colores de fila: verde = cargado en SAGIR, celeste = pendiente SAGIR, turquesa (#27DDF5) = garantía, fucsia = monto sobre $200.000.000, rojo = rectificación (cuando Materia, Asociado u Obs. dicen "rectifica" o "rectificación"). Prioridad: rojo, luego fucsia, luego turquesa, luego verde/celeste. Las filas con ⚠ están "por revisar" (datos del historial en papel que no se leían con claridad).

> El repositorio es público: lo que se guarde en `data/registro.json` (números de memo, BIP, montos, observaciones) es visible para cualquiera.
