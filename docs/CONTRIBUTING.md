# Convención de contribuciones

Para que la autoría individual sea visible, cada integrante trabaja desde su propia rama y abre
su propio pull request. No se comparten commits ni se reutiliza la identidad Git de otra persona.

## Ramas

Usar el formato `nombre/tipo-descripcion`, por ejemplo:

```text
jose/feat-ide
ana/test-clases
luis/docs-instalacion
```

Tipos sugeridos: `feat`, `fix`, `test`, `docs` y `chore`. Las ramas parten de `main`, tienen un
alcance pequeño y vuelven mediante pull request después de que CI esté verde.

## Commits

Usar mensajes imperativos con el mismo prefijo:

```text
feat: valida constructores de clases
test: cubre acceso a miembros heredados
docs: explica cómo ejecutar el IDE
```

Antes de publicar una rama:

```bash
python -m pytest -q
git status
git log --oneline main..HEAD
```

El autor debe revisar que `user.name` y `user.email` correspondan a su propia cuenta de GitHub.
No se recomienda hacer squash entre contribuciones de distintas personas porque ocultaría la
autoría que el curso evaluará.
