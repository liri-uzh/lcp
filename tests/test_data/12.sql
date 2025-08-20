WITH RECURSIVE fixed_parts AS
  (SELECT "d"."char_range" AS "d_char_range",
          "d"."document_id" AS "d",
          "d"."meta"->>'classCode' AS "d_classCode",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1"."xpos2" AS "t1_xpos2",
          "t2"."char_range" AS "t2_char_range",
          "t2"."segment_id" AS "t2_segment_id",
          "t2"."token_id" AS "t2",
          "t2"."xpos2" AS "t2_xpos2",
          "t2_lemma"."lemma" AS "t2_lemma",
          "t3"."char_range" AS "t3_char_range",
          "t3"."token_id" AS "t3",
          "t3"."xpos2" AS "t3_xpos2"
   FROM
     (SELECT Segment_id
      FROM bnc1.fts_vectorrest vec
      WHERE vec.vector @@ '7ART <1> (2true & 7ADJ) <1> 7SUBST') AS fts_vector_s
   CROSS JOIN "bnc1"."document" "d"
   CROSS JOIN "bnc1"."tokenrest" "t1"
   CROSS JOIN "bnc1"."tokenrest" "t2"
   CROSS JOIN "bnc1"."tokenrest" "t3"
   CROSS JOIN "bnc1"."segmentrest" "s"
   CROSS JOIN "bnc1"."lemma" "t2_lemma"
   WHERE "d"."char_range" && "s"."char_range"
     AND "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "s"."segment_id" = "t1"."segment_id"
     AND ("t1"."xpos2")::text = ('ART')::text
     AND "s"."segment_id" = "t2"."segment_id"
     AND (("t2_lemma"."lemma")::text = ('true')::text
          AND ("t2"."xpos2")::text = ('ADJ')::text)
     AND "s"."segment_id" = "t3"."segment_id"
     AND ("t3"."xpos2")::text = ('SUBST')::text
     AND "t2"."token_id" - "t1"."token_id" = 1
     AND "t2_lemma"."lemma_id" = "t2"."lemma_id"
     AND "t3"."token_id" - "t2"."token_id" = 1
     AND ("d"."meta"->>'classCode')::text ~ '^S' ),
               gather AS
  (SELECT "d",
          "d_char_range",
          "d_classCode",
          "s",
          "s_char_range",
          "t1",
          "t1_char_range",
          "t1_xpos2",
          "t2",
          "t2_char_range",
          "t2_lemma",
          "t2_segment_id",
          "t2_xpos2",
          "t3",
          "t3_char_range",
          "t3_xpos2"
   FROM fixed_parts) ,
               match_list AS
  (SELECT gather."d" AS "d",
          gather."d_char_range" AS "d_char_range",
          gather."d_classCode" AS "d_classCode",
          gather."s" AS "s",
          gather."s_char_range" AS "s_char_range",
          gather."t1" AS "t1",
          gather."t1_char_range" AS "t1_char_range",
          gather."t1_xpos2" AS "t1_xpos2",
          gather."t2" AS "t2",
          gather."t2_char_range" AS "t2_char_range",
          gather."t2_lemma" AS "t2_lemma",
          gather."t2_segment_id" AS "t2_segment_id",
          gather."t2_xpos2" AS "t2_xpos2",
          gather."t3" AS "t3",
          gather."t3_char_range" AS "t3_char_range",
          gather."t3_xpos2" AS "t3_xpos2"
   FROM gather),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array(s, jsonb_build_array(t1, t2, t3))
   FROM match_list) ,
               collocates2 AS
  (SELECT "_token_collocate2"."form_id"
   FROM match_list
   CROSS JOIN "bnc1"."tokenrest" "_token_collocate2"
   WHERE "_token_collocate2"."token_id" <> match_list."t2"
     AND "_token_collocate2"."segment_id" = match_list."t2_segment_id"
     AND "_token_collocate2"."token_id" BETWEEN "t2" + (-2) AND "t2" + (2)),
               resXn2 AS
  (SELECT count(*) AS freq
   FROM collocates2),
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array("collocates2_form", o, e)
   FROM
     (SELECT "collocates2_form"."form" AS "collocates2_form",
             o,
             1. * x.freq / token_n.freq * resXn2.freq AS e
      FROM
        (SELECT "collocates2"."form_id",
                freq,
                count(*) AS o
         FROM collocates2
         JOIN bnc1.token_freq USING ("form_id")
         WHERE token_freq.lemma_id IS NULL
           AND token_freq.xpos1 IS NULL
           AND token_freq.xpos2 IS NULL
         GROUP BY "form_id",
                  freq) x
      CROSS JOIN "bnc1"."form" "collocates2_form"
      CROSS JOIN bnc1.token_n
      CROSS JOIN resXn2
      WHERE "collocates2_form"."form_id" = x."form_id") x) ,
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