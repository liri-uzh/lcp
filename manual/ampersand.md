# DQD: the `&` operator

The `&` operator expresses a location-wise overlap relation. As such, it can only be applied to entities that are location-aligned.

It is a binary operator: it uses the syntax `x&y`, where `x` and `y` are labels referring to entities that should overlap on the location plane.

`x` can be of two types. First, it can be the name of an annotation layer in the corpus. For example, the block below means that the smudge `s` should be part of the page labeled `p`

```
Page p

Smudge&p s
```

Second, it can be the keyword [`sequence`](sequence.md), in which case all the entities declared within the scope of the sequence must be contained (location-wise) within the labeled entity. For example, the block below means that we are looking for a named entity contained (location-wise) in a segment, which itselfs contains the sequence "Monte Rosa":

```
Segment s

NamedEntity&s ne

sequence&ne seq
    Token
        form = "Monte"
    Token
        form = "Rosa"
```

Note that such a query only makes sense in a corpus where tokens, named entities and segments have all been aligned on the location plane, which is not the case for all corpora that define a location plane.