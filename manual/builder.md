# Corpus builder

The tool `lcpcli` ships with a helper python class `Corpus` to prepare LCP corpora.

The [tutorial](import_tutorial_part1.md) uses the `Corpus` class to process SRT files and import a video corpus into LCP.

The following repositories also use the `Corpus` class to convert existing data sets:

 - [XML-to-LCP conversion of NOAH's Corpus](https://github.com/liri-uzh/lcpimport_noah_corpus)
 - [TEI-to-LCP conversion of OFROM](https://github.com/liri-uzh/lcpimport_ofrom)
 - [Conversion of Alto-XML scanned documents to LCP](https://github.com/liri-uzh/lcpimport_erara44085)

The various [tests in the `lcpcli` repository](https://github.com/liri-uzh/lcpcli/tree/main/tests) give concrete examples on how to use the `Corpus` class.

## `Corpus`

You need to instantiate the `Corpus` class to create a new corpus.

Arguments:

 - `name` (`str`, mandatory) is the name of the corpus
 - `document` (`str`, optional, default `"Document"`) is the name of the document-level layer of the corpus
 - `segment` (`str`, optional, default `"Segment"`) is the name of the sentence-level layer of the corpus
 - `token` (`str`, optional, default `"Token"`) is the name of the word-level layer of the corpus
 - `authors` (`str`, optional, default `"placeholder"`) is the name(s) of the author(s) of the corpus
 - `institution` (`str`, optional, default `""`) is the name of the institution associated with the corpus
 - `description` (`str`, optional, default `""`) is a description of the corpus, as it will be presented to end users
 - `date` (`str`, optional, default `"placeholder"`) is the date when the corpus was curated
 - `revision` (`int | float`, optional, default `1`) is the revision number of the corpus
 - `url` (`str`, optional, default `"placeholder"`) is the source URL of the corpus
 - `license` (`str | None`, optional, default `None`) is the code of the license of the corpus

The values of `authors`, `institution`, `description`, `date`, `revision`, `url` and `license` can be modified in LCP after import.

**Example**

```python
from lcpcli.builder import Corpus

c = Corpus("my great corpus", document="Book", segment="Sentence", token="Word")
```

### Instance methods

An instance of the `Corpus` class has an open set of methods, which should all start with a capital letter, and which will create and return an entity in the corpus with the passed attributes (an instance of the class `Layer`)

All corpora should create at least one entity by calling each of the methods named after the values passed as `document`, `segment` and `token` when instantiating the `Corpus` class.

**Example**

```python
from lcpcli.builder import Corpus

c = Corpus("my great corpus")

c.Document(
    c.Segment(
        c.Token("hello"),
        c.Token("world")
    )
)

c.make("path/to/output/")
```

#### `make`

Writes all the CSV files and the configuration JSON file of the corpus to the passed directory.

The `make` method is the only valid method on a `Corpus` instance that starts with a non-capital letter.

Arguments:

 - `destination` (`str`, mandatory) is a path where to place the output files
 - `is_global` (`dict`, optional, default `{}`) maps layers to attribute names whose possible values are defined globally, such as the [`upos` on tokens](https://universaldependencies.org/u/pos/)

## `Layer` class

This class is never instantiated explicitly (as in `Layer(...)`). Instances of the `Layer` class are returned by calling a method that starts with a capital letter on an instance of `Corpus`, or on another `Layer` instance.

Upon instantiation, pass named arguments to create corresponding attributes on the entity, as in `corpus.Document(title="my document", year=2026)`. There are three special instantiation cases:

1. When instantiating **tokens**, you should pass a string as the sole unnamed argument to represent the form, as in `corpus.Token("is", lemma="be")`.
2. When instantiating **segments**, you can pass token instances as unnamed arguments, as in `document.Segment(corpus.Token("hello"), corpus.Token("world"))`.
3. You can pass a dictionary as the sole unnamed argument (and _no_ named argument) to create a `GlobalAttribute` instance instead of a `Layer` instance, as in `corpus.Speaker({"id": "johndoe", "firstname": "John", "lastname": "Doe"})`

### Instance methods

Just like `Corpus` instances, `Layer` instances have an open set of methods, which should all start with a capital letter, and which will create and return a new `Layer` instance.

In addition, `Layer` instances come with the methods listed below.

#### `make`

If called with **no argument**: makes the instance in the destination corpus and will clear it from memory as soon as possible.

If call with **multiple unnamed arguments**: each argument should be a `Layer` instance with at least one attribute that points to another `Layer` instance. This is typically used for token dependency relation in a segment, as in:

```python
t1 = c.Token("the")
t2 = c.Token("cat")
s = c.Segment(t1, t2)
s.make()
c.DepRel.make(
    c.DepRel(dependent=t3, udep="root"),
    c.DepRel(head=t2, dependent=t1, udep="detj")
)
```

#### `add`

Adds a `Layer` instance as a child of the current instance.

Arguments:

 - `child`: a `Layer` instance

Example:

```python
s = c.Segment()
t = c.Token("hello")
s.add(t)
```

#### `set_media`

#### `set_char`

#### `get_char`

#### `set_time`

#### `get_time`

#### `set_xy`

#### `get_xy`

## `GlobalAttribute` class
