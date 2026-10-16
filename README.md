# Landings 3D

Dos landings de producto con 3D interactivo, modeladas por código en Blender y animadas con Three.js.

| Página | Qué hace |
|---|---|
| [`morvic.html`](morvic.html) | Reloj automático que se despieza con el scroll: esfera, lume, calibre en movimiento, corona para dar cuerda, rotor con física y configurador. |
| [`gambito.html`](gambito.html) | Ajedrez: el scroll reproduce la partida de la Ópera de Morphy (1858), anatomía del caballo, configurador y partida contra una IA. |

Son marcas conceptuales: nombres, precios y especificaciones son inventados.

## Verlo

Abre `index.html` con doble clic: los modelos van incrustados en `assets/3d/*-data.js`, así que funciona sin servidor. Necesita internet para cargar Three.js, chess.js y las fuentes desde CDN.

En Vercel no hace falta configurar nada: es un sitio estático (Framework Preset: Other, sin comando de build).

## Regenerar los modelos

Los scripts de `blender/` construyen cada modelo desde cero en Blender 5.2 y exportan el `.glb` a `assets/3d/`:

```python
p = r'...\landings-3d\blender\gambito.py'
exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), {'__name__': '__main__'})
```

Después hay que volver a incrustar el `.glb` en base64 dentro del `-data.js` correspondiente.
