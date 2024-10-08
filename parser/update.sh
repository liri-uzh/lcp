#!/bin/bash

python lark_to_cobquec.py dqd_grammar.lark cobquec.auto.json

lark-js dqd_grammar.lark -o dqd_parser.js

echo "/* eslint-disable */" | cat - dqd_parser.js > temp_dqd_parser && mv temp_dqd_parser dqd_parser.js
sed -i 's/\s.*"strict"/\/\/  "strict"/' dqd_parser.js
sed -i 's/\s.*"ordered_sets"/\/\/  "ordered_sets"/' dqd_parser.js

cp dqd_parser.js ../frontend/src/