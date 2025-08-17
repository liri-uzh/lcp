# DQD: the `%` operator

The `%` operator expresses a time-wise overlap relation. As such, it can only be applied to entities that are time-aligned.

It is a binary operator: it uses the syntax `x%y`, where `x` and `y` are labels referring to entities that should overlap along the time axis. In the particular case where `x` refers to a parent of the annotation unit referred to by `y`, for example a Document-Segment relation, the `%` operator essentially expresses a _containment_ relation.

`x` can be of two types. First, it can be the name of an annotation layer in the corpus. For example, the block below means that the segment `s` should be part of the document labeled `d`

```
Document d
    year(date) > 2000

Segment%d s
    speaker.age > 20
```

Second, it can be the keyword [`sequence`](sequence.md), in which case all the entities declared within the scope of the sequence must be contained (time-wise) within the labeled entity. For example, the block below means that we are looking for a named entity contained (time-wise) in a segment, which itselfs contains the sequence "Monte Rosa":

```
Segment s

NamedEntity%s ne

sequence%ne seq
    Token
        form = "Monte"
    Token
        form = "Rosa"
```

Note that such a query only makes sense in a corpus where tokens, named entities and segments have all been aligned along the time axis, which is not the case for all corpora that define a time axis.

See [the *functions* page](functions.md) to learn how to target more fine-grained time information.