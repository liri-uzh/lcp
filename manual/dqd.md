# The DQD Query Language

> For a list of keywords used in DQD, see [DQD keywords](keywords.md)

## Introduction

LCP's query language _DQD_ (**D**escriptive **Q**uery **D**efinition) follows the idea of [Entity-Relationship models](https://en.wikipedia.org/wiki/Entity%E2%80%93relationship_model). A DQD query defines sets of entities by listing logical constraints on their properties and on their relations to one another. The query engine then searches for those constellations of entities inside the selected corpus or corpora. Along the lines of first order logic, DQD includes quantors, which can be employed to enforce the existence or non-existence of constellations.

In addition to the declaration of sets of entities and their constraints, every query needs to specify at least one result set, which is either a (plain) list of entities comprising the query matches, a statistical or a collocational analysis.


## Getting started

In a text corpus with standard annotations (viz the [CoNLL-U format](https://universaldependencies.org/format.html)), a simple query for the occurrence of the word "dogs" would look like this:
```
Segment s

Token@s t
    form = "dogs"

result => plain
    context
        s
    entities
        t
```

We proceed to explain this simple query below.

### Instantiation and Scopes

Entities are instantiated by providing the name of their [annotation layer](model.md#layers), followed by a (unique) label, which can be used to reference the entitiy later on. The simple line `Segment s` instantiates an entity labeled `s` on the annotation layer `Segment`.

> LCP allows corpus creators to use arbitrary annotation layer names, but `Token` and `Segment` are common default names. You can see the annotation layers in a corpus by looking at [its diagram](corpora_in_lcp.md#diagram) and reference them in your DQD query.

An entity is by default existantially quantified, and its scope ranges from its instanciation to the end of the query. This means that the query will only output results where a matching entity was found, and that occurrences of its label will refer back it anywhere in the query below its instantiation line. 

> Some exceptions exist, for example when entities are instantiated within the scope of a negative existential quantifier, or within the scope of a repeatable [sequence](sequence.md). We will touch on those later.

The code above declares a second entity, labeled `t`, on the annotation layer named `Token`. The character-containment operator [`@`](at.md) requires that the current entity (the token labeled `t`) be part of the entity whose label appears to the right of the operator (the segment labeled `s`). The use of this operator will become apparent later.

Scope is controled via **indentation**: in the code above, the constraint `form = "dogs"` is in the scope of the token instantiation, but the line that comes next (`result => plain`) is not in that scope, because the line was de-dented.

## Constraints

Simple constraints usually use the format `left operator right` and are interpreted in the scope 
. The constraint in the example above respects this schema, where `left` is `form`, `operator` is `=` and `right` is `"dogs"`. LCP allows corpus creators to define arbitrary attributes for each layer, but `form` is mandatory on the token-level attribute. Because the constraint is in the scope of the token, `form` refers to the token attribute named "form": this constraint states that we are looking for token entities whose form must be "dogs". 

Annotation layers can come with any number of attributes, but it is standard for tokens to also define an attribute named `lemma`. Had we used the constraint `lemma = "dog"` instead, we would have matched token occurrences whose form could be either "dog" or "dogs".

> Attributes can have different types; in this illustration, both `form` and `lemma` are assumed to be strings. Accordingly, we surround the test value in double quotes. DQD does **not** accept string surrounded by single quotes. You can see the attributes of the annotation layers in a corpus by looking at [its diagram](corpora_in_lcp.md#diagram) and reference them in your DQD query.

### Regular expressions

In addition to plain strings, DQD supports references to regular expressions by enclosing a string in forward slashes (`/`). For example, the constraint `form = /^[Dd]ogs?$/` expresses that the form should be exactly one of "dog", "Dog", "dogs" or "Dogs".


## Sequences

To look for consecutive entities, such as a series of tokens, one can use the keyword [`sequence`](sequence.md).

## Sets

By default, each entity produce one match for each occurrence in the corpus. For example, if one sentence contains three occurrences of "dogs", the results will report three distinct hits for that sentence. To prevent that behavior, one can use the keyword [`set`](set.md).

## Results

DQD queries come with a constraint part, and a results part. There are three types of results:

 1. [`plain`](results.md#plain)
 2. [`analysis`](results.md#analysis)
 3. [`collocation`](results.md#collocation)