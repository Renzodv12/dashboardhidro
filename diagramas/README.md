# Diagramas PlantUML

Esta carpeta contiene diagramas entidad relacion basados en el esquema real de
SQLite del sistema hidroponico.

Archivos:

- `er-completo.puml`: modelo completo de la base de datos.
- `er-monitoreo-control.puml`: vista enfocada en sensores, dispositivos,
  alertas y control PID.
- `er-seguridad-evidencias.puml`: vista enfocada en usuarios, auditoria,
  vision, metricas y respaldos operativos.
- `DICCIONARIO_DATOS.md`: explicacion de cada tabla, columna, clave e indice
  relevante del modelo.

Para renderizar con PlantUML:

```bash
plantuml diagramas/*.puml
```

Si no esta instalado, tambien se pueden abrir los archivos `.puml` con una
extension de PlantUML en VS Code o copiarlos en un visor PlantUML compatible.
