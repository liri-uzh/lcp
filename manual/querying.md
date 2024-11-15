# Querying

![LCP querying](images/lcp-query.png)

To start querying, you need to select "Query" option from navigation bar at the top of the page.

Once you are in the query interface, ensure that the corpus you want to query is selected. To write your query you will need to use DQD (Descriptive Query Definition) language. 

## The DQD language

DQD is a linguistic query language designed specifically for use in LCP and its ecosystem. Like other such languages (TGrep, CQL, AQL, etc.), DQD is designed to allow users to build complex queries on parsed/annotated corpora, and specify the format in which query results should be provided.

For DQD, a key concept was the Entity relationship (ER) model used for modeling data structures in software development, especially for database schemata. For corpora hosted by our infrastructure, the structure needs to be defined in terms of entities (plus their attributes and attribute types), and relations between them. [In detailed DQD documentation](dqd.md) you can find more information about how to make queries using DQD or how to translate CQP into DQD. On this page, we provide a more general introduction to the main components of the DQD language.

Aside from selecting a corpus, for multilingual corpora, you can select the language from a dropdown menu. In a future version, language selection will become part of the DQD query syntax.

All that remains at this point is to write and submit a query in DQD syntax. The simplest way to understand the language is to break it into two parts:

1. The query definition, or *constraints*
2. The format for results

As a simple initial example, the following query would search a corpus for the verb lemma `race`, viewed as a simple KWIC/concordance.

```
Segment sent

Token@sent raceProcess
  upos = "VERB"
  lemma = "race"

KWIC => plain
  context
    sent
  entities
    raceProcess
```

You can see immediately that in comparison to most linguistic query languages, DQD is fairly verbose. The advantage of this is that components of the query can be given labels and referred to elsewhere (`sent`, `raceProcess`). As queries get more complex, the ability to name and refer to specific parts becomes more and more powerful, while the query remains readable to a human, can be annotated with comments, and so on.

In the above query, there are three "blocks"---the first two constitute the *query*, and the third constitute the *results format*:

1. The first line simply defines a name we can use to refer to the segment/sentence level throughout the rest of the query. Most queries on text corpora will use this convention, though some exceptions apply, such as for multimodal corpora.
2. The second block defines a single token inside a sentence called `raceProcess`, matching the verb `race` in any form, as in `I raced to the exit`
3. A simple keyword-in-context/concordance, showing the `race` verb in the context the sentence it is in.

If you run this query on a valid corpus (i.e. one containing *lemmma* and *upos* annotations), LCP will search for the pattern and provide a KWIC display. The richness of this display will depend on the corpus; if a corpus is annotated with dependency relations, one can view each matching sentence as a dependency graph. For any KWIC result, it is also possible to view the results as a simple table of sentences (i.e. without the matching portion centred).

All queries contain one or more *query blocks*/*constraints*, which together define the query, followed by one or more *results blocks*, which enumerate the different result views (KWICs, frequency tables, collocations) required. The *query blocks*/*constraints* and *results blocks* are described in more detail individually below.

### Query/constraints definition

A query can be understood as one or more constraints, each of which narrows down the entire corpus to a set of tokens, sentences or annotations that satisfy all given contraints.

The first part(s) of the query specifies one or more lexicogrammatical features to match, as well as relationships between these features (e.g. dependency relationships, adjacency). In its simplest form, we provide and name a context (the sentence level) and a token to match:

```
Segment s

Token@s anyverb
  upos = "VERB"
```

#### Regular expressions

If you want to use regular expressions, rather than simple strings, quotation marks should become forward slashes. The example below is essentially equivalent to the one above:

```
Segment s

Token@s anyverb
  xpos = /V.*/
```

### String length

The `length(feature)` syntax can be provided to search based on the number of characters in a string:

```
Segment@d s

Token@s t3
  lemma = /^[ABC]/
  length(lemma) > 5
```

#### Negation

You can also negate equality with `!=`; below we find any *non-verbal token*

```
Segment s

Token@s nonverb
  upos != "VERB"
```

#### Mathematical operators

In addition to the `length(feature)` function, there are some other cases where mathematical operators can be used. For corpora with numerical metadata (timestamps, years, speaker IDs, etc.), you can perform basic mathematical operations  such as `<`, `>`, `<=` and `>=`:

```
Document d
  year > 1979

Segment@d s

Token@s shortWord
  length(form) <= 4
  upos != /PRON|ADP/
```

#### Sequence

Using the `sequence` keyword, one can define a multiword unit to match:

```
Segment s

sequence@s
  Token@s t1
    form = "very"
  Token@s t2
    upos = "ADJ"
```

In the example above, we match `very happy`, `very angry`, etc.

A `sequence` takes an optional argument specifying the minimum/maximum number of occurrences.

* `2..*` means *two or more times*
* `*..5` means *up to five times*
* `3..3` means `exactly three times`

Below, we allow any number of adjectives or adverbs, followed by a noun, "citizen". This could match `very pleasant local citizen`:

```
Segment s

sequence@s
  sequence 1..*
    Token classifier
      upos = /ADJ|ADV/
    Token head
      upos = "NOUN"
      lemma = "citizen"
```

#### Grammatical / dependency queries

The DQD syntax allows queries of dependency-annotated corpora. As a simple example, we could find nouns which govern verbs in the dependency graphs of a corpus:

```
Segment s

Token@s thead
  upos = "NOUN"
  lemma = /^d/
  length(lemma) > 3

Token@s thead
  upos = "VERB"
  DepRel
    head = thead
    dep = t3
```

In the above, note the important distinction between

1. Quotation marks (for string matching),
2. Forward slashes (for regular expressions)
3. No quotation marks or slashes, denoting either a number, or a reference to a named component within the query (`head = thead`, `dep = t3`)

