# SCRUM-20 — Selección de herramienta de automatización

## Objetivo

Evaluar y seleccionar la herramienta de automatización de configuración
para el proyecto VITALIA entre las opciones **Ansible**, **Puppet** y **Chef**.

### Ansible

- **Modelo:** sin agente (usa SSH).
- **Lenguaje:** YAML.
- **Curva de aprendizaje:** baja.
- **Ventajas:**
  - No requiere instalar agentes en los nodos gestionados.
  - Sintaxis legible y fácil de mantener.
  - Excelente integración con Docker y pipelines de CI/CD.
  - Comunidad y documentación muy amplias.
- **Desventajas:**
  - Menos potente que Puppet/Chef para configuraciones muy complejas
    a gran escala.

### Puppet

- **Modelo:** con agente.
- **Lenguaje:** DSL propio (basado en Ruby).
- **Curva de aprendizaje:** media-alta.
- **Ventajas:**
  - Robusto en entornos grandes y heterogéneos.
  - Modelo declarativo maduro.
- **Desventajas:**
  - Requiere desplegar y mantener agentes en cada nodo.
  - Mayor complejidad operativa.

### Chef

- **Modelo:** con agente.
- **Lenguaje:** Ruby.
- **Curva de aprendizaje:** alta.
- **Ventajas:**
  - Muy flexible y potente.
  - Gran ecosistema de "cookbooks".
- **Desventajas:**
  - Mayor complejidad inicial.
  - Requiere conocimientos sólidos de Ruby.

## Decisión

Se selecciona **Ansible** como herramienta de automatización para VITALIA,
con base en los siguientes criterios:

1. **Simplicidad operativa:** no requiere instalar agentes en los servidores,
   solo acceso SSH.
2. **Curva de aprendizaje baja:** su sintaxis YAML facilita la incorporación
   del equipo.
3. **Integración con el stack actual:** se adapta bien al uso de Docker y
   pipelines de CI/CD ya existentes en el proyecto.
4. **Comunidad y soporte:** es actualmente el estándar de facto para
   automatización de configuración en proyectos modernos.
