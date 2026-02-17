WITH RECURSIVE fixed_parts AS
  (SELECT "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."segment_id" AS "t1_segment_id",
          "t1"."token_id" AS "t1",
          "t1"."xpos2" AS "t1_xpos2",
          "t2"."char_range" AS "t2_char_range",
          "t2"."token_id" AS "t2",
          "t2"."xpos2" AS "t2_xpos2",
          "t3"."char_range" AS "t3_char_range",
          "t3"."token_id" AS "t3",
          "t3"."xpos2" AS "t3_xpos2"
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE vec.vector @@ '7ART <1> 7ADJ <1> 7SUBST') AS fts_vector_s
   CROSS JOIN "bnc1"."segmentrest" "s"
   CROSS JOIN "bnc1"."tokenrest" "t1"
   CROSS JOIN "bnc1"."tokenrest" "t2"
   CROSS JOIN "bnc1"."tokenrest" "t3"
   WHERE "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "s"."segment_id" = "t1"."segment_id"
     AND ("t1"."xpos2")::text = ('ART')::text
     AND "s"."segment_id" = "t2"."segment_id"
     AND ("t2"."xpos2")::text = ('ADJ')::text
     AND "s"."segment_id" = "t3"."segment_id"
     AND ("t3"."xpos2")::text = ('SUBST')::text
     AND "t2"."token_id" - "t1"."token_id" = 1
     AND "t3"."token_id" - "t2"."token_id" = 1 ),
               gather AS
  (SELECT "s",
          "s_char_range",
          "t1",
          "t1_char_range",
          "t1_segment_id",
          "t1_xpos2",
          "t2",
          "t2_char_range",
          "t2_xpos2",
          "t3",
          "t3_char_range",
          "t3_xpos2",
          fixed_parts.t1 AS min_seq,
          fixed_parts.t3 AS max_seq
   FROM fixed_parts) ,
               match_list AS
  (SELECT ARRAY
     (SELECT "t"."token_id"
      FROM "bnc1"."tokenrest" "t"
      WHERE "t"."segment_id" = gather."s"
        AND "t"."token_id" BETWEEN gather."min_seq"::bigint AND gather."max_seq"::bigint) AS "seq",
          gather."s" AS "s",
          gather."s_char_range" AS "s_char_range",
          gather."t1" AS "t1",
          gather."t1_char_range" AS "t1_char_range",
          gather."t1_segment_id" AS "t1_segment_id",
          gather."t1_xpos2" AS "t1_xpos2",
          gather."t2" AS "t2",
          gather."t2_char_range" AS "t2_char_range",
          gather."t2_xpos2" AS "t2_xpos2",
          gather."t3" AS "t3",
          gather."t3_char_range" AS "t3_char_range",
          gather."t3_xpos2" AS "t3_xpos2"
   FROM gather),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("t3") , array[lower(match_list."s_char_range"), upper(match_list."s_char_range")])
   FROM match_list) ,
               collocates2 AS
  (SELECT "_token_collocate2"."lemma_id"
   FROM match_list
   CROSS JOIN "bnc1"."tokenrest" "_token_collocate2"
   WHERE NOT "_token_collocate2"."token_id" = ANY(match_list."seq")
     AND "_token_collocate2"."segment_id" = match_list."t1_segment_id"
     AND "_token_collocate2"."token_id" BETWEEN "seq"[1] + (-2) AND "seq"[array_length("seq", 1)] + (2)),
               resXn2 AS
  (SELECT count(*) AS freq
   FROM collocates2),
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array("collocates2_lemma", o, e)
   FROM
     (SELECT "collocates2_lemma"."lemma" AS "collocates2_lemma",
             o,
             1. * x.freq / token_n.freq * resXn2.freq AS e
      FROM
        (SELECT "collocates2"."lemma_id",
                freq,
                count(*) AS o
         FROM collocates2
         JOIN bnc1.token_freq USING ("lemma_id")
         WHERE token_freq.form_id IS NULL
           AND token_freq.xpos1 IS NULL
           AND token_freq.xpos2 IS NULL
         GROUP BY "lemma_id",
                  freq) x
      CROSS JOIN "bnc1"."lemma" "collocates2_lemma"
      CROSS JOIN bnc1.token_n
      CROSS JOIN resXn2
      WHERE "collocates2_lemma"."lemma_id" = x."lemma_id") x) ,
               res0 AS
  (SELECT 0::int2 AS rstype,
          jsonb_build_array(count(match_list.*))
   FROM match_list)
SELECT *
FROM res0
UNION ALL
SELECT *
FROM res1
UNION ALL
SELECT *
FROM res2 ;