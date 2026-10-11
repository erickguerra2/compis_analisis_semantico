# Lenguaje intermedio TAC

El compilador traduce Compiscript a código de tres direcciones (TAC). La salida
canónica se obtiene con `Emitter.lines()`; no aplica optimizaciones ni plegado
de constantes. `Emitter.dump()` agrega sangría y, cuando corresponde, la
sección de literales string para consumo humano.

## Instrucciones

| Construcción | Forma canónica |
|---|---|
| binaria | `t0 = a + b` (`+ - * / % < <= > >= == !=`) |
| unaria | `t0 = neg a`, `t0 = not a` |
| copia | `x = y` |
| control | `L0:`, `goto L0`, `if x goto L0`, `ifFalse x goto L0` |
| funciones | `begin_func f`, `end_func f`, `param x`, `t0 = call f, 2`, `return x` |
| arreglos | `t0 = a[i]`, `a[i] = y`, `t0 = new_array n`, `bounds a, i`, `t0 = len a` |
| objetos | `t0 = new C`, `t0 = o.campo`, `o.campo = y` |
| strings | `t0 = concat a, b`, `t0 = to_str a` |
| excepciones | `try_begin L0`, `try_end`, `throw .str0`, `catch err` |
| salida | `print x` |

La división de enteros trunca. `==` y `!=` comparan el valor de enteros y
booleanos, pero la identidad de referencias para strings, arreglos y objetos.

## Operandos y nombres

- Las constantes se imprimen como `5`, `true`, `false` y `null`. Un negativo
  escrito en el fuente se conserva como operación, por ejemplo `t0 = neg 3`.
- Los temporales son `t0`, `t1`, ... y reinician en cada unidad de código.
- Las etiquetas son globales (`L0`, `L1`, ...) y nunca reinician.
- Cada texto se interna una sola vez como `.str0`, `.str1`, ... en orden de
  aparición y queda disponible en `emitter.strings`.
- Las declaraciones homónimas se distinguen por orden: `x`, `x_1`, `x_2`.
- El programa principal se llama `main`; las funciones anidadas usarán
  `externa.interna`, los métodos `Clase.metodo` y los constructores
  `Clase.constructor`. `this` conserva ese nombre.

## Temporales

El pool entrega siempre el identificador libre más pequeño. Solo se liberan
temporales. En operaciones unarias y binarias se evalúan los operandos, se
liberan y después se solicita el resultado, lo que permite reutilizar un id:

```text
t0 = a * b
t1 = c * d
t0 = t0 + t1
```

La construcción que consume un operando es responsable de liberarlo. Al final
de cada sentencia debe haber tantos temporales vivos como al inicio. El
cortocircuito y el ternario reservan primero su temporal resultado para que las
ramas no puedan reutilizarlo.

## Expresiones y declaraciones

Las variables y constantes se usan directamente. Por ejemplo:

```text
begin_func main
t0 = 3 * 2
t0 = 5 + t0
x = t0
print x
end_func main
```

Una declaración sin inicializador recibe `0` si es `integer`, `false` si es
`boolean` y `null` en cualquier otro caso. Las asignaciones son expresiones:
`a = b = 3` produce `b = 3` seguido de `a = b`.

Para `a && b`, el resultado se copia antes del salto y el lado derecho solo se
evalúa si hace falta:

```text
r = a
ifFalse r goto Lend
r = b
Lend:
```

`||` usa `if r goto Lend`. El ternario reserva `r`, evalúa la condición, salta
a la rama falsa con `ifFalse`, y hace que ambas ramas copien su valor a `r`.

Si el resultado de `+` es string, se emite `concat`. Todo operando integer,
boolean o null se convierte previamente mediante `to_str`.

## Estructuras de control

La condición de `if`, `while`, `do-while` y `for` se evalúa a un operando, se
usa en el salto y se libera. Si la condición es una variable se usa
directamente, sin copiarla a un temporal. Las etiquetas de cada construcción se
numeran en el orden en que aparecen en su patrón.

`if` con `else`; sin `else` el salto va directo a `Lend` y no hay `goto`:

```text
<cond → c>
ifFalse c goto Lelse
<then>
goto Lend
Lelse:
<else>
Lend:
```

`while` (`continue` salta a `Lstart`, `break` a `Lend`):

```text
Lstart:
<cond → c>
ifFalse c goto Lend
<cuerpo>
goto Lstart
Lend:
```

`do-while` (`continue` salta a `Lcont`, `break` a `Lend`):

```text
Lstart:
<cuerpo>
Lcont:
<cond → c>
if c goto Lstart
Lend:
```

`for` (`continue` salta a `Lcont`, `break` a `Lend`). La condición y la
actualización son opcionales; sin condición no se emite el `ifFalse`:

```text
<init>
Lstart:
<cond → c>
ifFalse c goto Lend
<cuerpo>
Lcont:
<actualización>
goto Lstart
Lend:
```

Por ejemplo, `for (let i = 0; i < 3; i = i + 1) { print(i); }` produce:

```text
i = 0
L0:
t0 = i < 3
ifFalse t0 goto L2
print i
L1:
t0 = i + 1
i = t0
goto L0
L2:
```

`switch` evalúa su expresión una sola vez y la compara con cada `case` en
orden. El operando de la expresión se mantiene vivo durante las comparaciones:

```text
<expr → s>
t = s == <expr del case 0>
if t goto Lcase_0
t = s == <expr del case 1>
if t goto Lcase_1
goto Ldefault
Lcase_0:
<cuerpo del case 0>
Lcase_1:
<cuerpo del case 1>
Ldefault:
<cuerpo del default>
Lend:
```

Sin `default`, el salto posterior a las comparaciones va a `Lend`. Entre los
cuerpos no hay saltos, así que la ejecución cae al siguiente `case`
(fall-through) hasta encontrar un `break`. `break` sale de la construcción más
cercana, sea ciclo o `switch`; `continue` dentro de un `switch` va al ciclo que
lo contiene.

## Excepciones

| Instrucción | Significado |
|---|---|
| `try_begin L0` | registra `L0` como handler activo |
| `try_end` | desregistra el handler activo más reciente |
| `throw .str0` | salta al handler activo con el string como mensaje; sin handler, el programa termina e imprime el mensaje |
| `catch err` | primera instrucción de un handler: guarda el mensaje en `err` |

`try/catch`:

```text
try_begin Lcatch
<bloque try>
try_end
goto Lend
Lcatch:
catch err
<bloque catch>
Lend:
```

La variable del `catch` es de tipo `string`, ya está inicializada y solo existe
dentro del bloque `catch`. Si su nombre ya estaba en uso, se renombra como
cualquier otra declaración (`err_1`).

Un `break` o `continue` que abandona un `try` emite antes del `goto` un
`try_end` por cada `try` abierto desde que se entró al ciclo o `switch` de
destino, para que no queden handlers registrados:

```text
try_begin L2
t0 = i == 2
ifFalse t0 goto L4
try_end
goto L1
L4:
try_end
goto L3
L2:
catch e
print e
L3:
```

Un salto que no sale del `try` (por ejemplo, el `break` de un ciclo que está
dentro del bloque `try`) no emite `try_end`.

## Supuestos

- Las funciones no son valores de primera clase.
- No se comprueba división entre cero.
- El despacho de métodos será estático según el tipo declarado.
- Un programa con errores léxicos, sintácticos o semánticos no genera TAC.
