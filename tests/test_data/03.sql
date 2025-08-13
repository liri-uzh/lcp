WITH RECURSIVE fixed_parts AS
  (SELECT "d"."char_range" AS "d_char_range",
          "d"."document_id" AS "d",
          "d"."meta"->>'classCode' AS "d_classCode",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1"."xpos2" AS "t1_xpos2",
          "t4"."char_range" AS "t4_char_range",
          "t4"."token_id" AS "t4",
          "t4"."xpos2" AS "t4_xpos2"
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE vec.vector @@ '(1cat | 7ADJ <1> 1dog)'
        AND vec.vector @@ '7ART <1> (1cat | 7ADJ <1> 1dog) <1> 7VERB') AS fts_vector_s
   CROSS JOIN "bnc1"."document" "d"
   CROSS JOIN "bnc1"."tokenrest" "t1"
   CROSS JOIN "bnc1"."tokenrest" "t4"
   CROSS JOIN "bnc1"."segmentrest" "s"
   WHERE "d"."char_range" && "s"."char_range"
     AND "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "s"."segment_id" = "t1"."segment_id"
     AND ("t1"."xpos2")::text = ('ART')::text
     AND "s"."segment_id" = "t4"."segment_id"
     AND ("t4"."xpos2")::text = ('VERB')::text
     AND "t4"."token_id" - "t1"."token_id" < 4
     AND "t4"."token_id" - "t1"."token_id" > 1
     AND ("d"."meta"->>'classCode')::text ~ '^S' ),
               transition0 (source_state, dest_state, label, SEQUENCE) AS (
                                                                           VALUES (0,
                                                                                   2,
                                                                                   't2',
                                                                                   'anonymous4'), (0,
                                                                                                   3,
                                                                                                   'tadj',
                                                                                                   'anonymous'), (3,
                                                                                                                  1,
                                                                                                                  't3',
                                                                                                                  'anonymous')) ,
               traversal0 AS
  (SELECT prev_cte.s,
          prev_cte."t1",
          prev_cte."t4",
          prev_cte."d",
          prev_cte."d_char_range",
          prev_cte."d_classCode",
          prev_cte."s_char_range",
          prev_cte."t1_char_range",
          prev_cte."t1_xpos2",
          prev_cte."t4_char_range",
          prev_cte."t4_xpos2",
          "token"."token_id" start_id,
          "token"."token_id" id,
          transition0.dest_state state,
          jsonb_build_array(jsonb_build_array("token"."token_id", transition0.label, transition0.sequence)) token_list
   FROM fixed_parts prev_cte
   JOIN "bnc1"."tokenrest" "token" ON "token".segment_id = prev_cte."s"
   AND "token"."token_id" = prev_cte.t1 + 1
   JOIN transition0 ON transition0.source_state = 0
   LEFT JOIN "bnc1"."form" "token_form" ON "token_form"."form_id" = "token"."form_id"
   WHERE ("token"."token_id" = "prev_cte"."t1" + 1)
     AND ((transition0.dest_state = 2
           AND "s" = "token"."segment_id"
           AND ("token_form"."form")::text = ('cat')::text
           AND "token_form"."form_id" = "token"."form_id"
           AND transition0.label = 't2')
          OR (transition0.dest_state = 3
              AND "s" = "token"."segment_id"
              AND ("token"."xpos2")::text = ('ADJ')::text
              AND transition0.label = 'tadj'))
   UNION ALL SELECT traversal0.s,
                    traversal0."t1",
                    traversal0."t4",
                    traversal0."d",
                    traversal0."d_char_range",
                    traversal0."d_classCode",
                    traversal0."s_char_range",
                    traversal0."t1_char_range",
                    traversal0."t1_xpos2",
                    traversal0."t4_char_range",
                    traversal0."t4_xpos2",
                    traversal0.start_id,
                    "token"."token_id" id,
                    transition0.dest_state,
                    traversal0.token_list || jsonb_build_array(jsonb_build_array("token"."token_id", transition0.label, transition0.sequence))
   FROM traversal0 traversal0
   JOIN transition0 ON transition0.source_state = traversal0.state
   JOIN "bnc1"."tokenrest" "token" ON "token"."token_id" = traversal0.id + 1
   AND "token".segment_id = traversal0."s"
   LEFT JOIN "bnc1"."form" "token_form" ON "token_form"."form_id" = "token"."form_id"
   WHERE (transition0.source_state = 3
          AND transition0.dest_state = 1
          AND "s" = "token"."segment_id"
          AND ("token_form"."form")::text = ('dog')::text
          AND "token_form"."form_id" = "token"."form_id"
          AND transition0.label = 't3') ) SEARCH DEPTH FIRST BY id
SET ordercol ,
    gather AS
  (SELECT "d",
          "d_char_range",
          "d_classCode",
          "s",
          "s_char_range",
          "t1",
          "t1_char_range",
          "t1_xpos2",
          "t4",
          "t4_char_range",
          "t4_xpos2",
          traversal0.t1 AS min_seq,
          traversal0.t4 AS max_seq
   FROM
     (SELECT *
      FROM traversal0
      WHERE (traversal0.state IN (1,
                                  2)
             AND traversal0.t4 = traversal0.id + 1)
      ORDER BY ordercol) traversal0) ,
    match_list AS
  (SELECT ARRAY
     (SELECT t.token_id
      FROM bnc1.tokenrest t
      WHERE t.segment_id = gather.s
        AND t.token_id BETWEEN gather.min_seq::bigint AND gather.max_seq::bigint) AS seq,
          gather."d" AS "d",
          gather."d_char_range" AS "d_char_range",
          gather."d_classCode" AS "d_classCode",
          gather."s" AS "s",
          gather."s_char_range" AS "s_char_range",
          gather."t1" AS "t1",
          gather."t1_char_range" AS "t1_char_range",
          gather."t1_xpos2" AS "t1_xpos2",
          gather."t4" AS "t4",
          gather."t4_char_range" AS "t4_char_range",
          gather."t4_xpos2" AS "t4_xpos2"
   FROM gather),
    res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array(s, jsonb_build_array(seq))
   FROM match_list) ,
    res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1 ;
