# DQD: the `@` operator

The `@` operator essentially expresses a character-wise containment relation. As such, it can only be applied to entities that are character-aligned, for example tokens or segments (unlike gesture annotations of video corpora that, typically, are not character-aligned).

It is a binary operator: it uses the syntax `x@y`, where `y` is a label refering to the entity that should contain the one being declared by `x`.

`x` can be of two types. First, it can be the name of an annotation layer in the corpus. For example, the block below means that the adverb token `t1` should be part of the segment labeled `s`

 ```
 Segment s
    speaker.name = "Marcel"

 Token@s t1
    upos = "ADV"
```

Second, it can be the keyword [`sequence`](sequence.md), in which case all the entities declared within the scope of the sequence must be contained within the labeled entity. For example, the block below means that we are looking for a named entity contained in a segment, which itselfs contains the sequence "Monte Rosa":

```
Segment s

NamedEntity@s ne

sequence@ne seq
    Token
        form = "Monte"
    Token
        form = "Rosa"
```