#### `set` blocks

In most dependency grammars, a parent can have multiple child nodes. To express this, the `set` construct can be used:

```
Segment s

Token@s thead
  upos = "NOUN"
  lemma = "mirror"

set tdeps
  Token@s modifier
    DepRel
      head = thead
      dep = modifier
```

In the example above, a single result will conain the noun `mirror` and its immediate dependents; `big old mirror`, for example, is a single match. If we remove the `set` construct, `big old mirror` will match twice---one match being `big ,,, nirror` and the other being `old mirror`:


```
Segment s

Token@s thead
  upos = "NOUN"
  lemma = "mirror"


Token@s modifier
  DepRel
    head = thead
    dep = modifier
```

#### Time- and video-based queries

For corpora with time-alignment, it is possible to query based on temporal distance (i.e. how much time passed between two features). 15 minutes could be expressed as `900s`, '15m' or `0.25h`.

For a corpus of videos annotated with gesture information, we can query for a gesture that co-occurs temporally with an utterance. If interested in the gestures made by a speaker when talking about a direction, we can search for a three-second context via:

```
Document d

Segment@d s

Token@s direction_word
  form = /up|down|left|right/
  
Gesture g
  start(g) >= start(direction_word) - 3
  end(g) <= end(direction_word) + 3
```

### Results formats

Accompanying each query definition should be one or more blocks that specify the format of results. 

Currently, three types of result are possible, each with different options and parameters:

1. `plain`, which provides a simple KWIC table/list of matching esentences
2. `analysis`: a frequency table
3. `collocation`: calculate the ectent to which tokens tend to co-occur

Below we provide a query and request one of each result type:

```
Segment s

sequence@s
  Token@s intensifier
    form = "very"
  Token@s quality
    upos = "ADJ"

KWICTable1 => plain
    context
        s
    entities
        intensifier
        quality

frequencyCounts1 => analysis
    attributes
        quality.lemma
    functions
        frequency
    filter
        frequency > 10

collocationTable1 => collocation
    center
        quality
    window
        -5..+5
    attribute
        lemma
```

Each *result block* begins with a name that you can choose---this will be the name of the tab that appears in the interface. Following this is the specification of the result type, e.g. `=> collocation` for a collocation result.

You can request results in as many formats as you like, and different results blocks can focus on different parts of the query. For example, in the above query, we can generate separate collocation results for the adverb and the adjective:

```
Segment s

sequence@s
  Token@s intensifier
    form = "very"
  Token@s quality
    upos = "ADJ"

coll1 => collocation
    center
        intensifier
    attribute
        form

coll2 => collocation
    center
        quality
    attribute
        lemma
```


#### KWIC results

For KWIC results, create a block beginning with `<name> => plain`. Additionally, you need to specify:

1. The `context` (i.e. the span for the entire KWIC line, normally the sentence/segment level)
2. One or more `entities`, which should be displayed in the center/match column in the KWIC display

For example:

```
Segment@d s

sequence seq
  Token@s t1
    upos = "DET"
  Token@s t2
    upos = "ADJ"
  Token@s t3
    lemma = /^fr.*/
    length(lemma) > 5
    upos = "NOUN"

SimpleNP => plain
  context
    s
  entities
    t1
    t2
    t3
```

#### Frequency tables

Frequency tables are defined via `<name> => analysis`. You need to provide:

1. One or more *attributes*, the specific feature of each token to count
2. One or more *functions*; the mathematical operation to perform
3. One or more *filters*; predicates that restrict what can appear in the table

In the following, we get absolute frequencies, but skip instances that occur fewer than ten times:

```
Segment@d s

sequence seq
  Token@s t1
    upos = "DET"
  Token@s t2
    upos = "ADJ"
  Token@s t3
    lemma = /^fr.*/
    upos = "NOUN"

TotalFreq => analysis
  attributes
    t1.lemma
    t2.lemma
    t3.lemma
  functions
    frequency
  filter
    frequency > 10
```

#### Collocation

Collocation tables are defined via `<name> => collocation`. A collocation can have either:

1. A *center*, specifying the word collocates should be near; and *window*, specifying the distance in tokens to the left and right within which tokens can be counted
2. A *space*, which corresponds to a predefined *set* block, which defines the tokens that should be included, and how far they are from their *head*

These are shown as `collocationType1` and `collocationType2` below:

```
Segment@d s

sequence seq
    Token@s t1
        upos = "DET"
    Token@s t2
        upos = "ADJ"
    Token@s t3
        lemma = /^fr.*/
        upos = "NOUN"

set tdeps
    Token@s tx
        DepRel
            head = t3
            dep = tx


collocationType1 => collocation
    center
        t3
    window
        -5..+5
    attribute
        lemma

collocationType2 => collocation
    space
        tdeps
    attribute
        lemma
```

## Running queries

LCP is designed to work with corpora containing anywhere from hundreds to billions of words. Corpora with more than a million words are internally divided into subsections, each of which contains a randomised sample of sentences.

When KWIC queries are run, the LCP engine will query subsections of the corpus until a reasonable number of matches are provided (the usual default is currently around 200). Browsing through the pages of KWIC results can cause a paused query to continue, so that more pages are filled. This can be done until a hard maximum (currently around 1000 KWIC results) is reached.

ALternatively, you can click the `Search whole corpsu` button to run the query over the entire dataset. If your query contains no KWIC *result blocks* (i.e. only requests frequency tables and/or collocations), the entire corpus will be searched without pausing.

### Query cache

The LCP system remembers previous queries for a finite amount of time. If you rerun a query that was recently performed, the results can be retrieved from LCP's cache and loaded more quickly.

