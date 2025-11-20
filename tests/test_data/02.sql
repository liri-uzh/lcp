WITH RECURSIVE fixed_parts AS
  (SELECT "e"."alignment_id" AS "e",
          "e"."char_range" AS "e_char_range",
          "e_aligned"."meta"->>'date' AS "e_aligned_date",
          "s"."char_range" AS "s_char_range",
          "s"."segment_id" AS "s",
          "t1"."char_range" AS "t1_char_range",
          "t1"."token_id" AS "t1",
          "t1"."upos" AS "t1_upos",
          "t1_lemma"."lemma" AS "t1_lemma",
          "t2"."char_range" AS "t2_char_range",
          "t2"."token_id" AS "t2",
          "t2"."upos" AS "t2_upos",
          "t3"."char_range" AS "t3_char_range",
          "t3"."token_id" AS "t3",
          "t3"."upos" AS "t3_upos",
          "t3"."xpos" AS "t3_xpos"
   FROM
     (SELECT Segment_id
      FROM sparcling1.fts_vector_enrest vec
      WHERE vec.vector @@ '3VERB <1> 3DET <1> (3NOUN & 6NP)') AS fts_vector_s
   CROSS JOIN "sparcling1"."session_en" "e"
   CROSS JOIN "sparcling1"."session_alignment" "e_aligned"
   CROSS JOIN "sparcling1"."segment_enrest" "s"
   CROSS JOIN "sparcling1"."deprel_en" "anonymous"
   CROSS JOIN "sparcling1"."token_enrest" "t1"
   CROSS JOIN "sparcling1"."lemma_en" "t1_lemma"
   CROSS JOIN "sparcling1"."token_enrest" "t2"
   CROSS JOIN "sparcling1"."token_enrest" "t3"
   WHERE "e"."alignment_id" = "e_aligned"."alignment_id"
     AND "e"."char_range" && "s"."char_range"
     AND "fts_vector_s"."segment_id" = "s"."segment_id"
     AND "s"."segment_id" = "t1"."segment_id"
     AND ("t1"."upos")::text = ('VERB')::text
     AND "s"."segment_id" = "t2"."segment_id"
     AND ("t2"."upos")::text = ('DET')::text
     AND "s"."segment_id" = "t3"."segment_id"
     AND (("t3"."upos")::text = ('NOUN')::text
          AND ("t3"."xpos")::text = ('NP')::text)
     AND "t1_lemma"."lemma_id" = "t1"."lemma_id"
     AND "t2"."token_id" - "t1"."token_id" = 1
     AND "t3"."token_id" - "t2"."token_id" = 1
     AND ("anonymous"."dependent" = "t3"."token_id"
          AND "anonymous"."head" = "t1"."token_id"
          AND ("anonymous"."udep")::text = ('dobj')::text)
     AND ("e_aligned"."meta"->>'date')::text ~ '^2000' ),
               gather AS
  (SELECT "e",
          "e_aligned_date",
          "e_char_range",
          "s",
          "s_char_range",
          "t1",
          "t1_char_range",
          "t1_lemma",
          "t1_upos",
          "t2",
          "t2_char_range",
          "t2_upos",
          "t3",
          "t3_char_range",
          "t3_upos",
          "t3_xpos"
   FROM fixed_parts) ,
               match_list AS
  (SELECT gather."e" AS "e",
          gather."e_aligned_date" AS "e_aligned_date",
          gather."e_char_range" AS "e_char_range",
          gather."s" AS "s",
          gather."s_char_range" AS "s_char_range",
          gather."t1" AS "t1",
          gather."t1_char_range" AS "t1_char_range",
          gather."t1_lemma" AS "t1_lemma",
          gather."t1_upos" AS "t1_upos",
          gather."t2" AS "t2",
          gather."t2_char_range" AS "t2_char_range",
          gather."t2_upos" AS "t2_upos",
          gather."t3" AS "t3",
          gather."t3_char_range" AS "t3_char_range",
          gather."t3_upos" AS "t3_upos",
          gather."t3_xpos" AS "t3_xpos"
   FROM gather),
               res1 AS
  (SELECT DISTINCT 1::int2 AS rstype,
                   jsonb_build_array("s", jsonb_build_array("t1", "t2", "t3") , array[lower(match_list."s_char_range"), upper(match_list."s_char_range")])
   FROM match_list) ,
               res2 AS
  (SELECT 2::int2 AS rstype,
          jsonb_build_array(FALSE, "t1_lemma", frequency)
   FROM
     (SELECT "t1_lemma" ,
             count(*) AS frequency
      FROM match_list
      GROUP BY "t1_lemma") x
   WHERE frequency > 1 ) ,
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
