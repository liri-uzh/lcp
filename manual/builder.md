# Corpus builder

The tool `lcpcli` ships with a helper python class `Corpus` to prepare LCP corpora.

The [tutorial](import_tutorial.md) uses the `Corpus` class to process SRT files and import a video corpus into LCP.

The various [tests in the `lcpcli` repository](https://github.com/liri-uzh/lcpcli/tree/main/tests) give concrete examples on how to use the `Corpus` class.

The following repositories also use the `Corpus` class to convert existing data sets:

 - [XML-to-LCP conversion of NOAH's Corpus](https://github.com/liri-uzh/lcpimport_noah_corpus)
 - [TEI-to-LCP conversion of OFROM](https://github.com/liri-uzh/lcpimport_ofrom)

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

## Instance methods

An instance of the `Corpus` class has an open set of methods, which should all start with a capital letter, and which will create and return an entity in the corpus with the passed attributes (an instance of the class `Layer`)

All corpora should create at least one entity by calling each of the methods named after the values passed as `document`, `segment` and `token` when instantiating the `Corpus` class.

**Example**

```python
from lcpcli.builder import Corpus

c = Corpus("my great corpus")

c.Document(
    c.Segment(
        c.Word("hello"),
        c.Word("world")
    )
)

c.make("path/to/output/")
```

### `make`

Writes all the CSV files and the configuration JSON file of the corpus to the passed directory.

The `make` method is the only valid method that starts with a non-capital letter.

Arguments:

 - `destination` (`str`, mandatory) is a path where to place the output files
 - `is_global` (`dict`, optional, default `{}`) maps layers to attribute names whose possible values are defined globally, such as the [`upos` on tokens](https://universaldependencies.org/u/pos/)

## `Layer` class

### Instance methods

#### `make`

#### `add`

#### `set_media`

#### `set_char`

#### `get_char`

#### `set_time`

#### `get_time`

#### `set_xy`

#### `get_xy`