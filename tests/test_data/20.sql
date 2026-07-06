WITH RECURSIVE fixed_parts AS
  (SELECT "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1_form"."form" AS "t1_form",
          "t1_lemma"."lemma" AS "t1_lemma"
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE vec.vector @@ E'(1?\\! | 2?\\!)') AS fts_vector_s
   CROSS JOIN "bnc1"."segmentrest" "s"
   CROSS JOIN "bnc1"."tokenrest" "t1"
   CROSS JOIN "bnc1"."form" "t1_form"
   CROSS JOIN "bnc1"."lemma" "t1_lemma"
   WHERE "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "s"."segment_id" = "t1"."segment_id"
     AND (("t1_form"."form")::text = ('?!')::text
          OR ("t1_lemma"."lemma")::text = ('?!')::text)
     AND "t1_form"."form_id" = "t1"."form_id"
     AND "t1_lemma"."lemma_id" = "t1"."lemma_id" ),
               gather AS
  (SELECT "s",
          "s_char_range",
          "t1",
          "t1_char_range",
          "t1_form",
          "t1_lemma",
          fixed_parts.t1 AS min_seq,
          fixed_parts.t1 AS max_seq
   FROM fixed_parts) ,
               match_list AS
  (SELECT "s",
          "s_char_range",
          "t1",
          ARRAY
     (SELECT "t"."token_id"
      FROM "bnc1"."tokenrest" "t"
      WHERE "t"."segment_id" = gather."s"
        AND "t"."token_id" BETWEEN gather."min_seq"::bigint AND gather."max_seq"::bigint) AS "seq"
   FROM gather),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("seq") , array[lower(match_list."s_char_range"), upper(match_list."s_char_range")])
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
