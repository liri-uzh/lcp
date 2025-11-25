# Importing

You can import your own corpora into LCP using a tool called `lcpcli`. This page describes how to use it.

## LCPCLI

The tool `lcpcli` is a python library that lets you prepare and upload LCP corpora. It can be imported in python or used in a command line.

### Installation

Make sure you have python 3.11+ with `pip` installed in your local environment, then run

```bash
pip install lcpcli
```

### Corpus preparation

To prepare an LCP corpus before importing it, you can either:

 - [convert CoNNL-U files](import_conllu.md), or
 - [use the `Corpus` class in the `lcpcli.builder` python submodule](builder.md); the [tutorial](import_tutorial_part1.md) walks you through its use to import a corpus into LCP

### Corpus import

Once you have prepared your corpus files, you can upload them to a collection in LCP by following these steps:

1. Visit an LCP instance (e.g. _catchphrase_) and create a new collection if you don't already have one where your corpus should go.

2. Retrieve the API key and secret for your collection by clicking on the button that says: "Create API Key"

    The secret will appear at the bottom of the page and remain visible only for 120s, after which it will disappear forever (you would then need to revoke the API key and create a new one)
    
    The key itself is listed above the button that says "Revoke API key" (make sure to **not** copy the line that starts with "Secret Key" along with the API key itself)

3. Once you have your API key and secret, you can start converting and uploading your corpus by running the following command:

```
lcpcli -i $CONLLU_FOLDER -o $OUTPUT_FOLDER -m upload -k $API_KEY -s $API_SECRET -p $COLLECTION --live
```

- `$CONLLU_FOLDER` should point to the folder that contains your CONLLU files.
- `$OUTPUT_FOLDER` should point to *another* folder that will be used to store the converted files to be uploaded.
- `$API_KEY` is the key you copied from your collection on LCP (still visible when you visit the page).
- `$API_SECRET` is the secret you copied from your collection on LCP (only visible upon API Key creation).
- `$COLLECTION` is the name of the collection exactly as displayed on LCP — it is case-sensitive, and space characters should be escaped.

