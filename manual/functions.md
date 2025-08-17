# Functions

This page lists functions that can be used in DQD.

## length

Argument: attribute of type `text` or `categorical`

Returns: length of the string value (`number`)

Example:

```
Token t
    length(form) > 3
```

## century

Argument: attribute of type `text` or `categorical` that encodes a date

Returns: number representing the century in the value (`number`)

Example:
```
Document d
    century(pubdate) >= 20
```

## decade

Argument: attribute of type `text` or `categorical` that encodes a date

Returns: number representing the decade in the value (`number`)

Example:

```
Document d
    decade(pubdate) < 90
```

## year

Argument: attribute of type `text` or `categorical` that encodes a date

Returns: number representing the year in the value (`number`)

Example:

```
Document d
    year(pubdate) > 1999
```

## month

Argument: attribute of type `text` or `categorical` that encodes a date

Returns: number representing the month in the value (`number`)

Example:

```
Document d
    month(pubdate) = 3
```

## day

Argument: attribute of type `text` or `categorical` that encodes a date

Returns: number representing the day in the value (`number`)

Example:

```
Document d
    day(pubdate) > 28
```

## position

Argument: entity that is character-aligned

Returns: the position of the entity in the corpus along the character axis (`number`)

Example:

```
Segment s

Token@s t

# match only the first token
position(t) = position(s)
```

## range

Argument: entity that is character-aligned

Returns: the number of characters that the entity spans along the character axis (`number`)

Example:

```
Segment s

Token@s t

# match only the last token
position(t) + range(t) >= position(s) + range(s) - 1
```

## start

Argument: entity that is time-aligned

Returns: the number in seconds at which the entity starts in the corpus (`number`)

Example:

```
Document d

Segment%d s

# match segments within the first second of their document
start(s) < start(d) + 1
```

## end

Argument: entity that is time-aligned

Returns: the number in seconds at which the entity ends in the corpus (`number`)

Example:

```
Document d

Segment%d s

# match segments within the last second of their document
end(s) > end(d) - 1
```
